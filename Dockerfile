FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip uv && \
    uv pip install --system --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python3 -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8004)}/health', timeout=5)" || exit 1

# Honor the platform-injected $PORT (PaaS platforms); default 8004 locally.
# WEB_CONCURRENCY defaults to 1 (safe on low-memory free-tier hosts — each
# worker is a separate process with its own DB pool and thread pool); a
# multi-vCPU deployment can raise it to use every core, since a single
# process's classification work is GIL-bound and can't do that alone.
# exec via sh so $PORT expands AND uvicorn becomes PID 1 (clean SIGTERM shutdown).
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8004} --workers ${WEB_CONCURRENCY:-1}"]
