/* Optional real-browser smoke test against a running local development server.
 * Default: read-only public test. For the staff write/restore test, provide a
 * private Playwright storage-state file through PLOTMATRIX_STORAGE_STATE.
 * No credentials, sessions or test accounts are embedded or created here.
 */
'use strict';
const assert = require('node:assert/strict');
const {chromium} = require('playwright');

const base = (process.env.PLOTMATRIX_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const slug = process.env.PLOTMATRIX_PROJECT_SLUG || 'govindpuram-society-demo';
const storageState = process.env.PLOTMATRIX_STORAGE_STATE;
const escapeRegex = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
assert(/^[a-z0-9-]+$/.test(slug), 'Use a valid project slug.');
assert(!new URL(base).username && !new URL(base).password, 'Keep credentials out of the base URL.');

(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? {executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH} : {}),
  });
  const context = await browser.newContext({viewport:{width:1440,height:1100}, ...(storageState ? {storageState} : {})});
  const page = await context.newPage();
  page.setDefaultTimeout(12000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let baseline, chosen, changed = false, temporaryId = null;
  const publicApi = `${base}/api/projects/${slug}/plots/`;
  let editorApi;
  const editorPost = async payload => {
    const cookies = await context.cookies(base);
    const csrf = cookies.find(cookie => cookie.name === 'csrftoken');
    assert(csrf, 'A CSRF cookie is required for editor writes.');
    const response = await context.request.post(editorApi, {data:payload, headers:{'X-CSRFToken':csrf.value, Referer:`${base}/`}});
    assert(response.ok(), `Editor request failed with HTTP ${response.status()}.`);
    return response.json();
  };
  const saveThroughForm = async () => {
    const pending = page.waitForResponse(response => response.url() === editorApi && response.request().method() === 'POST');
    await page.locator('#editor-save').click();
    const response = await pending;
    assert(response.ok(), `Editor form save failed with HTTP ${response.status()}.`);
    return response.json();
  };

  try {
    const initial = await context.request.get(publicApi);
    assert(initial.ok(), 'Run seed_demo and start the development server before this test.');
    baseline = await initial.json();
    assert(baseline.layout && baseline.plots.length, 'The selected public project needs a published layout with plots.');
    chosen = baseline.plots.find(plot => plot.status === 'available');
    assert(chosen, 'The browser workflow requires an available demo plot.');
    await page.goto(`${base}/projects/${slug}/`);
    await page.locator('.pm-plot').first().waitFor();
    assert.equal(await page.locator('.pm-plot').count(), baseline.plots.length);
    await page.getByRole('button', {name:new RegExp(`^Plot ${escapeRegex(chosen.number)}, Available`)}).press('Enter');
    await page.getByRole('button', {name:'Enquire about this plot →', exact:true}).click();
    const enquiry = await page.locator('#enquiry-dialog form').evaluate(form => ({
      open:form.closest('dialog').open, project:form.elements.namedItem('project').value,
      plot:form.elements.namedItem('plot').value, kind:form.elements.namedItem('kind').value,
    }));
    assert(enquiry.open && enquiry.project === slug && enquiry.plot === chosen.number && enquiry.kind === 'enquiry', 'Plot enquiry lost its project/plot context.');
    await page.getByRole('button', {name:'Close enquiry form'}).click();
    await page.locator('#plot-explorer').getByRole('button', {name:'Schedule a site visit', exact:true}).click();
    assert.equal(await page.locator('#enquiry-dialog [name=kind]').inputValue(), 'site_visit');
    await page.getByRole('button', {name:'Close enquiry form'}).click();
    await page.setViewportSize({width:375,height:900});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile page overflows horizontally.');
    assert.equal(await page.locator('.pm-plot').count(), baseline.plots.length);
    await page.setViewportSize({width:1440,height:1100});
    console.log(`Public map passed: ${baseline.plots.length} polygons; keyboard selection; enquiry/site visit context; mobile layout.`);

    if (!storageState) {
      console.log('Staff writes not run: set PLOTMATRIX_STORAGE_STATE to a private authorized staff browser state.');
    } else {
      assert(baseline.project.is_demo, 'Staff smoke writes are allowed only on an explicitly marked DEMO project.');
      editorApi = `${base}/api/layouts/${baseline.layout.id}/plots/`;
      await page.goto(`${base}/admin/estate/projectlayout/${baseline.layout.id}/editor/`);
      await page.locator('#editor-search').waitFor();
      const editorConfig = JSON.parse(await page.locator('#editor-config').textContent());
      const staffPlot = editorConfig.plots.find(plot => plot.slug === chosen.slug && plot.block === chosen.block);
      assert(staffPlot?.id, 'The chosen plot must exist in the authorized editor configuration.');
      chosen.id = staffPlot.id;
      await page.locator('#editor-search').fill(chosen.number);
      await page.locator('[name=status]').selectOption('booked');
      changed = true;
      await saveThroughForm();
      const after = await (await context.request.get(publicApi)).json();
      assert.equal(after.plots.find(plot => plot.number === chosen.number).status, 'booked');
      assert.equal(after.counts.available, baseline.counts.available - 1);
      assert.equal(after.counts.booked, baseline.counts.booked + 1);
      await page.locator('[name=status]').selectOption(chosen.status);
      await saveThroughForm();
      changed = false;

      await page.getByRole('button', {name:'◇ Draw a plot', exact:true}).click();
      await page.getByRole('button', {name:'Reset view', exact:true}).click();
      const viewBox = (await page.locator('.pm-svg').getAttribute('viewBox')).split(' ').map(Number);
      const [, , width, height] = viewBox;
      for (const vertex of [[width*.8,height*.84],[width*.85,height*.84],[width*.83,height*.9],[width*.8,height*.9]]) {
        const point = await page.locator('.pm-svg').evaluate((svg, coordinates) => {
          const source = svg.createSVGPoint(); source.x = coordinates[0]; source.y = coordinates[1];
          const screen = source.matrixTransform(svg.getScreenCTM()); return {x:screen.x,y:screen.y};
        }, vertex);
        await page.mouse.click(point.x,point.y);
      }
      await page.getByRole('button', {name:'✓ Close polygon',exact:true}).click();
      const temporaryNumber = `BROWSER-${Date.now()}`;
      await page.locator('[name=number]').fill(temporaryNumber);
      await page.locator('[name=area]').fill('90');
      await page.locator('[name=status]').selectOption('blocked');
      const created = await saveThroughForm();
      temporaryId = created.plot?.id;
      assert(temporaryId && created.plot.polygon.length === 4, 'Drawing did not save a four-vertex polygon.');
      await page.reload();
      await page.locator('#editor-search').fill(temporaryNumber);
      assert.equal(await page.locator('[name=number]').inputValue(),temporaryNumber);
      page.once('dialog', dialog => dialog.accept());
      const deletion = page.waitForResponse(response => response.url() === editorApi && response.request().method() === 'POST');
      await page.locator('#editor-delete').click();
      assert((await deletion).ok(), 'Temporary plot deletion failed.');
      temporaryId = null;
      console.log('Staff map passed: status/count persistence; irregular polygon drawing; reload; confirmed deletion; original availability restored.');
    }
    assert.deepEqual(errors, [], 'Browser JavaScript errors were observed.');
  } finally {
    // Leave only the legitimate audit records of the temporary demo status test.
    // Cleanup runs even if a browser assertion fails; no real inventory is edited.
    try {
      if (temporaryId) await editorPost({action:'delete',id:temporaryId});
      if (changed && chosen) await editorPost({action:'bulk',ids:[chosen.id],status:chosen.status,note:'Restored after optional demo browser smoke test'});
    } finally {
      await browser.close();
    }
  }
})().catch(error => {
  // Playwright call logs can include request cookies; report only the error's
  // first line and keep authenticated request details out of console output.
  console.error(String(error.message).split('\n')[0]);
  process.exitCode = 1;
});
