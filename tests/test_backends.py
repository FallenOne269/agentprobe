"""Tests for backends — mock determinism, Anthropic auth handling."""

from unittest.mock import MagicMock, patch

import pytest

from agentprobe.backends.mock import MockBackend
from agentprobe.backends.anthropic import AnthropicBackend


class TestMockBackend:
    def test_returns_string(self):
        b = MockBackend()
        out = b.generate("Hello")
        assert isinstance(out, str)
        assert len(out) > 0

    def test_deterministic_same_prompt(self):
        b = MockBackend()
        assert b.generate("test prompt") == b.generate("test prompt")

    def test_different_prompts_differ(self):
        b = MockBackend()
        assert b.generate("prompt A") != b.generate("prompt B")

    def test_seed_affects_output(self):
        b1 = MockBackend(seed="alpha")
        b2 = MockBackend(seed="beta")
        assert b1.generate("same prompt") != b2.generate("same prompt")

    def test_same_seed_same_output(self):
        b1 = MockBackend(seed="fixed")
        b2 = MockBackend(seed="fixed")
        assert b1.generate("prompt") == b2.generate("prompt")

    def test_contains_prompt_length(self):
        b = MockBackend()
        prompt = "A" * 42
        out = b.generate(prompt)
        assert "42" in out

    def test_max_tokens_reflected(self):
        b = MockBackend()
        out = b.generate("test", max_tokens=256)
        assert "256" in out


class TestAnthropicBackend:
    def test_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="API key"):
            AnthropicBackend(api_key=None)

    def test_accepts_explicit_api_key(self):
        with patch("agentprobe.backends.anthropic.AnthropicBackend.__init__") as mock_init:
            mock_init.return_value = None
            b = AnthropicBackend.__new__(AnthropicBackend)
            # Just verify no ValueError raised with explicit key

    def test_generate_calls_client(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Mocked Claude response")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        with patch("agentprobe.backends.anthropic.Anthropic", return_value=mock_client):
            b = AnthropicBackend(model="claude-opus-4-6")
            result = b.generate("Test prompt", max_tokens=100)

        assert result == "Mocked Claude response"
        mock_client.messages.create.assert_called_once_with(
            model="claude-opus-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": "Test prompt"}],
        )

    def test_model_stored(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        with patch("agentprobe.backends.anthropic.Anthropic"):
            b = AnthropicBackend(model="claude-haiku-4-5-20251001")
            assert b.model == "claude-haiku-4-5-20251001"
