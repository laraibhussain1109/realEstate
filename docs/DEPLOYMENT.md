# PythonAnywhere deployment

This application uses ordinary Django WSGI. It does not need a Node.js production process, Redis, Docker, a worker queue, WebSockets or root access. An appropriate paid PythonAnywhere account is required for the custom domains `plotmatrix.in` and `www.plotmatrix.in`.

## 1. Prepare the account

Select an available Python version compatible with the pinned packages (Python 3.11 or later). Match that version when creating the virtual environment and the Web app. In a Bash console, replace the placeholders:

```bash
cd /home/YOUR_USERNAME
# Use your actual repository URL and authentication method.
git clone https://github.com/laraibhussain1109/realEstate.git
cd realEstate
python3.11 -m venv /home/YOUR_USERNAME/.virtualenvs/plotmatrix
source /home/YOUR_USERNAME/.virtualenvs/plotmatrix/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
chmod 600 .env
```

A PythonAnywhere account may require outbound-network permissions for package installation; use its supported package and network facilities. Keep TLS and package verification enabled.

## 2. Configure production

Edit `.env` privately. Use a new random `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, production `DJANGO_ALLOWED_HOSTS` and the HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS` for your domains. The repository's `.env.example` lists the application's supported names. Do not commit `.env` or paste the key into support messages.

Generate a key locally without putting it in shell history:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the result securely into `.env`. If console history/output is retained or shared, generate and store the key using your account's secure secret-management facility instead.

SQLite is the default and is suitable for modest workloads. Keep the database on persistent account storage. An optional `DATABASE_URL` can configure PostgreSQL or MySQL; install and pin its compatible driver (`psycopg` or `mysqlclient`) and follow PythonAnywhere's database connection instructions. Never put a database URL containing credentials into version control.

## 3. Initialize data and files

```bash
source /home/YOUR_USERNAME/.virtualenvs/plotmatrix/bin/activate
cd /home/YOUR_USERNAME/realEstate
python manage.py migrate
python manage.py seed_content
python manage.py setup_roles
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check
python manage.py check --deploy
python manage.py test
```

Do not run `seed_demo` on a public commercial deployment. If development demo records were copied from a local database, remove or archive them before public launch. Do not publish actual availability until staff have checked the source plan and inventory.

Investigate every deployment-check warning. Host-side HTTPS and static/media routing must be tested separately; a passing check is not proof that a deployed site is reachable.

## 4. Configure the Web app

In PythonAnywhere's Web tab:

1. Add a manual-configuration Python web application with the selected Python version.
2. Set the virtualenv path to `/home/YOUR_USERNAME/.virtualenvs/plotmatrix`.
3. Open its generated WSGI configuration file and use [pythonanywhere_wsgi.py](pythonanywhere_wsgi.py), replacing the username and repository directory.
4. Keep source code at `/home/YOUR_USERNAME/realEstate`. The WSGI file adds this folder to Python's import path and loads `.env`.
5. Set static mappings as below, using the actual `STATIC_ROOT` and `MEDIA_ROOT` configured in Django.
6. Reload the web application.

| URL | Directory |
| --- | --- |
| `/static/` | `/home/YOUR_USERNAME/realEstate/staticfiles/` |
| `/media/` | `/home/YOUR_USERNAME/realEstate/media/` |

Development-only Django media routing does not serve uploads with `DJANGO_DEBUG=False`. Both mappings are required. Map only the generated static directory and public upload directory; never map the repository root, database, `.env`, home directory or backup directory. Public uploads must be treated as files, never executed as Python/CGI. This application restricts raster images and PDF documents; do not loosen validation to upload active content.

## 5. Domain and HTTPS

Configure the paid account's custom web app for your chosen primary domain. Follow PythonAnywhere's current DNS guidance and point the domain's CNAME/record to the exact target shown in the Web tab. Add both intended hostnames to `DJANGO_ALLOWED_HOSTS` and both HTTPS origins to `DJANGO_CSRF_TRUSTED_ORIGINS`. Configure the alternate hostname as your hosting plan supports.

Enable a valid HTTPS certificate through the Web tab, confirm renewal, then test both domains. Production settings enable secure cookies and HTTP-to-HTTPS handling. Respect the hosting platform's trusted proxy configuration: do not blindly trust arbitrary forwarded headers on a different host.

## 6. Release smoke checks

Using a fresh private browser session:

- Open the homepage, published project, gallery and project layout without logging in.
- Confirm source images, logo, layout, CSS and JavaScript load over HTTPS without 404s or mixed content.
- Resize the layout and select a known boundary; check it matches the approved source.
- Submit a contact and a site visit enquiry; confirm both arrive in staff admin and that inventory is unchanged.
- Sign in as staff, change a test plot from Available to Booked, and verify the public color, label, totals and audit history. Restore the correct status afterwards.
- Confirm draft and archived project URLs return 404, and anonymous layout writes are rejected.
- Check uploaded gallery photographs and PDF documents with `DJANGO_DEBUG=False`.
- Confirm WhatsApp and Google Maps links contain the correct project/plot information.

Only then announce the release. No hosting deployment, DNS change, production approval or regulatory review is implied by local tests.

## Upgrades and backups

Before an upgrade, back up the SQLite database and complete media directory while writes are paused, or use SQLite's online backup API for a consistent snapshot. Store the files outside public directories. For remote databases use their supported backup tools. Test restoration periodically.

Activate the virtualenv, install the pinned requirements, run migrations, collect static, run checks/tests, then reload the Web app. Keep the previous code and a consistent pre-upgrade backup available. Restoring code alone cannot undo a schema/data migration safely.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ModuleNotFoundError` | Web tab virtualenv path, selected Python version, installed requirements and WSGI project path. |
| `DisallowedHost` | The exact requested hostname must be in `DJANGO_ALLOWED_HOSTS`; do not use `*` as a fix. |
| CSRF error | HTTPS origin configuration, correct host, cookie settings and submitted CSRF token. |
| Redirect loop | HTTPS/proxy configuration for the actual host. Do not disable secure cookies as a shortcut. |
| Missing CSS or admin styling | Run `collectstatic`; verify `/static/` maps to `STATIC_ROOT`. |
| Images work locally but disappear in production | Verify `/media/` mapping, `MEDIA_ROOT`, filesystem permissions and the uploaded file's existence. |
| Empty project page | Project/area publication flags, active layout revision and hidden-plot status. |
| Plot totals seem wrong | Check active revision and real visible plot records; totals are not manually entered. |
| Enquiry fails validation | Required contact fields, consent, project/plot relationship and a valid future site visit date. |
| SQLite locked | Avoid concurrent long-running writes; investigate request load and move to a hosted database if needed. |

Read the PythonAnywhere error and access logs for the exact failure. Do not publish logs containing personal data, cookies, secrets or private lead messages.
