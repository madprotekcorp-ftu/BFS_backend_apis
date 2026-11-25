# Deployment guide — Gunicorn + Nginx + PostgreSQL + HTTPS

This assumes Ubuntu 22.04/24.04, with the API on its own subdomain (e.g. `api.example.com`) and
the React site on `example.com`. The real domain is still an open decision.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql nginx libmagic1 certbot python3-certbot-nginx
```

## 2. Database

```bash
sudo -u postgres psql -c "CREATE USER bfs WITH PASSWORD '<strong-password>';"
sudo -u postgres psql -c "CREATE DATABASE bfs OWNER bfs;"
```

## 3. Application

```bash
sudo adduser --system --group --home /srv/bfs bfs
sudo -u bfs git clone <repo-url> /srv/bfs/app
cd /srv/bfs/app
sudo -u bfs python3.12 -m venv .venv
sudo -u bfs .venv/bin/pip install -r requirements.txt
sudo -u bfs mkdir -p /srv/bfs/private_media && sudo chmod 750 /srv/bfs/private_media
```

Create `/srv/bfs/app/.env`, readable only by the `bfs` user (`chmod 600`):

```ini
DJANGO_SECRET_KEY=<50+ random characters>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=api.example.com
DATABASE_URL=postgres://bfs:<strong-password>@localhost:5432/bfs
CORS_ALLOWED_ORIGINS=https://example.com,https://www.example.com
CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
SESSION_COOKIE_DOMAIN=.example.com
PRIVATE_MEDIA_ROOT=/srv/bfs/private_media
DOCUMENT_MAX_SIZE_MB=10
IMPORT_MAX_ROWS=5000
TIME_ZONE=Asia/Kolkata
NUM_PROXIES=1
DOCUMENTS_USE_X_ACCEL=True
# Staging only:
# API_DOCS_ENABLED=True
```

Then run:

```bash
export DJANGO_SETTINGS_MODULE=config.settings.prod
sudo -u bfs -E .venv/bin/python manage.py migrate
sudo -u bfs -E .venv/bin/python manage.py createcachetable
sudo -u bfs -E .venv/bin/python manage.py collectstatic --noinput   # only needed if Swagger/admin are enabled
sudo -u bfs -E .venv/bin/python manage.py check --deploy
sudo -u bfs -E .venv/bin/python manage.py createsuperuser           # the BFS admin account
```

Never run `seed_demo` in production.

## 4. Gunicorn (systemd)

`/etc/systemd/system/bfs.service`:

```ini
[Unit]
Description=BFS API (Gunicorn)
After=network.target postgresql.service

[Service]
User=bfs
Group=bfs
WorkingDirectory=/srv/bfs/app
Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
# The access-log format uses the path only (%(U)s), never the query string,
# so mobile numbers typed into search are not written to the logs.
ExecStart=/srv/bfs/app/.venv/bin/gunicorn config.wsgi:application \
    --bind 127.0.0.1:8001 --workers 3 --timeout 60 \
    --access-logfile - --access-logformat '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)ss'
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now bfs
```

## 5. Nginx

`/etc/nginx/sites-available/bfs-api`:

```nginx
server {
    listen 80;
    server_name api.example.com;
    client_max_body_size 12m;          # 10 MB documents + multipart overhead

    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;   # overwrite, don't append (NUM_PROXIES=1)
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;                         # large imports
    }

    # Only reachable via X-Accel-Redirect from Django after the auth check.
    location /protected-documents/ {
        internal;
        alias /srv/bfs/private_media/;
        add_header X-Content-Type-Options nosniff always;
        add_header Cache-Control "private, no-store" always;
    }

    # Only if Swagger/admin are enabled (staging):
    # location /static/ { alias /srv/bfs/app/staticfiles/; }

    location / { return 404; }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/bfs-api /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.example.com     # HTTPS + automatic renewal
```

Make sure `private_media` is **never** under an Nginx `root` or a `location` that is not `internal`.
The `www-data` user needs read access to it (e.g. `sudo usermod -aG bfs www-data`).

## 6. Scheduled jobs

```cron
# crontab -u bfs -e
0 * * * * cd /srv/bfs/app && DJANGO_SETTINGS_MODULE=config.settings.prod .venv/bin/python manage.py cleanup_import_previews
30 3 * * * cd /srv/bfs/app && DJANGO_SETTINGS_MODULE=config.settings.prod .venv/bin/python manage.py clearsessions
```

## 7. Backups

Back up both the database (`pg_dump`) and `/srv/bfs/private_media/`. They must be restored together:
document records point at files by `storage_key`.

## 8. Release checklist (security, from spec section 7)

- [ ] `DJANGO_DEBUG=False`, `manage.py check --deploy` shows no warnings
- [ ] HTTPS works and HTTP redirects; the HSTS header is present
- [ ] `/api/docs/`, `/api/schema/` and `/django-admin/` return 404 in production
- [ ] `CORS_ALLOWED_ORIGINS` lists only the real frontend origins
- [ ] `.env` is not in git and is `chmod 600`
- [ ] `https://api.example.com/protected-documents/...` returns 404 when opened directly
- [ ] The admin account has a strong password
- [ ] The production database holds no demo data
