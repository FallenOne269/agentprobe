import sys
import json
from pathlib import Path

import click

from .runner import Runner
from .backends.mock import MockBackend
from .backends.anthropic import AnthropicBackend
from .backends.openai import OpenAIBackend
from .evaluator import Evaluator


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """agentprobe — Agent regression testing for production LLM systems."""
    pass


@cli.command()
@click.argument("scenarios_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--backend", type=click.Choice(["mock", "anthropic", "openai"]), default="mock",
              show_default=True, help="Backend to use")
@click.option("--model", default=None,
              help="Model ID (default: claude-opus-4-6 for anthropic, gpt-4o for openai)")
@click.option("--baseline", type=click.Path(dir_okay=False),
              help="Baseline JSON for drift detection")
@click.option("-o", "--output", type=click.Path(),
              help="Write results JSON to file")
@click.option("--save-baseline", type=click.Path(),
              help="Save this run as new baseline")
@click.option("--tolerance", default=1.0, show_default=True, type=float,
              help="Pass threshold 0.0–1.0")
@click.option("--tag", default=None,
              help="Only run scenarios that include this tag")
def run(scenarios_dir, backend, model, baseline, output, save_baseline, tolerance, tag):
    """Run all .yaml scenarios in SCENARIOS_DIR against the chosen backend."""

    # ── backend ──────────────────────────────────────────────────────────
    if backend == "mock":
        be = MockBackend()
    elif backend == "anthropic":
        try:
            be = AnthropicBackend(model=model or "claude-opus-4-6")
        except (ValueError, ImportError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)
    else:  # openai
        try:
            be = OpenAIBackend(model=model or "gpt-4o")
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
        results = runner.run_directory(scenarios_dir, tag=tag)
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
tags:
  - smoke
metadata:
  category: smoke
  priority: high
"""
    Path(output).write_text(template)
    click.echo(f"Scenario created → {output}")


@cli.command("generate-scenario")
@click.argument("description")
@click.argument("output", type=click.Path())
@click.option(
    "--backend",
    type=click.Choice(["anthropic", "openai"]),
    default="anthropic",
    show_default=True,
    help="LLM backend to use for generation",
)
@click.option("--model", default=None, help="Model ID override")
def generate_scenario(description, output, backend, model):
    """Use an LLM to generate a scenario YAML from a natural language DESCRIPTION.

    Example:

    \b
        agentprobe generate-scenario \\
            "Summarise a legal contract and list the key obligations" \\
            scenarios/legal_summary.yaml
    """
    # ── build backend ─────────────────────────────────────────────────────
    try:
        if backend == "anthropic":
            be = AnthropicBackend(model=model or "claude-opus-4-6")
        else:
            be = OpenAIBackend(model=model or "gpt-4o")
    except (ValueError, ImportError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # ── prompt the LLM ────────────────────────────────────────────────────
    system_block = (
        "You are an expert at writing agentprobe scenario YAML files. "
        "Output ONLY valid YAML — no markdown fences, no prose, no explanation."
    )
    user_block = f"""Create an agentprobe scenario YAML for the following task:

{description}

The YAML MUST contain exactly these top-level keys:
  name            - short snake_case identifier derived from the task
  input           - the detailed prompt to send to the agent (multi-line string)
  expected_contains - list of 4-8 key terms the response must include
  max_tokens      - appropriate integer (256–2048)
  tags            - list of relevant tags (always include "smoke")
  metadata        - mapping with keys: category (smoke|regression) and priority (high|medium|low)
"""

    full_prompt = f"{system_block}\n\n{user_block}"

    click.echo(f"Generating scenario via {backend}…")
    try:
        raw_yaml = be.generate(full_prompt, max_tokens=1024)
    except Exception as e:
        click.echo(f"Generation failed: {e}", err=True)
        sys.exit(1)

    # Strip accidental markdown fences the model might add
    lines = raw_yaml.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    clean_yaml = "\n".join(lines) + "\n"

    Path(output).write_text(clean_yaml)
    click.echo(f"Scenario written → {output}")
    click.echo("Review the file and adjust expected_contains before committing.")


def main():
    cli()


if __name__ == "__main__":
    main()
