"""Tests for Runner — directory execution, baseline save/load."""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from agentprobe.backends.mock import MockBackend
from agentprobe.runner import Runner
from agentprobe.scenarios import Scenario


def write_scenario(directory: Path, name: str, expected_contains=None, tags=None) -> Path:
    data = {
        "name": name,
        "input": f"Test prompt for {name}",
        "expected_contains": expected_contains or [],
        "max_tokens": 128,
        "tags": tags or [],
        "metadata": {},
    }
    p = directory / f"{name}.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestRunnerBasics:
    def test_run_single_scenario(self, tmp_path):
        write_scenario(tmp_path, "smoke")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.summary["total"] == 1

    def test_run_multiple_scenarios(self, tmp_path):
        write_scenario(tmp_path, "s1")
        write_scenario(tmp_path, "s2")
        write_scenario(tmp_path, "s3")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.summary["total"] == 3

    def test_empty_directory_raises(self, tmp_path):
        runner = Runner(backend=MockBackend())
        with pytest.raises(ValueError, match="No .yaml scenarios"):
            runner.run_directory(tmp_path)

    def test_pass_rate_calculation(self, tmp_path):
        # No expected_contains → all pass
        for i in range(4):
            write_scenario(tmp_path, f"s{i}")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.summary["pass_rate"] == 1.0
        assert result.summary["failed"] == 0

    def test_failing_scenario(self, tmp_path):
        # Mock output never contains "IMPOSSIBLE_TERM_XYZ"
        write_scenario(tmp_path, "fail_case", expected_contains=["IMPOSSIBLE_TERM_XYZ"])
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.summary["failed"] == 1
        assert not result.scenario_results[0].passed

    def test_model_name_in_result(self, tmp_path):
        write_scenario(tmp_path, "s1")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.model == "mock"

    def test_timestamp_present(self, tmp_path):
        write_scenario(tmp_path, "s1")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.timestamp  # non-empty ISO string


class TestBaseline:
    def test_save_and_load_baseline(self, tmp_path):
        write_scenario(tmp_path, "s1")
        baseline_path = tmp_path / "baseline.json"

        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        runner.save_baseline(result, baseline_path)

        assert baseline_path.exists()
        data = json.loads(baseline_path.read_text())
        assert "scenarios" in data
        assert "s1" in data["scenarios"]

    def test_baseline_contains_raw_output(self, tmp_path):
        write_scenario(tmp_path, "s1")
        baseline_path = tmp_path / "baseline.json"

        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        runner.save_baseline(result, baseline_path)

        data = json.loads(baseline_path.read_text())
        assert "raw_output" in data["scenarios"]["s1"]

    def test_runner_loads_baseline(self, tmp_path):
        write_scenario(tmp_path, "s1")
        baseline_path = tmp_path / "baseline.json"

        # First run: save baseline
        r1 = Runner(backend=MockBackend())
        result = r1.run_directory(tmp_path)
        r1.save_baseline(result, baseline_path)

        # Second run: load baseline (mock is deterministic → high similarity)
        r2 = Runner(backend=MockBackend(), baseline_path=baseline_path)
        assert r2.baseline is not None
        assert "s1" in r2.baseline["scenarios"]

    def test_deterministic_mock_no_drift(self, tmp_path):
        """Same MockBackend seed → identical outputs → no drift flagged."""
        write_scenario(tmp_path, "s1")
        baseline_path = tmp_path / "baseline.json"

        runner = Runner(backend=MockBackend(seed="fixed"))
        result = runner.run_directory(tmp_path)
        runner.save_baseline(result, baseline_path)

        runner2 = Runner(backend=MockBackend(seed="fixed"), baseline_path=baseline_path)
        result2 = runner2.run_directory(tmp_path)
        drift = result2.scenario_results[0].metrics.get("drift_score")
        assert drift == 1.0  # deterministic → no drift


class TestTagFiltering:
    def test_tag_filter_runs_matching_only(self, tmp_path):
        write_scenario(tmp_path, "s_smoke", tags=["smoke"])
        write_scenario(tmp_path, "s_regression", tags=["regression"])
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path, tag="smoke")
        assert result.summary["total"] == 1
        assert result.scenario_results[0].scenario_name == "s_smoke"

    def test_tag_filter_no_match_raises(self, tmp_path):
        write_scenario(tmp_path, "s1", tags=["smoke"])
        runner = Runner(backend=MockBackend())
        with pytest.raises(ValueError, match="no_such_tag"):
            runner.run_directory(tmp_path, tag="no_such_tag")

    def test_no_tag_runs_all(self, tmp_path):
        write_scenario(tmp_path, "s1", tags=["smoke"])
        write_scenario(tmp_path, "s2", tags=["regression"])
        write_scenario(tmp_path, "s3")
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path)
        assert result.summary["total"] == 3

    def test_multiple_tags_scenario_matches(self, tmp_path):
        write_scenario(tmp_path, "s_multi", tags=["smoke", "regression"])
        runner = Runner(backend=MockBackend())
        result = runner.run_directory(tmp_path, tag="regression")
        assert result.summary["total"] == 1
