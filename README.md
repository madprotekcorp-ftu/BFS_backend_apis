# BFS Phase 1 — Backend

Django REST API for the Bright Financial Solution website enquiry form and the admin
Lead Management System (LMS). The React frontend talks to it only through the JSON
endpoints under `/api/`.

- **Stack:** Python 3.12+ (tested on 3.13), Django 5.2, Django REST Framework, PostgreSQL 16+ (tested on 18)
- **API docs:** Swagger UI at `/api/docs/`, OpenAPI schema at `/api/schema/` (dev and staging only)
- **Deployment:** see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Known issues and open decisions:** see [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md)

## Project layout

```
config/            settings (base, dev, prod, test), urls, wsgi
apps/
  accounts/        csrf, login, logout, me
  catalog/         ServiceCategory + public services API (15 seeded categories)
  leads/           Lead, LeadRemark, enquiry, CRUD, filters, export, dashboard, seed_demo
  employees/       Employee, LeadAssignment, assign/transfer + history
  imports/         ImportBatch, ImportRow, template, preview, confirm, cancel, report
  documents/       LeadDocument, upload, download, bin, restore, purge
common/            response envelope, pagination, exception handler, enums, mobile validator
private_media/     uploaded documents (git-ignored, never served by a URL route)
tests/             pytest suite (acceptance tests from the spec)
```

## Local setup (Windows)

1. Create the database in PostgreSQL (pgAdmin or psql):
   ```sql
   CREATE DATABASE bfs_project_db;
   ```
2. Create a virtual environment and install dependencies:
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```
3. Copy `.env.example` to `.env` and fill in the values. `DATABASE_URL` looks like
   `postgres://USER:PASSWORD@localhost:5432/bfs_project_db`.
4. Create the tables, the cache table (used by the login and enquiry throttles) and an admin:
   ```powershell
   python manage.py migrate
   python manage.py createcachetable
   python manage.py createsuperuser
   ```
5. Optional: load fake demo data (employees, 60 leads, remarks, assignments):
   ```powershell
   python manage.py seed_demo
   ```
6. Run the server:
   ```powershell
   python manage.py runserver
   ```
   The API is at http://127.0.0.1:8000/api/ and Swagger at http://127.0.0.1:8000/api/docs/.
   The Django admin is at `/django-admin/` in dev (it is kept off `/admin/`, which the React app uses).

On Linux/macOS, use `source .venv/bin/activate` and install the `libmagic1` system package
(Windows uses the bundled `python-magic-bin`).

## Running the tests

```powershell
python -m pytest
```

The test run creates and drops its own `test_<dbname>` database, so the database user needs the
`CREATEDB` permission.

## How the frontend integrates

1. Call `GET /api/auth/csrf/` once. It sets the `csrftoken` cookie and returns `{ "csrf_token": "..." }`.
2. Send that value as the `X-CSRFToken` header on every POST, PATCH and DELETE, including login.
   Requests must use `credentials: "include"`.
3. `POST /api/auth/login/` with `{ "username", "password" }` (username or email). The response
   includes a **new** `csrf_token`, because Django rotates the token on login. Use it from then on.
4. On page load, `GET /api/auth/me/` returns the admin or a 401 (`not_authenticated`).
5. Sessions last 8 hours from login.

Every JSON response uses one envelope:

```json
{ "success": true, "data": {}, "message": "Lead created" }
{ "success": true, "data": [], "pagination": { "page": 1, "page_size": 20, "total": 143, "total_pages": 8 } }
{ "success": false, "error": { "code": "validation_error", "message": "...", "fields": { "mobile": ["..."] } } }
```

File downloads (CSV, XLSX and documents) are the only responses without the envelope.

## Useful commands

| Command | What it does |
|---|---|
| `python manage.py seed_demo` | Fake demo data (dev only; refuses to run when DEBUG is off) |
| `python manage.py cleanup_import_previews` | Cancels import previews older than 24 hours (run hourly from cron) |
| `python manage.py spectacular --file schema.yml` | Exports the OpenAPI schema to a file |
