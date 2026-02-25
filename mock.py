import hashlib
from .base import AgentBackend


class MockBackend(AgentBackend):
    """
    Deterministic mock backend for CI and offline testing.
    Produces consistent output for a given prompt — no API key required.
    """

    def __init__(self, seed: str = "default"):
        self.seed = seed

    def generate(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        hash_val = hashlib.md5(f"{self.seed}:{prompt}".encode()).hexdigest()[:8]
        return (
            f"[MOCK] Deterministic response for prompt hash {hash_val}. "
            f"Prompt length: {len(prompt)} chars. "
            f"Max tokens: {max_tokens}."
        )
