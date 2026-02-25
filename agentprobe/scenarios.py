import hashlib
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Scenario:
    """A single test case: input prompt + what the output must contain."""

    name: str
    input: str
    expected_contains: list[str] = field(default_factory=list)
    max_tokens: int = 1024
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        return hashlib.sha256(self.input.encode()).hexdigest()[:16]

    @classmethod
    def from_yaml(cls, path: Path | str) -> "Scenario":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path | str) -> None:
        with open(path, "w") as f:
            yaml.dump(asdict(self), f, default_flow_style=False)

    @classmethod
    def load_directory(cls, directory: Path | str, tag: str | None = None) -> list["Scenario"]:
        directory = Path(directory)
        scenarios = []
        for yaml_file in sorted(directory.glob("*.yaml")):
            try:
                s = cls.from_yaml(yaml_file)
                if tag is None or tag in s.tags:
                    scenarios.append(s)
            except Exception as e:
                print(f"Warning: could not load {yaml_file}: {e}")
        return scenarios
