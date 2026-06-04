FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=latexgenius.settings

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN addgroup --system django && adduser --system --ingroup django django
RUN chown -R django:django /app
USER django

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
