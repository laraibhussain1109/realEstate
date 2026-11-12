# Verification

## Django regression tests

```bash
source .venv/bin/activate
python manage.py check
python manage.py test
```

The suite creates an isolated test database and checks public/private publication rules, active layout revisions, irregular geometry validation, staff permissions and CSRF, saved status history and counts, mixed area-unit filters, lead/site visit validation, gallery/testimonial visibility, canonical URLs and safe uploads.

Use a valid private production secret and production environment variables when running `python manage.py check --deploy`. That check does not replace deployment smoke checks.

## Optional real-browser map test

Start the local server and opt-in demonstration content first:

```bash
python manage.py seed_demo
python manage.py runserver 127.0.0.1:8000
```

In another terminal, install Playwright outside the repository and run the saved browser test. If system Chromium is available at `/usr/bin/chromium`:

```bash
npm install --prefix /tmp/plotmatrix-browser playwright
NODE_PATH=/tmp/plotmatrix-browser/node_modules \
  PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
  node scripts/browser_map_smoke.cjs
```

Otherwise install Playwright's supported Chromium browser, including the host's required system libraries, and omit `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. Keep package signatures and TLS validation enabled. Node.js and Playwright are optional development test tools; production serves the prewritten static assets through WSGI and does not use Node.js.

By default this script is read-only: it checks actual polygons, keyboard selection, project/plot enquiry context, the site visit modal and mobile horizontal overflow. It does not submit visitor leads.

To exercise staff editing, provide a private Playwright storage-state file containing a valid local staff login session with plot view/change/add/delete permissions:

```bash
NODE_PATH=/tmp/plotmatrix-browser/node_modules \
  PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium \
  PLOTMATRIX_STORAGE_STATE=/private/path/to/staff-storage-state.json \
  node scripts/browser_map_smoke.cjs
```

Treat that state file like a password: keep it outside the checkout, restrict its permissions and remove it when finished. The script contains no credentials and does not create users. Use a temporary local test account and revoke its session afterwards.

Staff tests refuse to write unless the selected project is explicitly marked **DEMO**. They change one available demo plot to Booked, verify public status and totals, restore it, draw and save a temporary irregular polygon, reload it and delete it with confirmation. Cleanup runs after errors too. The genuine audit records of those demo status changes remain. Run only against a disposable local development database, away from concurrent manual edits.

Optional configuration:

- `PLOTMATRIX_BASE_URL`: default `http://127.0.0.1:8000`.
- `PLOTMATRIX_PROJECT_SLUG`: default `govindpuram-society-demo`.
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`: optional installed Chromium path.
- `PLOTMATRIX_STORAGE_STATE`: optional private authenticated browser state.

Read the output carefully: a public-only run explicitly reports that staff writes were not run. A browser test does not certify a production deployment, approved inventory or survey accuracy.
