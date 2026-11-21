import io
import json
from email.message import Message
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, build_opener
from urllib.response import addinfourl

import pytest

from stock_mover.briefing import TOP_MOVE_LIMIT, build_facts, check_numbers, configured_sarvam, write_briefing
from stock_mover.constants import SEED_RUN_PATH
from stock_mover.contract import Briefing, Run
from stock_mover.run import run_text

FALLBACK = Briefing(text="Template summary.", source="template", checked=True)
VALID_TEXT = "Review 1916 stock moves today."


@pytest.fixture
def facts():
    seed = Run.model_validate_json(SEED_RUN_PATH.read_text(encoding="utf-8"))
    return build_facts(seed)


def test_facts_use_only_run_summary_and_capped_priority_moves(facts):
    assert set(facts) == {
        "data_as_of", "totals", "top_moves", "data_issues", "rules", "under_stocked_stores",
    }
    assert len(facts["top_moves"]) == TOP_MOVE_LIMIT
    assert facts["top_moves"][0]["id"] == "w2s-LKO-01-KUR-04-XL"
    assert set(facts["top_moves"][0]) == {
        "id", "sku_id", "style_id", "style_name", "from", "to", "units", "reason",
    }
    assert facts["totals"]["moves"] == 1916
    assert facts["rules"] == {"passed": 10, "total": 10}


def test_matching_numbers_allow_grouping_decimals_signed_values_and_identifiers(facts):
    assert check_numbers(
        "On 31 Oct 2026, LKO-01 gets 45 units of KUR-04-XL, style KUR-04. "
        "Totals: Rs 2,72,58,196 (27,258,196 or 27258196). "
        "Cover was 0.00, sales were 1.50 per day and a separate issue showed -4.",
        facts,
    ) == []


def test_rejects_invented_counts_percentages_dates_and_codes(facts):
    assert check_numbers(
        "2017 moves, 45%more, 2026-10-30, LKO-09, KUR-01 and 1-LKO-01.",
        facts,
    ) == ["2017", "45%", "2026-10-30", "LKO-09", "KUR-01", "1-LKO-01"]


def test_rejects_compound_numbers_even_when_components_are_allowed(facts):
    assert check_numbers("1 and 2", facts) == []
    assert check_numbers("1/2, 2:1, 1 ⁄ 2, 1\n/ 2, 2 ∶\n1, and ½.", facts) == [
        "1/2", "2:1", "1 ⁄ 2", "1\n/ 2", "2 ∶\n1", "½",
    ]


@pytest.mark.parametrize("number", [
    "2 percent", "2 PER CENT", "2 per-cent", "2\npct", "2％", "2 ٪",
    "٪2", "% 2", "﹪2", "2 percentage points", "2 pct pts", "2 pp.", "2 p.p.",
    "2 ppts", "2 basis points", "2 bps", "2 b.p.",
])
def test_rejects_percentage_formats_even_when_the_count_is_allowed(facts, number):
    assert check_numbers("2 issues", facts) == []
    assert check_numbers(f"Senior approval is required for {number} of moves.", facts) == [number]


def test_compares_unicode_minus_and_fractional_decimals_by_value(facts):
    assert check_numbers("Snapshot balance was −4.", facts) == []
    assert check_numbers("An unlisted rate was .2.", facts) == [".2"]


@pytest.mark.parametrize("replies", [[VALID_TEXT], ["2017 moves.", VALID_TEXT]])
def test_writer_accepts_checked_text_and_names_rejected_numbers_on_retry(facts, replies):
    llm = Mock(side_effect=replies)
    assert write_briefing(facts, llm, FALLBACK) == Briefing(text=VALID_TEXT, source="llm", checked=True)
    assert llm.call_count == len(replies)
    assert json.loads(llm.call_args_list[0].args[1]) == facts
    if len(replies) == 2:
        assert "2017" in llm.call_args.args[1]


def test_writer_falls_back_after_two_number_failures(facts):
    llm = Mock(return_value="2017 moves.")
    assert write_briefing(facts, llm, FALLBACK) == FALLBACK
    assert llm.call_count == 2


@pytest.mark.parametrize("error", [OSError("fake-key"), TimeoutError("fake-key"), ValueError("fake-key")])
def test_writer_falls_back_on_request_failure_without_logging_details(facts, capsys, error):
    llm = Mock(side_effect=error)
    result = write_briefing(facts, llm, FALLBACK)
    assert result == FALLBACK
    assert llm.call_count == 1
    assert "fake-key" not in capsys.readouterr().err + result.model_dump_json()


@pytest.mark.parametrize("content", ["", " \n", None])
def test_writer_falls_back_on_empty_or_invalid_text(facts, content):
    llm = Mock(return_value=content)
    assert write_briefing(facts, llm, FALLBACK) == FALLBACK
    assert llm.call_count == 1


def test_malformed_unicode_falls_back_to_a_serializable_run(facts):
    run = Run.model_validate_json(SEED_RUN_PATH.read_bytes())
    llm = Mock(return_value="Review 1916 moves \ud800")
    run.briefing = write_briefing(facts, llm, FALLBACK)
    assert json.loads(run_text(run))["briefing"] == FALLBACK.model_dump()
    assert llm.call_count == 1


def test_missing_key_skips_network(facts, monkeypatch, tmp_path):
    monkeypatch.setattr("stock_mover.briefing.REPO_ROOT", tmp_path)
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    monkeypatch.setenv("SARVAM_MODEL", "sarvam-105b")
    make_opener = Mock()
    monkeypatch.setattr("stock_mover.briefing.build_opener", make_opener)
    assert write_briefing(facts, configured_sarvam(), FALLBACK) == FALLBACK
    make_opener.assert_not_called()


def test_environment_overrides_local_key_and_auth_failure_does_not_echo_it(facts, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("stock_mover.briefing.REPO_ROOT", tmp_path)
    (tmp_path / ".env").write_text("SARVAM_API_KEY=local-key\nSARVAM_MODEL=sarvam-105b\n", encoding="utf-8")
    monkeypatch.setenv("SARVAM_API_KEY", "fake-key")
    monkeypatch.delenv("SARVAM_MODEL", raising=False)
    network = Mock(side_effect=HTTPError("", 401, "fake-key", {}, io.BytesIO(b"fake-key")))
    monkeypatch.setattr("stock_mover.briefing.build_opener", Mock(return_value=Mock(open=network)))
    result = write_briefing(facts, configured_sarvam(), FALLBACK)
    assert result == FALLBACK
    request = network.call_args.args[0]
    assert request.get_header("Api-subscription-key") == "fake-key"
    assert json.loads(request.data)["model"] == "sarvam-105b"
    assert "fake-key" not in capsys.readouterr().err + result.model_dump_json()


def test_redirect_does_not_send_a_second_request(facts, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("stock_mover.briefing.REPO_ROOT", tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "fake-key")
    monkeypatch.setenv("SARVAM_MODEL", "sarvam-105b")
    headers = Message()
    headers["Location"] = "https://other.example/redirect"
    response = addinfourl(io.BytesIO(b""), headers, "https://api.sarvam.ai/v1/chat/completions", 302)
    response.msg = "Found"
    transport = HTTPSHandler()
    transport.https_open = Mock(return_value=response)
    monkeypatch.setattr(
        "stock_mover.briefing.build_opener", lambda redirect_handler: build_opener(redirect_handler, transport),
    )
    assert write_briefing(facts, configured_sarvam(), FALLBACK) == FALLBACK
    transport.https_open.assert_called_once()
    request = transport.https_open.call_args.args[0]
    assert request.full_url == "https://api.sarvam.ai/v1/chat/completions"
    assert request.get_header("Api-subscription-key") == "fake-key"
    assert "Sarvam HTTP 302" in capsys.readouterr().err


def test_deeply_nested_provider_json_returns_template(facts, monkeypatch, tmp_path):
    monkeypatch.setattr("stock_mover.briefing.REPO_ROOT", tmp_path)
    monkeypatch.setenv("SARVAM_API_KEY", "fake-key")
    monkeypatch.setenv("SARVAM_MODEL", "sarvam-105b")
    response = io.BytesIO(b"[" * 10_000 + b"0" + b"]" * 10_000)
    network = Mock(return_value=response)
    monkeypatch.setattr("stock_mover.briefing.build_opener", Mock(return_value=Mock(open=network)))
    assert write_briefing(facts, configured_sarvam(), FALLBACK) == FALLBACK
    network.assert_called_once()
