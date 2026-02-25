"""Tests for Evaluator — tolerance thresholds and drift detection."""

import pytest
from agentprobe.evaluator import Evaluator
from agentprobe.scenarios import Scenario


def make_scenario(expected_contains=None):
    return Scenario(
        name="test_scenario",
        input="Summarize this contract.",
        expected_contains=expected_contains or ["liability", "termination"],
    )


class TestContainsCheck:
    def test_all_terms_found_passes(self):
        ev = Evaluator()
        s = make_scenario(["liability", "termination"])
        result = ev.evaluate(s, "The liability cap and termination clause apply.")
        assert result.passed
        assert result.contains_score == 1.0
        assert result.errors == []

    def test_missing_term_fails(self):
        ev = Evaluator()
        s = make_scenario(["liability", "termination"])
        result = ev.evaluate(s, "Only liability is mentioned here.")
        assert not result.passed
        assert result.contains_score == 0.5
        assert "termination" in str(result.errors)

    def test_no_expected_terms_passes(self):
        ev = Evaluator()
        s = make_scenario([])
        result = ev.evaluate(s, "Any output at all.")
        assert result.passed
        assert result.contains_score == 1.0

    def test_case_insensitive(self):
        ev = Evaluator()
        s = make_scenario(["LIABILITY"])
        result = ev.evaluate(s, "The liability clause is clear.")
        assert result.passed

    def test_partial_match_always_fails(self):
        """Missing terms always fail — tolerance applies to drift, not contains."""
        ev = Evaluator(tolerance=0.5)
        s = make_scenario(["liability", "termination"])
        result = ev.evaluate(s, "Only liability is mentioned.")
        assert not result.passed
        assert result.contains_score == 0.5
        assert "termination" in str(result.errors)


class TestDriftDetection:
    def test_identical_output_no_drift(self):
        ev = Evaluator(tolerance=0.7)
        s = make_scenario([])
        baseline = {"raw_output": "The liability and termination terms apply here."}
        result = ev.evaluate(s, "The liability and termination terms apply here.", baseline)
        assert result.metrics["drift_score"] == 1.0

    def test_high_drift_fails(self):
        ev = Evaluator(tolerance=0.9)
        s = make_scenario([])
        baseline = {"raw_output": "The liability and termination terms apply here."}
        result = ev.evaluate(s, "Completely different response about apples.", baseline)
        assert result.metrics["drift_score"] < 0.9
        assert not result.passed

    def test_no_baseline_skips_drift(self):
        ev = Evaluator()
        s = make_scenario([])
        result = ev.evaluate(s, "Any output.", None)
        assert result.metrics["drift_score"] is None
