FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
COPY pyproject.toml README.md LICENSE ./
COPY agentprobe/ ./agentprobe/

# Install the package with optional LLM backends
RUN pip install --no-cache-dir ".[anthropic,openai]"

# Copy example scenarios so the image is self-contained for demos
COPY scenarios/ ./scenarios/

ENTRYPOINT ["agentprobe"]
CMD ["--help"]
