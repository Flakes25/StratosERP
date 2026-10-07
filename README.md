# StratosERP

A cloud-based Enterprise Resource Planning system for inventory, asset and employee
management, with hardware telemetry. Built with Python and Django (MVT) for
Holy Angel University, Object-Oriented Programming, SY 2026-2027, 1st semester.

## What it does (mapped to the proposal)

| Objective | Where it lives |
|---|---|
| **A** Normalized database | `core/models.py`: Department, Employee, Supplier, Category, InventoryItem, StockMovement, PurchaseRequest, AssetAssignment, HardwareNode, ActivityLog |
| **B** Role-based access control | `core/permissions.py` (one `ACCESS` table), four groups created by `setup_roles` |
| **C** Inventory and procurement | `/inventory/`, `/suppliers/`, `/procurement/`, `/movements/` with request, approve, receive and automatic stock updates |
| **D** Asset assignment | `/assignments/`, assigning and returning updates stock and keeps full history; employee profiles show equipment held |
| **E** Dashboard, reports, CSV | Dashboard charts and low-stock alerts, `/reports/`, four CSV exports |
| Hardware telemetry | `/telemetry/` (auto-refresh), `POST /api/telemetry/` and `agent/telemetry_agent.py` |

## Roles

| Role | Can do |
|---|---|
| Administrator | Everything; manages users in `/admin/` (tick "Staff status") |
| Inventory Staff | Inventory, categories, suppliers, assignments, hardware; marks requests received |
| Human Resource Personnel | Employees and departments |
| Department Manager | Views most modules, creates purchase requests, approves or rejects them |

To change who can do what, edit the `ACCESS` table in `core/permissions.py`.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python manage.py makemigrations core
python manage.py migrate
python manage.py setup_roles --demo
python manage.py runserver
```

Open http://127.0.0.1:8000/ and log in. Demo accounts (password `stratos123`):
`demo_admin`, `demo_inventory`, `demo_hr`, `demo_manager`.

Settings changes needed are listed in `deploy/settings_snippet.py`.

## Tests

```bash
python manage.py test core
```

## Live telemetry from a real machine

1. Set `TELEMETRY_API_KEY` on the server (see `.env.example`) and restart it.
2. On the machine to monitor:
   ```bash
   pip install -r agent/requirements.txt
   python agent/telemetry_agent.py --url http://127.0.0.1:8000 --key YOUR_KEY
   ```
3. Open `/telemetry/`. The node appears and updates every few seconds.
4. Nodes that stop reporting stay "Online" until you run
   `python manage.py mark_stale_nodes --minutes 2` (schedule it with cron or a host cron job).

## Deploy to the cloud (example: Render)

1. Push the project to GitHub (`.gitignore` already excludes secrets and the local database).
2. Create a **PostgreSQL** database on the host and copy its connection URL.
3. Create a **Web Service** from the repository:
   - Build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_roles`
   - Start command: `gunicorn YOURPROJECT.wsgi` (replace `YOURPROJECT` with the folder that contains `settings.py`)
4. Set the environment variables from `.env.example`: `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `TELEMETRY_API_KEY`.
5. In the service shell run `python manage.py createsuperuser`, then add users to the four groups in `/admin/`.

Any host that runs Django and PostgreSQL works the same way (Railway, Fly.io, PythonAnywhere).

## Project layout

```
core/
  models.py          database design
  permissions.py     roles and the access table
  views.py           pages, CRUD factory, actions, charts, CSV, telemetry API
  forms.py           forms and validation
  urls.py            routes
  tests.py           automated tests
  templates/         base.html, dashboard, list/form pages, reports, telemetry, login
  management/commands/   setup_roles, mark_stale_nodes
agent/               telemetry agent for monitored machines
deploy/              settings for local and cloud use
```

## Team

| Member | Role |
|---|---|
| Ravao, Mark Angelo (Leader) | Frontend development (HTML) |
| Kippen, Jack John | Website styling (CSS) |
| Mangune, Cian Joshua | Interactive features (JavaScript) |
| Pecson, Mari Veighbrell | Backend development (Django) |
| Reyes, Lance Gabriel | Django ORM and models |
| Tullao, Arjay | Template integration |
| Tuquib, Rel Prince P. | Testing and debugging |

Prepared for Engr. Arnaz De Jesus.
