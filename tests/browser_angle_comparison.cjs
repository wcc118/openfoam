// Synthetic inputs only; no CFD results are manufactured by this browser test.
const {chromium} = require(process.argv[2] || 'playwright-core');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'angle-viewer-test-'));
  execFileSync('python3', ['-c', `
import importlib.util, pathlib, sys
s=importlib.util.spec_from_file_location('fixture',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
d=m.fixture();d['cases'][0]['source_revision']='</script><script>window.PWNED=true</script>'
p=pathlib.Path(sys.argv[2]);(p/'two.html').write_text(m.module.build_html(d))
d['cases']=d['cases'][:1];d['samples']['groups']=['midspan']*len(d['samples']['points'])
(p/'one.html').write_text(m.module.build_html(d))
`, path.join(__dirname, 'test_angle_comparison.py'), tmp]);
  const browser = await chromium.launch({executablePath: process.argv[3], headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1300, height: 1000}});
    const errors = [], network = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (!r.url().startsWith('file:')) network.push(r.url()); });
    // Observe projected wing geometry without adding test hooks to production code.
    await page.addInitScript(() => {
      const p = CanvasRenderingContext2D.prototype;
      const begin = p.beginPath, move = p.moveTo, line = p.lineTo, fill = p.fill, clear = p.clearRect;
      p.clearRect = function(...a) {window.__wingPaths=[];return clear.apply(this,a);};
      p.beginPath = function(...a) {this.__path=[];return begin.apply(this,a);};
      p.moveTo = function(...a) {this.__path?.push(['M',...a]);return move.apply(this,a);};
      p.lineTo = function(...a) {this.__path?.push(['L',...a]);return line.apply(this,a);};
      p.fill = function(...a) {if(this.fillStyle==='#566b82')window.__wingPaths.push(this.__path.slice());return fill.apply(this,a);};
    });
    await page.goto(pathToFileURL(path.join(tmp,'two.html')).href);
    assert.equal(await page.evaluate(() => window.PWNED), undefined);
    assert.match(await page.locator('#meta').innerText(), /case_00/);
    assert.equal(await page.locator('#arrows').isChecked(), true);
    const scene = page.locator('#scene'), shot = () => scene.screenshot();
    const arrowsOn = await shot();
    await page.locator('#arrows').uncheck();
    assert.notDeepEqual(arrowsOn, await shot(), 'arrow toggle must change rendering');
    const speed = await shot();
    await page.locator('#field').selectOption('cp');
    assert.equal(await page.locator('#legendMin').innerText(), '-1.000');
    assert.equal(await page.locator('#legendMax').innerText(), '1.020'); // analytical max (112-10)/100
    assert.notDeepEqual(speed, await shot(), 'field selection must change rendering');
    const all = await shot();
    await page.locator('#group').selectOption('tip');
    assert.notDeepEqual(all, await shot(), 'group selection must change rendering');
    await page.locator('#group').selectOption('all');
    await page.locator('#arrows').check();
    await page.locator('#view').selectOption('side');
    const box = await scene.boundingBox();
    await page.mouse.move(box.x+200,box.y+200);await page.mouse.down();
    await page.mouse.move(box.x+240,box.y+220,{steps:4});await page.mouse.up();
    await page.keyboard.down('Shift');await page.mouse.down();
    await page.mouse.move(box.x+260,box.y+230,{steps:3});await page.mouse.up();await page.keyboard.up('Shift');
    await page.mouse.wheel(0,-120);
    await page.waitForTimeout(50);
    const geometry = await page.evaluate(() => window.__wingPaths), before = await shot();
    assert.equal(geometry.length,1);
    await page.locator('#angle').selectOption('1');
    assert.deepEqual(await page.evaluate(() => window.__wingPaths),geometry,'case switch must preserve projected wing geometry');
    assert.notDeepEqual(before,await shot(),'same-view case selection must change field rendering');
    assert.match(await page.locator('#meta').innerText(), /case_05/);
    const info = await page.locator('#caseInfo').innerText();
    assert.match(info,/not physical time/);assert.ok(info.includes('a'.repeat(64)) && info.includes('b'.repeat(64)));
    assert.equal(await page.locator('#limitations li').count(),1);
    await page.locator('#angle').selectOption('0');
    assert.deepEqual(await shot(),before,'round-trip case selection must preserve camera and original field');
    assert.equal(await page.locator('#limitations li').count(),1);
    assert.equal(await page.locator('#play,#frame').count(),0);
    if(process.argv[4])await page.screenshot({path:process.argv[4],fullPage:true});
    await page.goto(pathToFileURL(path.join(tmp,'one.html')).href);
    assert.equal(await page.locator('#angle option').count(),1);
    await page.locator('#group').selectOption('tip');
    const emptyGeometry=await page.evaluate(() => window.__wingPaths);
    assert.equal(emptyGeometry.length,1);
    assert.ok(emptyGeometry.flat(2).filter(v=>typeof v==='number').every(Number.isFinite));
    assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
    console.log(JSON.stringify({status:'passed',checks:['synthetic fixture generation','injection inert','arrows/field/group rendering','analytical common Cp range','case-dependent fields at fixed camera','projected geometry preserved after orbit/zoom/pan','round-trip camera and field','bounded limitations','visible provenance','single case and empty group','offline/no errors/no time controls']}));
  } finally {await browser.close();fs.rmSync(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exit(1);});
