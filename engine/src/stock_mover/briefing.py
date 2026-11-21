"""Prepare and check the engine facts used in the morning briefing."""

import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from decimal import Decimal
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from stock_mover.constants import REPO_ROOT
from stock_mover.contract import Briefing, Run

Facts = dict[str, Any]
LLM = Callable[[str, str], str]
TOP_MOVE_LIMIT = 5
SYSTEM_PROMPT = (
    "Write a plain-text morning briefing for a Manyavar merchandiser in two to four "
    "short sentences. Start with total moves, units and MRP. Mention senior approval "
    "and a priority or data issue if useful. Use only the supplied JSON facts. "
    "Copy counts, full rupee figures and any identifiers exactly. Use digits for "
    "numbers. Avoid rounding, percentages, derived figures, and numbered lists. "
    "Return only the briefing."
)

NUMBER = r"[+\-\u2212]?(?:(?:\d+(?:,\d{3})+|\d{1,3}(?:,\d{2})+,\d{3}|\d+)(?:\.\d+)?|\.\d+)"
PERCENT_SIGN = r"[%％٪﹪]"
RATE_SUFFIX = (
    rf"(?:{PERCENT_SIGN}|percent(?:age)?\b(?:[\s-]+points?\b)?|"
    r"per[\s-]+cent\b|pct\b(?:[\s-]+(?:points?|pts?)\b)?|"
    r"p\.?p\.?(?:ts?\.?)?(?!\w)|basis[\s-]+points?\b|b\.?p\.?s?\.?(?!\w))"
)
TOKEN = re.compile(
    rf"{PERCENT_SIGN}\s*{NUMBER}(?!\w|[.,]\d)|"
    r"(?<!\w)(?:(?=[\w./-]*[^\W\d])\w+(?:[-./]\w+)*|"
    rf"\d{{4}}-\d{{2}}-\d{{2}}(?!\w)|"
    rf"{NUMBER}(?:\s*[/:\u2044\u2215\u2236\uff0f\uff1a]\s*{NUMBER})+(?!\w|[.,]\d)|"
    rf"{NUMBER}(?!\w|[.,]\d)(?:\s*{RATE_SUFFIX})?|\d+)",
    re.IGNORECASE,
)


def format_inr(value: float) -> str:
    """Whole rupees with Indian digit grouping: 11393257 -> 1,13,93,257."""
    digits = str(round(value))
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + groups + [tail])


def build_facts(run: Run) -> Facts:
    moves = run.moves
    counts = Counter(move.type for move in moves)
    value = round(sum(move.value_mrp for move in moves))
    top = sorted(moves, key=lambda move: (-move.priority, move.id))[:TOP_MOVE_LIMIT]
    return {
        "data_as_of": run.run.data_as_of.isoformat(),
        "totals": {
            "moves": len(moves),
            "units": sum(move.units for move in moves),
            "value_mrp": value,
            "value_mrp_indian_grouping": format_inr(value),
            "warehouse_to_store": counts["warehouse_to_store"],
            "store_to_store": counts["store_to_store"],
            "pull_back": counts["pull_back"],
            "senior_approval": sum(move.needs_senior_approval for move in moves),
            "excluded_issues": sum(issue.excluded for issue in run.data_issues),
        },
        "top_moves": [
            {
                "id": move.id, "sku_id": move.sku_id, "style_id": move.style_id,
                "style_name": move.style_name, "from": move.from_location,
                "to": move.to_location, "units": move.units, "reason": move.reason,
            }
            for move in top
        ],
        "data_issues": [
            issue.model_dump(include={"location_id", "sku_id", "note", "excluded"})
            for issue in run.data_issues
        ],
        "rules": {"passed": sum(rule.passed for rule in run.rule_check), "total": len(run.rule_check)},
        "under_stocked_stores": sum("under_stocked" in store.flags for store in run.stores),
    }


def _fact_tokens(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _fact_tokens(item)
    elif isinstance(value, list):
        for item in value:
            yield from _fact_tokens(item)
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        yield from TOKEN.findall(str(value))


def _normalize(token: str) -> str | Decimal:
    if re.fullmatch(NUMBER, token):
        return Decimal(token.replace(",", "").replace("−", "-"))
    return token.casefold()


def check_numbers(text: str, facts: Facts) -> list[str]:
    """Return the distinct numeric tokens that cannot be traced to the facts."""
    allowed = {_normalize(token) for token in _fact_tokens(facts)}
    allowed.update(Decimal(part) for part in facts["data_as_of"].split("-"))
    return list(dict.fromkeys(
        token for token in TOKEN.findall(text)
        if any(char.isnumeric() for char in token) and _normalize(token) not in allowed
    ))


def write_briefing(facts: Facts, llm: LLM | None, fallback: Briefing) -> Briefing:
    if llm is None:
        print("Using template briefing: Sarvam key or model is missing.", file=sys.stderr)
        return fallback

    facts_json = json.dumps(facts, ensure_ascii=False)
    prompt = facts_json
    for _ in range(2):
        try:
            result = llm(SYSTEM_PROMPT, prompt)
            if isinstance(result, str):
                result.encode("utf-8")
        except HTTPError as error:
            print(f"Using template briefing: Sarvam HTTP {error.code}.", file=sys.stderr)
            return fallback
        except (OSError, HTTPException, ValueError, KeyError, IndexError, TypeError):
            print("Using template briefing: Sarvam request failed or response was invalid.", file=sys.stderr)
            return fallback
        if not isinstance(result, str) or not result.strip():
            print("Using template briefing: Sarvam returned no text.", file=sys.stderr)
            return fallback
        rejected = check_numbers(result, facts)
        if not rejected:
            return Briefing(text=result.strip(), source="llm", checked=True)
        prompt = (
            facts_json
            + "\nThe previous response used unlisted numeric tokens: "
            + json.dumps(rejected, ensure_ascii=False)
            + ". Rewrite the briefing using only numbers in the supplied facts."
        )
    print("Using template briefing: Sarvam used unlisted numbers twice.", file=sys.stderr)
    return fallback


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def configured_sarvam() -> LLM | None:
    names = ("SARVAM_API_KEY", "SARVAM_MODEL")
    local = {}
    try:
        for line in (REPO_ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in names:
                local[name.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    except (OSError, UnicodeError):
        print("Could not read the local Sarvam settings.", file=sys.stderr)
    api_key, model = (os.environ.get(name, local.get(name, "")).strip() for name in names)
    if not api_key or not model:
        return None

    opener = build_opener(_NoRedirects())

    def complete(system: str, user: str) -> str:
        # The smoke test confirmed V1, api-subscription-key and choices[0].message.content.
        request = Request(
            "https://api.sarvam.ai/v1/chat/completions",
            headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "reasoning_effort": None,
                "max_tokens": 350,
            }).encode("utf-8"),
        )
        with opener.open(request, timeout=30) as response:
            try:
                content = json.load(response)["choices"][0]["message"]["content"]
            except RecursionError as error:
                raise ValueError("Assistant response JSON is too deeply nested") from error
        if not isinstance(content, str) or api_key in content:
            raise ValueError("Invalid assistant content")
        return content

    return complete
