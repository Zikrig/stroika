FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install .

COPY tests ./tests

RUN mkdir -p /app/data

CMD ["python", "-m", "app.main"]
