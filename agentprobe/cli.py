import sys
import json
from pathlib import Path

import click

from .runner import Runner
from .backends.mock import MockBackend
from .backends.anthropic import AnthropicBackend
from .evaluator import Evaluator


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """agentprobe — Agent regression testing for production LLM systems."""
    pass


@cli.command()
@click.argument("scenarios_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--backend", type=click.Choice(["mock", "anthropic"]), default="mock",
              show_default=True, help="Backend to use")
@click.option("--model", default="claude-opus-4-6", show_default=True,
              help="Model ID (anthropic backend only)")
@click.option("--baseline", type=click.Path(dir_okay=False),
              help="Baseline JSON for drift detection")
@click.option("-o", "--output", type=click.Path(),
              help="Write results JSON to file")
@click.option("--save-baseline", type=click.Path(),
              help="Save this run as new baseline")
@click.option("--tolerance", default=1.0, show_default=True, type=float,
              help="Pass threshold 0.0–1.0")
def run(scenarios_dir, backend, model, baseline, output, save_baseline, tolerance):
    """Run all .yaml scenarios in SCENARIOS_DIR against the chosen backend."""

    # ── backend ──────────────────────────────────────────────────────────
    if backend == "mock":
        be = MockBackend()
    else:
        try:
            be = AnthropicBackend(model=model)
        except (ValueError, ImportError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    # ── runner ───────────────────────────────────────────────────────────
    runner = Runner(
        backend=be,
        evaluator=Evaluator(tolerance=tolerance),
        baseline_path=baseline,
    )

    try:
        results = runner.run_directory(scenarios_dir)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # ── display ──────────────────────────────────────────────────────────
    click.echo(f"\nModel : {results.model}")
    click.echo(f"Time  : {results.timestamp}")
    click.echo("─" * 48)

    for r in results.scenario_results:
        icon = click.style("✓ PASS", fg="green") if r.passed else click.style("✗ FAIL", fg="red")
        click.echo(f"  {icon}  {r.scenario_name}")
        for err in r.errors:
            click.echo(f"        {err}")

    click.echo("─" * 48)
    s = results.summary
    rate_str = f"{s['pass_rate']:.0%}"
    click.echo(f"  {s['passed']}/{s['total']} passed  ({rate_str})\n")

    # ── optional output ───────────────────────────────────────────────────
    if output:
        payload = {
            "model": results.model,
            "timestamp": results.timestamp,
            "summary": results.summary,
            "results": [
                {
                    "scenario": r.scenario_name,
                    "passed": r.passed,
                    "contains_score": r.contains_score,
                    "metrics": r.metrics,
                    "errors": r.errors,
                }
                for r in results.scenario_results
            ],
        }
        Path(output).write_text(json.dumps(payload, indent=2))
        click.echo(f"Results written → {output}")

    if save_baseline:
        runner.save_baseline(results, save_baseline)

    sys.exit(0 if s["failed"] == 0 else 1)


@cli.command("init-scenario")
@click.argument("name")
@click.argument("output", type=click.Path())
def init_scenario(name, output):
    """Scaffold a new scenario YAML file."""
    template = f"""name: {name}
input: |
  Your prompt here. Be specific about what the agent should do.
expected_contains:
  - keyword_one
  - keyword_two
max_tokens: 512
metadata:
  category: smoke
  priority: high
"""
    Path(output).write_text(template)
    click.echo(f"Scenario created → {output}")


def main():
    cli()


if __name__ == "__main__":
    main()
