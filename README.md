# Plot Matrix

A Django 5.2 application for public residential project discovery and staff-managed plot availability. Visitors do not need an account. Project information, site content, leads, gallery photographs and testimonials are managed in Django admin. The SVG master-plan viewer and visual editor use the same image coordinate system, so polygons stay aligned when the page resizes. Authorized staff can generate boundary suggestions from uploaded plans, review and correct them, assign real plot numbers and explicit statuses, then import the selected polygons. Detection previews never create inventory automatically.

## Local development

Use Python 3.11 or later, preferably the same version selected for hosting. Node.js, Redis, Docker and background workers are not required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_content
python manage.py setup_roles
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Set a unique `DJANGO_SECRET_KEY` in `.env`. Open the application's public homepage and `/admin/`. Create your own administrator; the repository does not contain a shared password or enabled default administrator account. In a managed cloud task, use the existing isolated checkout; no extra Git worktree is needed.

Optional development content:

```bash
python manage.py seed_demo
```

The demo is explicitly labeled **DEMO** and illustrates interaction only. Its availability is invented for development and must not be presented as real inventory. Run `seed_content` to load editable brochure-derived company details without inventing projects, customer quotes, approvals or sales statistics. The master-plan reference is manually traced from the supplied illustration and is not a verified survey. Replace it with the original approved layout and verify each boundary before publishing real inventory.

## Architecture

- `config/`: environment-driven settings, root URL routing and WSGI entry point.
- `estate/models.py`: company content, locations, projects, layout revisions, plots, availability history, galleries, testimonials and leads.
- `estate/admin.py`: company administration and visual-editor links.
- `estate/views.py`: public pages, read-only discovery APIs, lead submission and permission-protected layout writes.
- `estate/detection_views.py`: permission-protected boundary preview and validated, atomic polygon imports.
- `estate/plot_detection.py`: local image boundary detection and optional OCR-assisted number suggestions.
- `estate/templates/estate/`: server-rendered pages and map editor.
- `estate/static/estate/`: CSS, native JavaScript and supplied brand assets. No frontend build is needed.
- `estate/management/commands/`: repeatable content initialization and optional demo setup.
- `estate/tests.py` and `estate/test_*.py`: integration, validation, access-control and boundary-detection tests.

Availability is derived from database records. Enquiring does not reserve a plot. Staff changes write an audit record; the public viewer periodically re-fetches status. Internal remarks are excluded from public JSON. Draft and archived projects, hidden plots and unpublished testimonials are excluded from public discovery.

Automatic detection uses the pinned OpenCV headless dependencies from `requirements.txt`, with no external image-analysis service or background worker. Optional number OCR uses a system Tesseract executable if available; otherwise assign numbers manually. No colour-based availability is imported automatically. Review all suggested boundaries and numbers against the source plan before publishing real inventory.

## Everyday administration

Read [the administrator handbook](docs/ADMINISTRATOR.md) for adding areas/projects, drawing plot boundaries, changing availability, publishing media and handling leads. Give staff only the Django model permissions they need. Keep superuser access limited.

## Checks

```bash
python manage.py check
python manage.py test
python manage.py collectstatic --noinput
```

Check the actual production configuration separately:

```bash
DJANGO_DEBUG=False python manage.py check --deploy
```

That command requires a strong environment-managed secret and production host/origin configuration. It does not prove HTTPS, static mappings, upload permissions, backups or a deployment work. Perform the deployment smoke checks in [the deployment guide](docs/DEPLOYMENT.md).

Optional browser interaction checks are documented in [the testing guide](docs/TESTING.md). They use actual rendered maps and can exercise a temporary demo status change and polygon drawing with authorized staff access.

## Deployment

See [PythonAnywhere deployment](docs/DEPLOYMENT.md) and [the WSGI example](docs/pythonanywhere_wsgi.py). The application runs as ordinary WSGI with SQLite by default. Optional database URLs use `dj-database-url`; install the corresponding PostgreSQL/MySQL driver separately if switching databases. Public uploaded files need a PythonAnywhere media mapping when `DJANGO_DEBUG=False`.

## Data and media

Back up SQLite and uploaded media together. Do not commit `.env`, database files, upload directories or production credentials. Content creation and status updates should be performed through the admin or editor, rather than editing the database by hand. Layout revisions protect existing geometry: create a new revision when replacing a plan, annotate and verify it, then activate it.

The brochure provides the company logo and contact details. Unverified founding-year, template-company, endorsement and achievement claims were deliberately omitted. Regulatory approvals, prices and real availability require administrator verification before publication.
