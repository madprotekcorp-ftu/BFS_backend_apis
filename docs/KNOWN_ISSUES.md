# Known issues, deviations and open decisions

## Open decisions (need BFS / frontend sign-off)

1. **Hosting and domain** are still open. CORS origins, the cookie domain and HTTPS can only be
   finalised once they are known.
2. **Service category names and descriptions.** The 15 slugs are the ones agreed with the
   frontend. The display names and `short_description` texts were written by the backend and
   should be checked by BFS. They can be edited in the Django admin without a code change.
3. **KYC and financial document storage** is built, but BFS has to confirm before go-live (as
   agreed in the spec).

## Contract notes for the frontend developer

These are small additions to, or interpretations of, the spec. Each needs agreement before it is final.

- **Login response** includes `csrf_token` as well as the user fields. Django rotates the CSRF
  token on login, so the frontend must use this new token afterwards.
- **`GET /api/auth/csrf/`** returns the token in the body (`data.csrf_token`) as well as setting
  the cookie, so the frontend never has to read a cross-subdomain cookie.
- **`409 duplicate_mobile`** includes `error.existing_lead_id` (per the spec) and, additionally,
  `error.existing_lead_code`.
- **Import `400` for missing columns** returns `error.code = "missing_columns"` and
  `error.missing_columns` (per the spec), plus `error.fields.file` with a readable message.
- **Import preview and batch detail** return the batch object with `rows` (one page) and
  `rows_pagination` inside `data` (per the spec), plus `created_at` and `imported_at`.
  `summary` has `successful_rows` and `failed_rows` only after confirm.
- **Unassign history:** `POST /assign/` with `employee_id: null` writes a history row with
  `new_employee: null`. The spec marks `new_employee` as required; it is nullable so unassignments
  stay in the history.
- **Dashboard `employee_counts`** items include `is_active`. Inactive employees appear only while
  they still hold leads, so the admin can transfer them.
- **Public services `group`** and **import `status` / `result`** are returned as bare codes, as in
  the spec's examples, not as `{code, label}` objects.
- **Honeypot:** when the hidden `website` field is filled in, the API answers `201` with a dummy
  reference and saves nothing, so bots get no signal.
- **Spec says "31 endpoints"** but its table lists 34. All 34 are implemented.

## Behaviour worth knowing

- **Import duplicates within one file** are matched against earlier *valid* rows only. If the first
  row with a number is invalid (e.g. unknown service), a later valid row with the same number is
  imported.
- **Confirm re-checks** valid rows against the database, so a lead added between preview and
  confirm is reported as a duplicate, not imported twice.
- **Admin manual leads** may use an inactive service; only the public enquiry requires an active one.
- **Search** matches lead codes by "contains" (e.g. `000123`) as well as names and mobiles.
- **CSV export escaping** prefixes cells starting with `=`, `+`, `-` or `@` with `'`, so a loan
  amount like `-5` shows as `'-5`. The importer strips this prefix again, so exported files can be
  re-imported.

## Environment notes

- Local development is on Python 3.13 and PostgreSQL 18 rather than the 3.12 and 16 the spec
  names. The code works on both; production can use 3.12 and 16.
- Throttle counters (login failures, enquiry rate) live in a database cache table, so they are
  shared across Gunicorn workers. Run `manage.py createcachetable` once per environment.
- `django-filter`, listed as a recommended extra, is not used: the lead filters are shared by the
  list, export and dashboard, so they are implemented once in `apps/leads/filters.py`.
