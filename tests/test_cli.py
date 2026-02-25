"""Tests for CLI commands — run and init-scenario."""

import json
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from agentprobe.cli import cli


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def scenario_dir(tmp_path):
    """Temporary directory with one passing scenario (no expected_contains)."""
    data = {
        "name": "smoke",
        "input": "Say hello.",
        "expected_contains": [],
        "max_tokens": 64,
        "metadata": {},
    }
    (tmp_path / "smoke.yaml").write_text(yaml.dump(data))
    return tmp_path


@pytest.fixture()
def failing_scenario_dir(tmp_path):
    """Temporary directory with one scenario that always fails."""
    data = {
        "name": "fail",
        "input": "Say hello.",
        "expected_contains": ["IMPOSSIBLE_TERM_XYZ"],
        "max_tokens": 64,
        "metadata": {},
    }
    (tmp_path / "fail.yaml").write_text(yaml.dump(data))
    return tmp_path


class TestRunCommand:
    def test_run_exits_zero_when_all_pass(self, runner, scenario_dir):
        result = runner.invoke(cli, ["run", str(scenario_dir), "--backend", "mock"])
        assert result.exit_code == 0

    def test_run_exits_one_when_scenario_fails(self, runner, failing_scenario_dir):
        result = runner.invoke(cli, ["run", str(failing_scenario_dir), "--backend", "mock"])
        assert result.exit_code == 1

    def test_run_output_contains_pass_summary(self, runner, scenario_dir):
        result = runner.invoke(cli, ["run", str(scenario_dir), "--backend", "mock"])
        assert "1/1 passed" in result.output

    def test_run_output_contains_fail_marker(self, runner, failing_scenario_dir):
        result = runner.invoke(cli, ["run", str(failing_scenario_dir), "--backend", "mock"])
        assert "FAIL" in result.output

    def test_run_empty_directory_exits_one(self, runner, tmp_path):
        result = runner.invoke(cli, ["run", str(tmp_path), "--backend", "mock"])
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_run_writes_output_json(self, runner, scenario_dir, tmp_path):
        output_file = tmp_path / "results.json"
        result = runner.invoke(
            cli,
            ["run", str(scenario_dir), "--backend", "mock", "-o", str(output_file)],
        )
        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert "results" in data
        assert data["summary"]["total"] == 1

    def test_run_saves_baseline(self, runner, scenario_dir, tmp_path):
        baseline_file = tmp_path / "baseline.json"
        result = runner.invoke(
            cli,
            ["run", str(scenario_dir), "--backend", "mock", "--save-baseline", str(baseline_file)],
        )
        assert result.exit_code == 0
        assert baseline_file.exists()
        data = json.loads(baseline_file.read_text())
        assert "scenarios" in data

    def test_run_with_baseline_no_drift(self, runner, scenario_dir, tmp_path):
        """Running twice with the same mock backend should produce no drift."""
        baseline_file = tmp_path / "baseline.json"
        # First run: save baseline
        runner.invoke(
            cli,
            ["run", str(scenario_dir), "--backend", "mock", "--save-baseline", str(baseline_file)],
        )
        # Second run: load baseline
        result = runner.invoke(
            cli,
            ["run", str(scenario_dir), "--backend", "mock", "--baseline", str(baseline_file)],
        )
        assert result.exit_code == 0


class TestInitScenarioCommand:
    def test_creates_yaml_file(self, runner, tmp_path):
        output = tmp_path / "new_scenario.yaml"
        result = runner.invoke(cli, ["init-scenario", "my_test", str(output)])
        assert result.exit_code == 0
        assert output.exists()

    def test_yaml_contains_scenario_name(self, runner, tmp_path):
        output = tmp_path / "new_scenario.yaml"
        runner.invoke(cli, ["init-scenario", "my_test", str(output)])
        content = output.read_text()
        assert "my_test" in content

    def test_yaml_is_valid(self, runner, tmp_path):
        output = tmp_path / "new_scenario.yaml"
        runner.invoke(cli, ["init-scenario", "valid_scenario", str(output)])
        data = yaml.safe_load(output.read_text())
        assert "name" in data
        assert "input" in data
        assert "expected_contains" in data

    def test_output_confirms_creation(self, runner, tmp_path):
        output = tmp_path / "new_scenario.yaml"
        result = runner.invoke(cli, ["init-scenario", "my_test", str(output)])
        assert "Scenario created" in result.output
