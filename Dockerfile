# --builder--
FROM python:3.11-slim as builder

# install uv via pip
RUN pip install --no-cache-dir uv

WORKDIR /app

# copy pyproject.toml and uv.lock files
COPY pyproject.toml uv.lock* README.md ./

# install deps into venv
RUN uv sync --no-dev --frozen

# --runtime--
FROM python:3.11-slim as runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/*

# copy venv from builder
COPY --from=builder /app/.venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# create non-root user (security best practice)
RUN useradd -m -u 1000 etluser

WORKDIR /app

# copy source code
COPY --chown=etluser:etluser etl/ ./etl/
COPY --chown=etluser:etluser sql/ ./sql/
COPY --chown=etluser:etluser scripts/ ./scripts/
COPY --chown=etluser:etluser pyproject.toml ./

USER etluser

CMD ["python", "-m", "etl.run_pipeline", "--help"]
