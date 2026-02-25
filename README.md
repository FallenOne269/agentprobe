# agentprobe

**Agent regression testing for production LLM systems.**

Catch prompt regressions, model drift, and behavior changes before they reach production.

---

## Install

```bash
pip install agentprobe
# or with Claude backend:
pip install "agentprobe[anthropic]"
```

---

## 60-Second Demo

```bash
# 1. Create a scenario
agentprobe init-scenario summarize_contract scenarios/summarize_contract.yaml

# 2. Run against mock backend (no API key)
agentprobe run scenarios/

# 3. Save a baseline
agentprobe run scenarios/ --backend anthropic --save-baseline baseline.json

# 4. Detect drift on future runs
agentprobe run scenarios/ --backend anthropic --baseline baseline.json --tolerance 0.8
```

**Output:**

```
Model : claude-opus-4-6
Time  : 2025-02-24T10:00:00+00:00
────────────────────────────────────────────────
  ✓ PASS  summarize_contract
  ✓ PASS  code_review_python
  ✗ FAIL  safety_refusal
          Missing expected terms: ['cannot', 'help']
────────────────────────────────────────────────
  2/3 passed  (67%)
```

---

## Scenarios

Scenarios are YAML files. One file = one test case.

```yaml
# scenarios/summarize_contract.yaml
name: summarize_contract
input: |
  Summarize this contract in 5 bullet points:
  "...The Contractor shall indemnify...termination upon 30 days notice..."
expected_contains:
  - liability
  - termination
max_tokens: 512
metadata:
  category: legal
  priority: high
```

Run a directory of scenarios:

```bash
agentprobe run scenarios/
```

---

## Drift Detection

Save a baseline after a known-good run. Future runs compare against it.

```bash
# Save baseline
agentprobe run scenarios/ --backend anthropic --save-baseline baseline.json

# Later: detect if outputs have drifted
agentprobe run scenarios/ --backend anthropic --baseline baseline.json --tolerance 0.8
```

`--tolerance 0.8` allows 20% variance. Drop below that, the run fails.

Drift is measured by [Jaccard similarity](https://en.wikipedia.org/wiki/Jaccard_index) on output tokens. Semantic similarity coming in v0.2.

---

## Backends

| Backend | Key required | Use case |
|---------|-------------|----------|
| `mock`  | No | CI, fast feedback, deterministic |
| `anthropic` | `ANTHROPIC_API_KEY` | Production evaluation |

```bash
# Mock (default)
agentprobe run scenarios/

# Claude
export ANTHROPIC_API_KEY=sk-...
agentprobe run scenarios/ --backend anthropic --model claude-opus-4-6
```

---

## CI Integration

```yaml
# .github/workflows/agent-tests.yml
- name: Run agent regression tests
  run: |
    pip install "agentprobe[anthropic]"
    agentprobe run scenarios/ \
      --backend anthropic \
      --baseline baseline.json \
      --tolerance 0.8
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

Exit code `1` on any failure — integrates cleanly with any CI system.

---

## Python API

```python
from agentprobe import Runner, Scenario
from agentprobe.backends.anthropic import AnthropicBackend

backend = AnthropicBackend(model="claude-opus-4-6")
runner = Runner(backend=backend, baseline_path="baseline.json")

scenario = Scenario(
    name="my_test",
    input="Summarize this contract...",
    expected_contains=["liability", "termination"],
)

result = runner.run_scenario(scenario)
print(result.passed, result.errors)
```

---

## Roadmap

- [x] YAML scenario format
- [x] Baseline + drift detection
- [x] Mock backend for CI
- [x] Anthropic/Claude backend
- [ ] Semantic similarity (embeddings-based drift)
- [ ] HTML/JSON report output
- [ ] OpenAI / Bedrock backends
- [ ] Scenario tagging + selective runs (`--tag smoke`)

---

## License

MIT
