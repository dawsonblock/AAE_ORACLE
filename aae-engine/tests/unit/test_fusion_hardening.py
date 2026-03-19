"""Tests for new fusion-hardening modules:

- ExperimentStore (SQLite persistence)
- RankingStore (SQLite persistence)
- ExperimentEvaluator (multi-signal scoring)
- CandidateRanker (confidence + prior blending)
- StructuredEventLogger (JSONL logging)
- ReplayEngine (history retrieval)
- RejectionTelemetry (metrics tracking)
- ContractVersion (versioned requests)
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from aae.storage.experiment_store import ExperimentStore
from aae.storage.ranking_store import RankingStore
from aae.analysis.experiment_evaluator import ExperimentEvaluator
from aae.analysis.structured_logger import StructuredEventLogger, generate_trace_id
from aae.analysis.replay import ReplayEngine
from aae.planning.ranker import CandidateRanker
from aae.oracle_bridge.contracts import ContractVersion, OraclePlanRequest
from aae.oracle_bridge.result_service import RejectionTelemetry


# ── ExperimentStore ──

class TestExperimentStore:

    def test_log_and_retrieve(self):
        store = ExperimentStore(db=":memory:")
        eid = store.log(goal="fix-bug", candidate_id="c1", result="success", score=0.85)
        assert eid  # non-empty UUID
        history = store.get_history("fix-bug")
        assert len(history) == 1
        assert history[0]["candidate_id"] == "c1"
        assert history[0]["score"] == 0.85

    def test_multiple_goals(self):
        store = ExperimentStore(db=":memory:")
        store.log(goal="g1", candidate_id="c1", result="success", score=0.9)
        store.log(goal="g2", candidate_id="c2", result="failure", score=0.2)
        store.log(goal="g1", candidate_id="c3", result="partial", score=0.5)
        assert len(store.get_history("g1")) == 2
        assert len(store.get_history("g2")) == 1

    def test_get_by_candidate(self):
        store = ExperimentStore(db=":memory:")
        store.log(goal="g1", candidate_id="c1", result="success", score=0.9)
        store.log(goal="g2", candidate_id="c1", result="failure", score=0.3)
        results = store.get_by_candidate("c1")
        assert len(results) == 2

    def test_get_by_trace(self):
        store = ExperimentStore(db=":memory:")
        store.log(goal="g1", candidate_id="c1", result="success", score=0.9, trace_id="trace-1")
        store.log(goal="g2", candidate_id="c2", result="failure", score=0.3, trace_id="trace-1")
        store.log(goal="g3", candidate_id="c3", result="success", score=0.8, trace_id="trace-2")
        assert len(store.get_by_trace("trace-1")) == 2
        assert len(store.get_by_trace("trace-2")) == 1

    def test_get_all(self):
        store = ExperimentStore(db=":memory:")
        for i in range(5):
            store.log(goal=f"g{i}", candidate_id=f"c{i}", result="success", score=0.5 + i * 0.1)
        all_results = store.get_all(limit=3)
        assert len(all_results) == 3


# ── RankingStore ──

class TestRankingStore:

    def test_update_and_get(self):
        store = RankingStore(db=":memory:")
        score = store.update("c1", "g1", 0.5)
        assert score == 0.5
        assert store.get_score("c1", "g1") == 0.5

    def test_cumulative_updates(self):
        store = RankingStore(db=":memory:")
        store.update("c1", "g1", 0.5)
        store.update("c1", "g1", 0.3)
        assert store.get_score("c1", "g1") == pytest.approx(0.8)

    def test_get_rankings(self):
        store = RankingStore(db=":memory:")
        store.update("c1", "g1", 0.9)
        store.update("c2", "g1", 0.3)
        store.update("c3", "g1", 0.7)
        rankings = store.get_rankings("g1")
        assert rankings[0]["candidate_id"] == "c1"  # highest
        assert rankings[-1]["candidate_id"] == "c2"  # lowest

    def test_missing_candidate_returns_zero(self):
        store = RankingStore(db=":memory:")
        assert store.get_score("nonexistent", "g1") == 0.0

    def test_update_legacy_delta_accepted(self):
        store = RankingStore(db=":memory:")
        score = store.update("c1", 0.4, True)
        assert score == pytest.approx(0.4)
        data = store.get("c1")
        assert data["accept_count"] == 1
        assert data["reject_count"] == 0

    def test_update_too_few_args_raises(self):
        store = RankingStore(db=":memory:")
        with pytest.raises(TypeError, match="update\\(\\) requires either"):
            store.update("c1", 0.5)

    def test_update_no_args_raises(self):
        store = RankingStore(db=":memory:")
        with pytest.raises(TypeError, match="update\\(\\) requires either"):
            store.update("c1")

    def test_update_too_many_args_raises(self):
        store = RankingStore(db=":memory:")
        with pytest.raises(TypeError, match="update\\(\\) requires either"):
            store.update("c1", "g1", 0.5, "extra")


# ── ExperimentEvaluator ──

class TestExperimentEvaluator:

    def test_full_success(self):
        evaluator = ExperimentEvaluator()
        result = evaluator.evaluate("fix-bug", {
            "status": "success",
            "artifacts": ["a", "b", "c", "d", "e"],
            "latency_ms": 100,
            "tests_passed": 10,
            "tests_total": 10,
        })
        assert result["score"] > 0.8
        assert result["metrics"]["success"] == 1.0
        assert result["metrics"]["test_pass_rate"] == 1.0

    def test_failure(self):
        evaluator = ExperimentEvaluator()
        result = evaluator.evaluate("fix-bug", {
            "status": "failure",
            "exception": "RuntimeError",
            "latency_ms": 3000,
        })
        assert result["score"] < 0.5
        assert result["metrics"]["success"] == 0.0
        assert result["metrics"]["no_exceptions"] == 0.0

    def test_safety_violations(self):
        evaluator = ExperimentEvaluator()
        result = evaluator.evaluate("fix-bug", {
            "status": "success",
            "safety_violations": [{"type": "file_access"}],
        })
        assert result["metrics"]["safety_score"] == 0.0


# ── StructuredEventLogger ──

class TestStructuredEventLogger:

    def test_log_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.jsonl")
            logger = StructuredEventLogger(path=path)
            logger.log({"stage": "test", "goal_id": "g1"})
            assert os.path.exists(path)
            with open(path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            record = json.loads(lines[0])
            assert record["stage"] == "test"
            assert "timestamp" in record

    def test_log_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "events.jsonl")
            logger = StructuredEventLogger(path=path)
            logger.log_plan(goal_id="g1", trace_id="t1", candidate_count=3, latency_ms=42.5)
            with open(path) as f:
                record = json.loads(f.readline())
            assert record["stage"] == "plan"
            assert record["candidate_count"] == 3


# ── generate_trace_id ──

def test_generate_trace_id():
    tid = generate_trace_id()
    assert len(tid) == 36  # UUID format


# ── CandidateRanker ──

class TestCandidateRanker:

    def test_rank_by_confidence(self):
        store = RankingStore(db=":memory:")
        ranker = CandidateRanker(ranking_store=store)

        class FakeCandidate:
            def __init__(self, cid, conf):
                self.candidate_id = cid
                self.confidence = conf

        candidates = [
            FakeCandidate("c1", 0.5),
            FakeCandidate("c2", 0.9),
            FakeCandidate("c3", 0.7),
        ]
        ranked = ranker.rank(candidates, goal_id="g1")
        assert ranked[0].candidate_id == "c2"  # highest confidence

    def test_prior_affects_ranking(self):
        store = RankingStore(db=":memory:")
        store.update("c1", "g1", 5.0)  # strong prior
        ranker = CandidateRanker(ranking_store=store)

        class FakeCandidate:
            def __init__(self, cid, conf):
                self.candidate_id = cid
                self.confidence = conf

        candidates = [
            FakeCandidate("c1", 0.5),  # lower confidence but strong prior
            FakeCandidate("c2", 0.9),  # higher confidence but no prior
        ]
        ranked = ranker.rank(candidates, goal_id="g1")
        assert ranked[0].candidate_id == "c1"  # prior boosts it


# ── ReplayEngine ──

class TestReplayEngine:

    def test_get_goal_history(self):
        store = ExperimentStore(db=":memory:")
        store.log(goal="g1", candidate_id="c1", result="success", score=0.9)
        engine = ReplayEngine(experiment_store=store)
        history = engine.get_goal_history("g1")
        assert len(history) == 1

    def test_get_recent(self):
        store = ExperimentStore(db=":memory:")
        for i in range(5):
            store.log(goal=f"g{i}", candidate_id=f"c{i}", result="success", score=0.5)
        engine = ReplayEngine(experiment_store=store)
        recent = engine.get_recent(limit=3)
        assert len(recent) == 3


# ── RejectionTelemetry ──

class TestRejectionTelemetry:

    def test_record_and_stats(self):
        t = RejectionTelemetry()
        t.record_acceptance()
        t.record_acceptance()
        t.record_rejection("low_score")
        t.record_rejection("invalid_type")
        t.record_rejection("low_score")
        stats = t.get_stats()
        assert stats["accepted"] == 2
        assert stats["rejected"] == 3
        assert stats["total"] == 5
        assert stats["rejection_reasons"]["low_score"] == 2


# ── ContractVersion ──

class TestContractVersion:

    def test_v1_value(self):
        assert ContractVersion.V1.value == "v1"

    def test_request_default_version(self):
        req = OraclePlanRequest(objective="fix bug")
        assert req.version == "v1"

    def test_request_with_trace_id(self):
        req = OraclePlanRequest(objective="fix bug", trace_id="abc-123")
        assert req.trace_id == "abc-123"
