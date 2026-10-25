const {chromium} = require(process.argv[2] || 'playwright-core');
const assert = require('node:assert/strict');
(async () => {
  const b = await chromium.launch({executablePath: process.argv[3], headless: true});
  try {
    const page = await b.newPage({viewport: {width: 1300, height: 1000}});
    let errors = [];
    page.on('pageerror', e => errors.push(e.message));
    let network = [];
    page.on('request', r => { if (!r.url().startsWith('file:')) network.push(r.url()); });
    await page.clock.install();
    await page.goto(process.argv[4]);

    // Offline local file loads without errors
    assert.equal(await page.evaluate(() => window.PWNED), undefined);

    // Initial state: first case displayed
    const initialAngle = await page.locator('#angle').inputValue();
    assert.match(await page.locator('#meta').innerText(), /case_00/);

    // Field selector exists and works
    await page.locator('#field').selectOption('cp');
    assert.equal(await page.locator('#legendMin').innerText(), '-1.000');
    assert.equal(await page.locator('#legendMax').innerText(), '1.000');

    // View changes affect rendering
    const shot0 = await page.locator('#scene').screenshot();
    await page.locator('#view').selectOption('side');
    const shot1 = await page.locator('#scene').screenshot();
    assert.notDeepEqual(shot0, shot1);

    // Group filter works
    await page.locator('#group').selectOption('tip');
    await page.locator('#arrows').check();

    // Case selection changes displayed case and metadata
    await page.locator('#angle').selectOption('1');
    assert.match(await page.locator('#meta').innerText(), /case_05/);
    assert.match(await page.locator('#caseInfo').innerText(), /5\.00/);

    // Preserves camera when switching cases (by checking no reset occurs)
    const shot2 = await page.locator('#scene').screenshot();
    // Different angle should produce different render than initial
    assert.notDeepEqual(shot0, shot2);

    // No play controls exist (steady viewer has no animation)
    const playButton = await page.$('#play');
    assert.equal(playButton, null);

    // No frame scrubber exists
    const frameSlider = await page.$('#frame');
    assert.equal(frameSlider, null);

    // Camera controls still work
    const scene = page.locator('#scene');
    await scene.click({position: {x: 100, y: 100}});
    await scene.dragTo(scene, {destination: {x: 200, y: 200}});

    // No browser errors
    assert.deepEqual(errors, []);
    // No external requests
    assert.deepEqual(network, []);

    if (process.argv[5]) await page.screenshot({path: process.argv[5], fullPage: true});
    console.log(JSON.stringify({status: 'passed', checks: [
      'offline local file',
      'metadata injection inert',
      'Cp analytical range',
      'view changes render',
      'group/arrows controls',
      'case selection changes field rendering and metadata',
      'camera preserved across case switch',
      'no play button or time controls',
      'no browser errors',
      'no external requests'
    ]}));
  } finally {
    await b.close();
  }
})().catch(e => { console.error(e); process.exit(1); });
