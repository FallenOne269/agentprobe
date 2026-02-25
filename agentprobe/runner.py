import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from .backends.base import AgentBackend
from .backends.mock import MockBackend
from .evaluator import Evaluator, EvaluationResult
from .hooks import HookEvent, HookRegistry
from .scenarios import Scenario


@dataclass
class RunResult:
    model: str
    timestamp: str
    scenario_results: list[EvaluationResult]
    summary: dict[str, Any] = field(default_factory=dict)


class Runner:
    """
    Orchestrates scenario execution, evaluation, and baseline management.

    Args:
        backend:       LLM backend to generate responses (default: MockBackend).
        evaluator:     Evaluator instance (default: Evaluator()).
        baseline_path: Path to a baseline JSON for drift detection.
        hooks:         HookRegistry for observability callbacks.
    """

    def __init__(
        self,
        backend: AgentBackend | None = None,
        evaluator: Evaluator | None = None,
        baseline_path: Path | str | None = None,
        hooks: HookRegistry | None = None,
    ):
        self.backend = backend or MockBackend()
        self.evaluator = evaluator or Evaluator()
        self.baseline_path = Path(baseline_path) if baseline_path else None
        self._baseline: dict | None = None
        self.hooks = hooks or HookRegistry()

    @property
    def baseline(self) -> dict | None:
        if self._baseline is None and self.baseline_path and self.baseline_path.exists():
            with open(self.baseline_path) as f:
                self._baseline = json.load(f)
        return self._baseline

    def run_scenario(self, scenario: Scenario) -> EvaluationResult:
        self.hooks.emit(HookEvent.SCENARIO_START, scenario=scenario)

        output = self.backend.generate(scenario.input, max_tokens=scenario.max_tokens)
        previous = None
        if self.baseline:
            previous = self.baseline.get("scenarios", {}).get(scenario.name)
        result = self.evaluator.evaluate(scenario, output, previous)

        self.hooks.emit(HookEvent.SCENARIO_END, scenario=scenario, result=result)
        return result

    def run_directory(self, directory: Path | str, tag: str | None = None) -> RunResult:
        directory = Path(directory)
        scenarios = Scenario.load_directory(directory, tag=tag)
        if not scenarios:
            msg = f"No .yaml scenarios found in {directory}"
            if tag:
                msg += f" with tag '{tag}'"
            raise ValueError(msg)

        self.hooks.emit(HookEvent.RUN_START, directory=str(directory), tag=tag)

        results = [self.run_scenario(s) for s in scenarios]

        passed = sum(1 for r in results if r.passed)
        run_result = RunResult(
            model=getattr(self.backend, "model", "mock"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            scenario_results=results,
            summary={
                "total": len(results),
                "passed": passed,
                "failed": len(results) - passed,
                "pass_rate": passed / len(results),
            },
        )

        self.hooks.emit(HookEvent.RUN_END, run_result=run_result)
        return run_result

    def save_baseline(self, result: RunResult, path: Path | str) -> None:
        path = Path(path)
        data = {
            "model": result.model,
            "created_at": result.timestamp,
            "scenarios": {
                r.scenario_name: {
                    "raw_output": r.raw_output,
                    "metrics": r.metrics,
                    "passed": r.passed,
                }
                for r in result.scenario_results
            },
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Baseline saved → {path}")
