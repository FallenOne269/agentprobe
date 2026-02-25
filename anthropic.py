import os
from .base import AgentBackend


class AnthropicBackend(AgentBackend):
    """Anthropic Claude backend."""

    def __init__(self, model: str = "claude-opus-4-6", api_key: str | None = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key required. "
                "Set ANTHROPIC_API_KEY or pass api_key=."
            )
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic package required: pip install anthropic"
            )
        self.client = Anthropic(api_key=self.api_key)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.content[0].text
