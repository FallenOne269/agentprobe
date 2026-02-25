import os
from .base import AgentBackend

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class OpenAIBackend(AgentBackend):
    """OpenAI backend."""

    def __init__(self, model: str = "gpt-4o", api_key: str | None = None):
        if OpenAI is None:
            raise ImportError(
                "openai package required: pip install openai"
            )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. "
                "Set OPENAI_API_KEY or pass api_key=."
            )
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    def generate(self, prompt: str, max_tokens: int = 1024, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return response.choices[0].message.content
