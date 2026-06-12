FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements-production.txt .
RUN pip install --no-cache-dir -r requirements-production.txt

COPY webapp/ ./webapp/

# Run as non-root; the app writes generated graphs/uploads under webapp/
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=5000 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 5000

CMD ["sh", "-c", "exec gunicorn --chdir webapp --bind 0.0.0.0:${PORT} --timeout 120 --workers 2 app:app"]
