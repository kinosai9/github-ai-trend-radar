import json

from github_ai_trend_radar.llm.errors import LLMResult
from github_ai_trend_radar.main import main
from github_ai_trend_radar.processors.llm_ranker import (
    adjusted_score,
    apply_llm_success,
    enrich_with_llm,
    extract_json_object,
    select_llm_candidates,
)
from github_ai_trend_radar.storage.files import save_json, snapshot_path


CONFIG = {"llm": {"default_model": "test-model", "max_readme_chars": 8000}}


def candidate(name: str, bucket: str, score: float = 0.7):
    return {
        "repo_full_name": name,
        "html_url": f"https://github.com/{name}",
        "description": "AI agent framework",
        "source_hits": ["ossinsight"],
        "matched_focus_topics": ["ai_agent"],
        "matched_keywords": ["ai agent"],
        "topic_match_confidence": "strong",
        "radar_bucket": bucket,
        "trend_score": score,
        "value_score": score,
        "radar_score": score,
        "final_score": score,
        "scores": {"topic_relevance_score": 0.8},
        "noise": {"is_noise": False, "penalty": 0},
        "recommended_action_rule_based": "read",
        "metrics": {"stars": 100, "forks": 10},
        "metadata": {"topics": ["ai-agents"], "license": "MIT", "default_branch": "main"},
        "readme_excerpt": "quickstart " * 20,
    }


def llm_payload(**overrides):
    payload = {
        "llm_is_relevant": True,
        "llm_is_noise": False,
        "llm_noise_reason": "",
        "llm_primary_topic": "ai_agent",
        "llm_secondary_topics": [],
        "llm_topic_match_confidence": "strong",
        "llm_project_type": "framework",
        "llm_maturity": "usable",
        "llm_trend_judgement": "breakout",
        "llm_novelty_score": 0.8,
        "llm_business_fit_score": 0.8,
        "llm_technical_value_score": 0.8,
        "llm_risk_score": 0.1,
        "core_idea": "agent framework",
        "technical_value": "useful",
        "why_it_matters": "trend",
        "enterprise_fit": "self hosted",
        "risks": [],
        "recommended_action_llm": "deep_research",
        "summary_for_report": "summary",
    }
    payload.update(overrides)
    return payload


class FakeClient:
    available = True
    model = "fake-model"

    def __init__(self, responses):
        self.responses = list(responses)

    def chat_json(self, *, system_prompt, user_payload):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(ok=True, content=item, raw={"raw": True}, provider="fake", model=self.model)


def test_select_llm_candidates_by_bucket_layers():
    candidates = [
        candidate("o/b1", "breakout"),
        candidate("o/b2", "breakout"),
        candidate("o/m1", "valuable_mature"),
        candidate("o/w1", "watchlist"),
    ]

    selected = select_llm_candidates(candidates, llm_top_n=3, breakout_n=1, mature_n=1, watchlist_n=1)

    assert [item["repo_full_name"] for item in selected] == ["o/b1", "o/m1", "o/w1"]


def test_json_fence_is_parsed():
    parsed = extract_json_object('```json\n{"llm_is_noise": false}\n```')

    assert parsed == {"llm_is_noise": False}


def test_parse_failed_does_not_block_other_candidates():
    scored = {"period": "daily", "stats": {}, "candidates": [candidate("o/a", "breakout"), candidate("o/b", "breakout")]}
    client = FakeClient(["not json", json.dumps(llm_payload())])

    payload = enrich_with_llm(scored, client=client, scoring_config=CONFIG, source_snapshot="scored.json", llm_top_n=2)

    statuses = [item["llm_status"] for item in payload["candidates"]]
    assert "parse_failed" in statuses
    assert "ok" in statuses
    assert payload["llm"]["parse_failed_count"] == 1
    assert payload["llm"]["ok_count"] == 1


def test_api_failed_does_not_block_snapshot():
    scored = {"period": "daily", "stats": {}, "candidates": [candidate("o/a", "breakout")]}
    client = FakeClient([RuntimeError("boom")])

    payload = enrich_with_llm(scored, client=client, scoring_config=CONFIG, source_snapshot="scored.json", llm_top_n=1)

    assert payload["candidates"][0]["llm_status"] == "api_failed"
    assert payload["llm"]["api_failed_count"] == 1


def test_llm_noise_lowers_adjusted_score():
    base = candidate("o/a", "breakout", score=0.8)
    clean = adjusted_score(base, llm_payload())
    noisy = adjusted_score(base, llm_payload(llm_is_noise=True))

    assert noisy < clean


def test_weak_llm_topic_match_lowers_adjusted_score():
    base = candidate("o/a", "breakout", score=0.8)
    strong = adjusted_score(base, llm_payload(llm_topic_match_confidence="strong"))
    weak = adjusted_score(base, llm_payload(llm_topic_match_confidence="weak"))

    assert weak < strong


def test_unselected_candidate_is_skipped():
    scored = {
        "period": "daily",
        "stats": {},
        "candidates": [candidate("o/a", "breakout"), candidate("o/b", "watchlist")],
    }
    client = FakeClient([json.dumps(llm_payload())])

    payload = enrich_with_llm(scored, client=client, scoring_config=CONFIG, source_snapshot="scored.json", llm_top_n=1)

    assert any(item["llm_status"] == "skipped" for item in payload["candidates"])


def test_llm_adjusted_score_is_clamped():
    scored = apply_llm_success(candidate("o/a", "breakout", score=1.0), llm_payload(llm_risk_score=-5), raw_response="{}")

    assert 0.0 <= scored["llm_adjusted_score"] <= 1.0


def test_recommended_action_llm_updates_final_action():
    scored = apply_llm_success(
        candidate("o/a", "breakout", score=0.8),
        llm_payload(recommended_action_llm="ignore"),
        raw_response="{}",
    )

    assert scored["final_recommended_action"] == "ignore"


def test_score_use_llm_without_key_writes_llm_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    candidates_path = snapshot_path(tmp_path, "daily", "candidates")
    save_json(
        {
            "period": "daily",
            "generated_at": "2026-05-20T00:00:00+00:00",
            "sources": {},
            "candidates": [candidate("o/a", "breakout")],
        },
        candidates_path,
    )

    exit_code = main(["score", "--period", "daily", "--snapshot-dir", str(tmp_path), "--use-llm", "--llm-top-n", "1"])

    assert exit_code == 0
    payload = json.loads(snapshot_path(tmp_path, "daily", "llm-scored").read_text(encoding="utf-8"))
    assert payload["llm"]["enabled"] is False
    assert payload["candidates"][0]["llm_status"] == "skipped"
