# Verification

## Django regression tests

```bash
source .venv/bin/activate
python manage.py check
python manage.py test
```

The suite creates an isolated test database and checks public/private publication rules, active layout revisions, irregular geometry validation, staff permissions and CSRF, saved status history and counts, mixed area-unit filters, lead/site visit validation, gallery/testimonial visibility, canonical URLs and safe uploads.

Use a valid private production secret and production environment variables when running `python manage.py check --deploy`. That check does not replace deployment smoke checks.

## Automatic boundary detection and imports

Run the focused integration tests against real synthetic raster images:

```bash
python manage.py test estate.test_detection_api
```

These tests verify that detection and point suggestions do not write inventory, that public availability remains unchanged until explicit import, and that active staff need both add-plot and change-plot permissions. They also cover CSRF, draft layout privacy, explicit statuses, source-image freshness, atomic validation, duplicate numbers, existing-record preservation, interior overlap rejection, shared-edge handling, stable suggestion identities across scan/point review, four-corner-only suggestions/imports, stale detection cache isolation and batch limits. Valid trapezoids and adjacent slanted quadrilaterals are tested; valid triangles and pentagons must be rejected by automatic import without affecting the manual polygon editor. Test images are temporary and removed after the suite; the tests do not depend on a detector mock or external image-analysis service.

Before using real inventory, also test a representative copy of the actual plan in a draft revision: review suggested boundaries, remove roads/parks, correct plot numbers, assign verified statuses and import a small batch. Reload the editor and public page to confirm the correct revision and database records appear. Check an intentionally invalid batch leaves existing inventory unchanged. Computer vision and optional OCR accuracy vary with the image; a passing synthetic test is not a survey or inventory verification.

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
