FROM ghcr.io/astral-sh/uv:0.11.8 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy RB_HOST=0.0.0.0 RB_PORT=8000
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra server --no-editable \
    && useradd --uid 10001 --create-home app
USER app
EXPOSE 8000
CMD ["/app/.venv/bin/research-bridge-ai-api"]
