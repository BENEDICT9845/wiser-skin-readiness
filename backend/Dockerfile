FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS test
COPY app ./app
COPY tests ./tests
COPY sample_requests ./sample_requests

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]

FROM base AS runtime
COPY app ./app

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
