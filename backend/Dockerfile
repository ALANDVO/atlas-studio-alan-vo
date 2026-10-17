FROM python:3.12-slim AS base

# Create nonroot user
RUN groupadd --system appgroup && useradd --system --gid appgroup --create-home appuser

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source
COPY ./app /app/app
COPY VERSION /app/VERSION

# Non-root
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()"

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]