"""The compliance eval runner (evals/compliance_eval.py): resuming, summaries, and the cost
estimate before a batch. No API calls."""

import json

from agent import costs
from evals import compliance_eval
from evals.graders.compliance import load_compliance_cases, reference_review


def review(case, error=None) -> dict:
    return {**reference_review(case), "claim_id": case.claim_id, "variant": "v1",
            "error": error, "cost_usd": 0.07, "seconds": None, "batch_ids": ["b-1"],
            "validation": []}


def test_resume_runs_only_missing_or_errored_reviews_and_summarises_the_whole_folder(tmp_path):
    cases = load_compliance_cases("dev")[:3]
    (tmp_path / "reviews").mkdir()
    compliance_eval._save(tmp_path, cases[0], 1, review(cases[0]), set())
    compliance_eval._save(tmp_path, cases[1], 1, review(cases[1], "APIError: down"), set())
    todo = compliance_eval.to_do(cases, 1, tmp_path, "v1")
    assert [c.claim_id for _, c in todo] == [cases[1].claim_id, cases[2].claim_id]
    summary = compliance_eval.write_summary(tmp_path, "v1", "dev")
    assert summary["runs"][0]["claims"] == 2 and summary["runs"][0]["errors"] == 1
    assert summary["batch"] and summary["seconds_per_claim"] is None
    assert "Batch API, half price" in (tmp_path / "summary.md").read_text()


def test_a_batch_is_estimated_before_it_is_sent(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "LEDGER", tmp_path / "spend.jsonl")
    monkeypatch.delenv("SPEND_LIMIT_USD", raising=False)
    monkeypatch.setattr(compliance_eval, "_policy_library", lambda kb: None)
    monkeypatch.setattr(compliance_eval, "known_clauses", lambda kb: set())
    sent = []

    def fake_batch(claim_ids, library, client, config, variant, run_ids):
        sent.append(claim_ids)
        cases = {c.claim_id: c for c in load_compliance_cases("all")}
        return [review(cases[c]) for c in claim_ids]

    monkeypatch.setattr(compliance_eval, "review_claims_batch", fake_batch)
    todo = [(1, c) for c in load_compliance_cases("dev")]  # 18 x $0.14 / 2 = $1.26
    (tmp_path / "reviews").mkdir()
    compliance_eval.run_batched(todo, "v1", 1.00, tmp_path, None, None, tmp_path)
    assert sent == []  # over --max-cost: nothing sent
    costs.record_spend({"cost_usd": 31.0})  # near the ledger's US$32 limit
    compliance_eval.run_batched(todo, "v1", 5.00, tmp_path, None, None, tmp_path)
    assert sent == []
    (tmp_path / "spend.jsonl").unlink()
    compliance_eval.run_batched(todo, "v1", 5.00, tmp_path, None, None, tmp_path)
    assert len(sent) == 1 and len(sent[0]) == 18
    assert len(list((tmp_path / "reviews").glob("*.json"))) == 18
    assert json.loads(next((tmp_path / "reviews").glob("*.json")).read_text())["grade"]
