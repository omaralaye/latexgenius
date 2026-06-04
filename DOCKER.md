# Docker Setup

LaTeXGenius runs in three containers:

- **web** — Django app served by Gunicorn with Whitenoise
- **db** — PostgreSQL 16 (production only)
- **latex-online** — LaTeX compilation microservice

## Quick Start (Development)

```bash
docker compose up --build
```

The app is available at `http://localhost:8000`.

Migrations run automatically on startup. Source code is mounted as a volume, so changes take effect immediately.

## Production Deployment

### 1. Set environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
DB_NAME=latexgenius
DB_USER=latexgenius
DB_PASSWORD=your-strong-db-password
KIMI_API_KEY=your-nvapi-key
KIMI_MODEL=moonshotai/kimi-k2.6
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. Build and start

```bash
docker compose -f docker-compose.prod.yml --env-file .env up --build -d
```

### 3. Create a superuser (first run)

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 4. Stop

```bash
docker compose -f docker-compose.prod.yml down
```

## Architecture

```
Browser ──► Gunicorn (:8000) ──► PostgreSQL (:5432)
                │
                └──► latex-online (:2700)
```

## Useful Commands

| Action | Command |
|--------|---------|
| View logs | `docker compose logs -f` |
| Shell into web | `docker compose exec web bash` |
| Run migrations | `docker compose exec web python manage.py migrate` |
| Rebuild | `docker compose up --build -d` |
