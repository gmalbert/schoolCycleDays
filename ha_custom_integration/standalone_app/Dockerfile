FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY school_cycle_days ./school_cycle_days
COPY templates ./templates

RUN mkdir -p /data
ENV SCD_DATABASE_PATH=/data/school_cycle_days.sqlite3

EXPOSE 8088

CMD ["uvicorn", "school_cycle_days.main:app", "--host", "0.0.0.0", "--port", "8088"]
