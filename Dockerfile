# Builder: resolve and install dependencies (wheels only, no compiler needed).
FROM python:3.12-alpine AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final: just the interpreter, installed packages and app code.
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /install /usr/local
COPY arr_exporter/ arr_exporter/

RUN adduser -D -H appuser
USER appuser

EXPOSE 8000

CMD ["python", "-m", "arr_exporter.main"]
