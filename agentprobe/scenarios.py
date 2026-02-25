import hashlib
import logging
import warnings
import yaml
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """A single test case: input prompt + what the output must contain."""

    name: str
    input: str
    expected_contains: list[str] = field(default_factory=list)
    max_tokens: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_hash(self) -> str:
        """First 16 hex characters of the SHA-256 hash of the input prompt."""
        return hashlib.sha256(self.input.encode()).hexdigest()[:16]

    @classmethod
    def from_yaml(cls, path: Path | str) -> "Scenario":
        """Load a :class:`Scenario` from a YAML file at *path*."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, path: Path | str) -> None:
        """Serialise this scenario to a YAML file at *path*."""
        with open(path, "w") as f:
            yaml.dump(asdict(self), f, default_flow_style=False)

    @classmethod
    def load_directory(cls, directory: Path | str) -> list["Scenario"]:
        """Load all ``.yaml`` scenario files from *directory*.

        Files that cannot be parsed are skipped with a :mod:`warnings` warning
        rather than raising an exception, so a single malformed file does not
        abort the entire suite.
        """
        directory = Path(directory)
        scenarios = []
        for yaml_file in sorted(directory.glob("*.yaml")):
            try:
                scenarios.append(cls.from_yaml(yaml_file))
            except Exception as e:
                warnings.warn(f"Could not load scenario {yaml_file}: {e}", stacklevel=2)
        return scenarios
