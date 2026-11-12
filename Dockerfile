# Optional: run the demo UI in a container.
#   docker build -t business-insights-agent .
#   docker run -p 8501:8501 business-insights-agent                 # guided demo, no API key
#   docker run -p 8501:8501 --env-file .env business-insights-agent  # live mode too
# The image builds the warehouse and the policy knowledge base (which downloads a 70 MB
# embedding model), so a container without an API key is the complete guided demo: this is
# what a hosted copy runs. CI builds and starts it.
FROM python:3.13-slim

# The uv version that wrote uv.lock, so the build doesn't change when uv does.
COPY --from=ghcr.io/astral-sh/uv:0.11.30 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev \
    && uv run python -m data.generator --scenario data/scenarios/dev.yaml \
    && uv run python -m data.generator --scenario data/scenarios/test.yaml \
    && uv run python -m mcp_servers.policies.build

EXPOSE 8501
CMD ["uv", "run", "streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.headless=true"]
