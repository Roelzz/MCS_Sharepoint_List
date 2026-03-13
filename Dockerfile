FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml .

# Install dependencies to a virtual environment
RUN uv venv .venv && \
    uv pip install --no-cache -r pyproject.toml

FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY src/ src/
COPY data/ data/

# Runtime config
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8080

# Entry point
ENTRYPOINT ["python", "-m", "src.server"]

