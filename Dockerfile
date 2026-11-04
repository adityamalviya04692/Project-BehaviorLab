FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BEHAVIOR_DB=/data/behavior.sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 10001 app && mkdir /data && chown app:app /data
COPY --chown=app:app . .
USER app
EXPOSE 8791
CMD ["gunicorn", "--bind", "0.0.0.0:8791", "--workers", "1", "--threads", "8", "--access-logfile", "-", "server:app"]
