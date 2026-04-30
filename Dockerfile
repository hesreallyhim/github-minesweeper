FROM python:3.11-slim

LABEL maintainer="github-issue-minesweeper"
LABEL description="Local validation image for GitHub Issue Minesweeper"

WORKDIR /app

# Install system dependencies (make for Makefile targets)
RUN apt-get update && \
    apt-get install -y --no-install-recommends make && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency list first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project
COPY config.yaml Makefile ./
COPY src/ src/
COPY tests/ tests/
COPY scripts/ scripts/

ENV PYTHONPATH=/app/src
ENV PYTHONIOENCODING=utf-8
ENV MINESWEEPER_SECRET=dev-secret-do-not-use-in-prod
ENV MINESWEEPER_SEED=42

# Default: run the test suite
CMD ["pytest", "tests", "-q"]
