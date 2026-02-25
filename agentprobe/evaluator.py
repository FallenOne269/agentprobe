from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    scenario_name: str
    passed: bool
    contains_score: float
    metrics: dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""
    errors: list[str] = field(default_factory=list)


class Evaluator:
    """
    Checks model output against scenario expectations.

    Checks:
      - expected_contains: all listed strings must appear in output
      - drift: Jaccard similarity vs baseline output (when baseline provided)
    """

    def __init__(self, tolerance: float = 1.0):
        self.tolerance = tolerance  # minimum pass threshold

    def evaluate(
        self,
        scenario,
        output: str,
        previous_baseline: dict | None = None,
    ) -> EvaluationResult:
        errors = []

        # ── contains check ────────────────────────────────────
        found, missing = [], []
        for term in scenario.expected_contains:
            (found if term.lower() in output.lower() else missing).append(term)

        n = len(scenario.expected_contains)
        contains_score = len(found) / n if n > 0 else 1.0
        if missing:
            errors.append(f"Missing expected terms: {missing}")

        # ── drift check ───────────────────────────────────────
        drift_score = None
        if previous_baseline and "raw_output" in previous_baseline:
            drift_score = self._jaccard(previous_baseline["raw_output"], output)
            if drift_score < self.tolerance:
                errors.append(
                    f"Drift detected: similarity {drift_score:.2f} < {self.tolerance:.2f}"
                )

        passed = not errors and contains_score >= self.tolerance

        return EvaluationResult(
            scenario_name=scenario.name,
            passed=passed,
            contains_score=contains_score,
            metrics={
                "found_terms": found,
                "missing_terms": missing,
                "drift_score": drift_score,
                "output_length": len(output),
                "prompt_hash": scenario.prompt_hash,
            },
            raw_output=output,
            errors=errors,
        )

    @staticmethod
    def _jaccard(a: str, b: str) -> float:
        w1, w2 = set(a.lower().split()), set(b.lower().split())
        if not w1 or not w2:
            return 0.0
        return len(w1 & w2) / len(w1 | w2)
