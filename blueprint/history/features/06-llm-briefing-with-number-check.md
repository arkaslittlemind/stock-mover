# Feature: LLM briefing with number check

**From build-plan:** feature 6
**Build attempt:** 1
**Branch:** feature/llm-briefing-with-number-check
**Status:** verified

## Goal

Replace the template morning briefing with a short Sarvam AI summary written from engine facts only, and publish it only when every number in it is traceable to those facts. A text that fails the check is retried once, then the existing template briefing is used. The run file says which one it is (`briefing.source`, `briefing.checked`) and the page labels it "AI-written, numbers checked".

## In scope

- A facts JSON built from the finished `Run` (never raw tables): run date, totals (moves, units, MRP value as a plain number, count per move type, senior-approval count), the top moves by priority (id, SKU, style name, from, to, units, one-line reason), data issues (location, SKU, plain-words note, excluded), rule check (rules passed of total), and store health counts (under-stocked stores).
- A Sarvam chat-completions client in the engine (stdlib `urllib`, no new dependency). Key from `SARVAM_API_KEY`, model from `SARVAM_MODEL`, both from the environment only. A small `.env` reader at the repo root so a local run works; real environment variables win. Timeout on the call.
- A number checker: every number in the text must appear in the facts. Numbers compare by value after removing digit-grouping commas (so Indian grouping `1,13,93,257` equals `11393257`). Identifiers that appear in the facts (store, SKU, style codes) and the facts' date parts are not treated as stray numbers; any other digit run not in the facts rejects the text.
- Retry once with the offending numbers named in the prompt, then fall back to `template_briefing` (`source: "template"`, `checked: true`, as today). The accepted LLM text is stored with `source: "llm"`, `checked: true`.
- Fallback also covers: no key or model set, HTTP or network error, timeout, malformed response, empty text. None of these may fail the run or write a partial file. The reason is printed to stderr without the key or the response body of an auth error.
- `build_run` takes an optional briefing writer (a callable from facts to text) so tests inject a fake. CLI `stock-mover run` wires the Sarvam writer when the key is set, and adds `--no-llm` to force the template.
- Page: label for `source: "llm"` and `checked: true` becomes "AI-written, numbers checked". `llm` with `checked: false` cannot be produced by the engine and is not given new UI; the template label stays "Template".
- Regenerate `apps/web/data/seed-run.json` once with the real briefing (trigger `seed`), so the live page shows it after push.

## Out of scope

- Data-issue notes written by the LLM (they stay the engine's templates), the daily job, Blob upload and run-info trigger text (item 7), any change to moves, rules or the run schema, streaming, multiple providers, caching of LLM output, and number words ("three") or lakh/crore wording checks. The prompt asks for digits and full figures, and anything else that introduces a number not in the facts is rejected and falls back.
- Page views never call the LLM.

## Build loop

Feature-level approval per `workflow.stepReview: feature`; checkpoint commits are disabled. Run `/check` before `/complete`; `/complete` creates the single feature commit. The LLM budget is about 20 calls for the whole day, so tests use a fake writer and the real service is called only in step 1 and step 4.

## Build steps

- [x] **1. Prove the key and the call shape.** Ask the user for `SARVAM_API_KEY` and the `SARVAM_MODEL` name (secret request, never printed or committed). Make one tiny real call and record the confirmed endpoint, auth header and response shape in a code comment next to the client. Put the values in the repo-root `.env` (already gitignored; confirm with `git check-ignore .env`). **Done when** the one-line call returns text with HTTP 200 and `git status` does not list `.env`. If the key does not work, stop and report; steps 2 and 3 can still be built and tested with the fake.
- [x] **2. Facts and number checker.** New `engine/src/stock_mover/briefing.py` with `build_facts(run)`, `check_numbers(text, facts)` and the prompt text. Facts cap the top moves at a small fixed count and are the only input to the prompt. **Done when** `uv run pytest -q` includes tests that show: the facts contain no raw table rows and no more than the capped moves; a text using only fact numbers passes, including Indian-grouped rupees and codes such as LKO-01 and KUR-04; a text with an invented number (a count, a percentage, an unlisted code digit) is rejected and the bad number is named; grouping commas and decimals compare by value.
- [x] **3. Writer with retry and fallback, wired into the run.** In `briefing.py`: `write_briefing(facts, llm, fallback)` with one retry and fallback on every failure listed in scope; the Sarvam client and `.env` reader; `build_run(..., briefing_writer=None)`; CLI `--no-llm`. **Done when** tests with a fake LLM prove: valid text gives `llm` and `checked: true`; an invented number on the first try and a clean second try gives `llm` after exactly 2 calls; invented numbers twice gives the template after exactly 2 calls; an LLM that raises, times out or returns empty gives the template with no exception; no key set gives the template with 0 calls; and a run built with the template stays byte-for-byte the same as the current seed apart from run id and timestamps. The API key never appears in the run JSON or the stderr text (asserted).
- [x] **4. Real run, seed and page label.** Run `uv run stock-mover run --trigger seed` with the real key (one call, at most one retry), validate the output against the schema, copy it to `apps/web/data/seed-run.json`, and change the label in `RunConsole.tsx`. **Done when** the new seed has `briefing.source: "llm"` and `checked: true` and passes the schema test; `pnpm lint`, `pnpm exec tsc --noEmit` and `pnpm build` pass; and the page in a browser at 1440 px and 390 px shows the briefing with "AI-written, numbers checked" and no horizontal scroll. If the real call falls back to the template, say so, keep the template seed, and do not claim the real-run done-when.
- [x] **5. Repair independent review findings F-01 through F-03.** Route malformed assistant Unicode through the template fallback, reject HTTP redirects at the Sarvam endpoint, and check fractions and ratios as whole expressions. **Done when** focused regressions and the engine suite pass and the stored seed still passes the checker.
- [x] **6. Repair the remaining independent review findings.** Recognize line breaks in fractions and ratios and alternate percentage formats. Fall back when the provider returns overly nested JSON. **Done when** focused regressions and the engine suite pass and the stored seed still passes the checker.
- [x] **7. Complete percentage-format coverage from review.** Treat leading localized percent signs and written percentage-point and basis-point expressions as complete numeric tokens. **Done when** regressions reject those expressions even if the bare count appears in the facts.
- [x] **8. Recognize abbreviated percentage points.** Treat common percentage-point and basis-point abbreviations as complete numeric tokens and cover the independent review examples.

## Files / areas

- New: `engine/src/stock_mover/briefing.py`, `engine/tests/test_briefing.py`.
- Edit: `engine/src/stock_mover/run.py` (optional briefing writer), `engine/src/stock_mover/cli.py` (`--no-llm`, writer wiring), `apps/web/src/components/approve/RunConsole.tsx` (label), `apps/web/data/seed-run.json` (regenerated).
- Unchanged: `contract.py`, `run.schema.json`, `apps/web/src/lib/run.ts` (the `briefing` shape already allows this), `.env.example` (already lists both variables).

## Data / contracts

- `Briefing { text: str, source: "llm" | "template", checked: bool }` is unchanged. The engine only emits `llm` with `checked: true`, or `template` with `checked: true`.
- Facts shape is internal to the engine: plain JSON, numbers as numbers (MRP value as an integer rupee amount, with a pre-formatted Indian-grouped string alongside so the model can quote it exactly).
- Briefing writer: `Callable[[dict], str]`-style seam over an `llm(system, user) -> str` function; tests pass a fake. The check runs on the final text only; the template is built from the same moves and issues as today.
- Env: `SARVAM_API_KEY`, `SARVAM_MODEL`. No key in code, logs, run JSON, or tests.

## Testing

Engine logic has a test gate (`uv run pytest -q`; 108 pass before this feature). All checker, retry and fallback behaviour is covered with a fake LLM and no network. The real call is evidence only in steps 1 and 4. The page has no unit runner: verify with lint, typecheck, build and browser evidence at 1440 px and 390 px. No claim of live-URL evidence until the push is deployed and checked.

## Notes for the AI

- Follow Blueprint's `implement`, not the user-level one. Never push; the user approves commit, merge and push, then check https://stock-mover.vercel.app with no sign-in.
- The LLM budget is tight (about 20 calls in total). Do not loop real calls while debugging; reproduce with the fake.
- Do not print, log or commit the key. Auth errors must not echo request headers.
- Keep moves, rules and the schema untouched. The seed's moves must stay identical to today's.
- Feature freeze is 3:45 pm. If the real call is unavailable, ship steps 2 and 3 with the template seed (cut order item 3) and say so.

## Implementation evidence

- Sarvam HTTP 200 with non-empty assistant text for the approved `sarvam-105b` model. The first smoke request returned empty content with a 32-token limit and default reasoning. A second smoke request with reasoning off returned text. Git ignores the local environment file.
- The real seed run returned a checked LLM briefing on the first attempt. The seed passes the existing schema and preserves all 1,916 moves, rules, issues and store health records. The template run matches the previous seed after normalizing the run ID, generated timestamp and checkout line endings.
- Verification passed with 122 engine tests, web lint, standalone typecheck, and production build. The local production page showed the checked briefing at 1440 and 390 px with no horizontal overflow.
- Independent-review repairs passed 125 engine tests, web lint, standalone typecheck, and production build. The stored Sarvam briefing also passed the repaired checker without a new provider call.
- The remaining review repairs passed 132 engine tests, web lint, standalone typecheck, and production build. The stored checked briefing passed again without a provider call.
- The percentage-format follow-up passed all 139 engine tests. The stored Sarvam seed passed the latest checker without a provider call. Web source and seed are identical to the verified production build.
- The abbreviation repair passed 144 engine tests, and the stored briefing passed the updated checker. The previously verified web source and seed are unchanged from their production build.


<!-- blueprint:completion {"schemaVersion":2,"specBytes":11119,"specSha256":"a07660a060df67151b3a0470c62ab3468e73b50e59a2d061e4a6958f1c251689","branch":"refs/heads/feature/llm-briefing-with-number-check","head":"7e4dae7c0ce1da9e8e1f667253fff001469c116b","baseRef":"refs/heads/main","baseCommit":"e060bbd45586f75236919a83c81e25356ef2b3e8","sourceTree":"a87a0f22489ced73bfbec541574e5b4505aa0c78","landing":"local-merge","absentOptional":[]} -->

## Findings

### 6/F-01 [P1] closed - Malformed assistant text can abort run serialization

**File:** engine/src/stock_mover/briefing.py:131
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** JSON decoding can return a string containing an unpaired Unicode surrogate. With a fake writer, the engine accepted that string as a checked briefing. Serializing the run then raised PydanticSerializationError before the CLI wrote the run. The feature requires the template fallback for malformed responses.
**Suggested fix:** Validate that response text encodes as UTF-8 before accepting it. Route encoding failures through the existing sanitized fallback and cover the malformed string through run serialization.
**Resolution:** Malformed assistant Unicode now returns the template. Independently confirmed with the passing regression that serializes the fallback run.

### 6/F-02 [P1] closed - HTTP redirects can forward the Sarvam subscription header

**File:** engine/src/stock_mover/briefing.py:174
**Found:** 2026-11-21 by /audit (scope: current; lens: security)
**Why it matters:** The request attaches the subscription key as a regular header. The installed urllib redirect handler follows supported POST redirects and copies that header without checking the destination origin, expanding the credential boundary beyond the configured HTTPS endpoint.
**Suggested fix:** Disable redirects for this request and let the existing sanitized HTTP failure path return the template. Verify the credential stays scoped to the original endpoint using fake response data.
**Resolution:** The Sarvam opener declines redirects. Independently confirmed with the passing simulated HTTP 302 regression that only the configured endpoint receives the request.

### 6/F-03 [P1] closed - Fractions and ratios can pass as checked numbers

**File:** engine/src/stock_mover/briefing.py:101
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** Against the committed seed facts, the checker accepted fabricated values written as `1/2` and `2:1`. The tokenizer splits each expression and approves the separate digits when they happen to exist in unrelated facts. This permits derived figures to reach the checked briefing.
**Suggested fix:** Treat digit-only fractions and ratios as whole expressions and reject them when absent from the facts. Add cases that reuse allowed component digits.
**Resolution:** Compound-number parsing now includes line breaks and common fraction and ratio symbols. The independent run passed regressions for wrapped operands whose individual digits are allowed.

### 6/F-04 [P1] closed - Spelled and localized percentages pass as checked numbers

**File:** engine/src/stock_mover/briefing.py:34
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** The checker ties only the ASCII percent sign to the number. Against the actual seed facts, a fake assistant response saying "Senior approval is required for 2 percent of moves" received the checked LLM label. The same happens with a fullwidth percent sign. The facts contain 2 excluded issues and 18 senior approvals out of 1,916 moves, so this publishes an invented percentage despite the feature's explicit percentage check.
**Suggested fix:** Recognize percentage expressions before comparing token values, including percentage-point wording and a percent sign preceding the number. Cover expressions whose digits exist elsewhere in the facts.
**Resolution:** The scanner now recognizes leading percent signs, percentage points, basis points and their tested variants as complete numeric tokens. The 139-test engine suite passed. The fresh review passed all 31 focused tests and confirmed that the written percentage-point expression falls back against the committed seed.

### 6/F-05 [P1] closed - Overly nested response JSON escapes the template fallback

**File:** engine/src/stock_mover/briefing.py:185
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** Python's JSON decoder raises RecursionError on a deeply nested response. The writer's exception handling leaves that error uncaught. A synthetic 20 KB response reproduced the exception escaping the writer on the project's Python 3.12 runtime. The CLI cannot finish writing a new run after this malformed provider response.
**Suggested fix:** Handle decoding recursion errors at the response boundary and route them through the existing sanitized fallback. Verify a synthetic deeply nested response returns the template.
**Resolution:** Excessive JSON nesting now takes the sanitized fallback path. The independent run passed the mocked provider response regression.

### 6/F-06 [P1] closed - Abbreviated percentage points pass as checked numbers

**File:** engine/src/stock_mover/briefing.py:32
**Found:** 2026-11-21 by /audit (scope: current; lens: quality, tests)
**Why it matters:** The approved spec requires the checker to treat percentage-point expressions as complete numbers. Using the committed seed facts and a fake writer, "Senior approvals rose by 2 pp." and "Senior approvals rose by 2 p.p." were each published with source llm and checked true. The facts supply 2 excluded issues and no percentage-point change. The checker rejects the same sentence with "2 percentage points".
**Suggested fix:** Recognize the spaced English percentage-point abbreviations in the existing suffix pattern and cover the committed-seed example through retry and fallback.
**Resolution:** The fresh review confirmed that both reported spellings are rejected against the committed seed even though the bare count is allowed. A fake writer retried once, named the rejected expression in the retry prompt, and returned the template after the second rejection for both spellings and three other abbreviations. All 36 briefing tests and all 144 engine tests passed. The stored briefing still passes the checker.


## Independent review

# Independent Review

**Status:** passed
**Target commit:** 7e4dae7c0ce1da9e8e1f667253fff001469c116b
**Base commit:** e060bbd45586f75236919a83c81e25356ef2b3e8
**Base ref:** refs/remotes/origin/main
**Spec hash:** a07660a060df67151b3a0470c62ab3468e73b50e59a2d061e4a6958f1c251689
**Prepared by:** codex
**Builder model:** gpt-6.2-sol
**Requested reviewer:** codex
**Requested model:** gpt-6.2-sol
**Requested execution:** automatic
**Requested at:** 2026-11-21T15:16:35.2962608+05:30
**Workflow:** regular
**Check required:** no
**Reviewer adapter:** codex
**Reviewer model:** gpt-6.2-sol
**Reviewer context:** fresh subagent
**Actual execution:** automatic
**Reviewed at:** 2026-11-21T15:18:00.9792805+05:30
**Scope:** current
**Lenses:** quality, security, performance, tests
**Verdict:** passed
**Check result:** not-required

## Commands

- `uv run pytest -q`: pass, 144 engine tests.
- `uv run pytest -q tests/test_briefing.py`: pass, 36 focused tests.
- `uv run python -` with the committed seed and a fake writer: pass, seed validation and five abbreviation retry and fallback cases.
- `git diff --check e060bbd..HEAD`: pass.
- `git check-ignore .env`: pass.
- `git diff --exit-code 91299de HEAD -- apps/web`: pass, web source and seed match the initially verified build.

## Evidence

- Reviewed the complete work-item delta from e060bbd through 7e4dae7, including facts, numeric tokens, retry and fallback, CLI wiring, tests, and the rendered briefing label and seed contract.
- The fixed HTTPS endpoint rejects redirects, the prompt uses a capped list of priority moves and run summary facts, and the request logs omit provider response content. The web page renders briefing text through React and uses the existing run schema.
- Requests have a timeout and at most one retry. The work added to the local engine run is limited to preparing the summary facts, selecting five moves, and checking the provider text.
- The verified spec records passing web lint, standalone typecheck and production build and local browser evidence at 1440 px and 390 px. The complete web tree matches that verification checkpoint.
- The stored briefing parses as a checked LLM briefing and its numbers pass the current checker.

## Findings

- F-06 closed after focused independent verification. No new findings.

## Remaining risk

- Reused the recorded web build and local browser evidence. This pass used a fake writer for provider verification.

## Try it now

Open the saved run in apps/web/data/seed-run.json. Its briefing.source is llm and briefing.checked is true. These fields drive the **AI-written, numbers checked** label.
