FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8004}/health || exit 1

# Honor the platform-injected $PORT (Railway/Render/Fly/Heroku); default 8004 locally.
# exec via sh so $PORT expands AND uvicorn becomes PID 1 (clean SIGTERM shutdown).
CMD ["sh", "-c", "exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8004} --workers 1"]
