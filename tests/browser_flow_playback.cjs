const {chromium}=require(process.argv[2] || 'playwright-core');
const assert=require('node:assert/strict');
(async()=>{
 const b=await chromium.launch({executablePath:process.argv[3],headless:true});
 try{
 const page=await b.newPage({viewport:{width:1300,height:1000}});let errors=[];page.on('pageerror',e=>errors.push(e.message));let network=[];page.on('request',r=>{if(!r.url().startsWith('file:'))network.push(r.url());});
 await page.clock.install();await page.goto(process.argv[4]);
 assert.equal(await page.evaluate(()=>window.PWNED),undefined);assert.equal(await page.locator('#frame').inputValue(),'0');
 assert.match(await page.locator('#time').innerText(),/frame 1\/3/);
 await page.locator('#field').selectOption('cp');assert.equal(await page.locator('#legendMin').innerText(),'-1.000');assert.equal(await page.locator('#legendMax').innerText(),'1.000');
 const shot0=await page.locator('#scene').screenshot();await page.locator('#view').selectOption('side');const shot1=await page.locator('#scene').screenshot();assert.notDeepEqual(shot0,shot1);
 await page.locator('#group').selectOption('tip');await page.locator('#arrows').check();await page.locator('#next').click();assert.equal(await page.locator('#frame').inputValue(),'1');assert.match(await page.locator('#loadStatus').innerText(),/CL 0.50000/);
 await page.locator('#previous').click();await page.locator('#play').click();await page.clock.runFor(2000);assert.equal(await page.locator('#frame').inputValue(),'0');await page.clock.runFor(1000);assert.equal(await page.locator('#frame').inputValue(),'1');
 await page.locator('#play').click();await page.clock.runFor(5000);assert.equal(await page.locator('#frame').inputValue(),'1');
 await page.locator('#frame').fill('2');await page.locator('#frame').dispatchEvent('input');assert.match(await page.locator('#time').innerText(),/frame 3\/3/);
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 if(process.argv[5]) await page.screenshot({path:process.argv[5],fullPage:true});
 console.log(JSON.stringify({status:'passed',checks:['offline local file','metadata injection inert','Cp analytical range','view changes render','group/arrows controls','nearest load sample','irregular-time playback','pause','scrub','no browser errors','no external requests']}));
 }finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
