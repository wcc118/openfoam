const {chromium}=require(process.argv[2]);
const fs=require('node:fs'),assert=require('node:assert/strict'),path=require('node:path');
(async()=>{
 const dir=process.argv[6],html=path.resolve(process.argv[4]),input=JSON.parse(fs.readFileSync(process.argv[5],'utf8'));fs.mkdirSync(dir,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.argv[3],args:['--enable-unsafe-swiftshader','--use-angle=swiftshader']});
 try{
 const page=await browser.newPage({viewport:{width:1500,height:1200}}),errors=[],network=[],consoleErrors=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith('file:'))network.push(r.url());});page.on('console',m=>{if(m.type()==='error')consoleErrors.push(m.text());});
 const start=Date.now();await page.goto('file://'+html,{timeout:120000,waitUntil:'load'});await page.waitForFunction(()=>window.flow3dTest,{timeout:120000});
 const loadMs=Date.now()-start;const evidence=await page.evaluate(()=>{
 const t=window.flow3dTest,d=t.data,a=t.actors;
 return {points:d.paths.points.length/3,surfaceTriangles:d.vortex.speed.length,volumeNodes:d.volume.speed.length,visibility:Object.fromEntries(Object.entries(a).map(([k,v])=>[k,v.getVisibility()])),volumeDims:a.volume.getMapper().getInputData().getDimensions(),volumeRange:a.volume.getMapper().getInputData().getPointData().getScalars().getRange(),vortexScalarMode:a.vortex.getMapper().getScalarMode(),actors:t.renderer.getActors().length};
 });
 assert.equal(evidence.points,input.paths.points.length/3);assert.equal(evidence.surfaceTriangles,input.vortex.speed.length);assert.deepEqual(evidence.volumeDims,input.volume.dimensions);assert.equal(evidence.volumeNodes,input.volume.speed.length);assert.equal(evidence.volumeRange[0],-1);assert.equal(evidence.visibility.volume,false);
 assert.equal(await page.evaluate(()=>window.PWNED),undefined);
 const scalarCheck=await page.evaluate(()=>{const t=flow3dTest,d=t.data,a=t.actors;const same=(x,y)=>x.length===y.length&&x.every((v,i)=>v===Math.fround(y[i]));const allowed=new Set(new Float32Array(d.paths.speed)),rendered=a.paths.getMapper().getInputData().getPointData().getScalars().getData();return {paths:rendered.length>0&&rendered.every(v=>allowed.has(v)),vortex:same(a.vortex.getMapper().getInputData().getCellData().getScalars().getData(),d.vortex.speed),volume:same(a.volume.getMapper().getInputData().getPointData().getScalars().getData(),d.volume.speed),maskOpacity:t.opacity.getValue(-1),nearest:a.volume.getProperty().getInterpolationType()===0};});assert.deepEqual(scalarCheck,{paths:true,vortex:true,volume:true,maskOpacity:0,nearest:true});
 const region=page.locator('#render-container');const shot=()=>region.screenshot({timeout:120000});const initial=await shot();fs.writeFileSync(path.join(dir,'paths-surface.png'),initial);
 await page.locator('#show-paths').uncheck();assert.notDeepEqual(initial,await shot(),'paths must affect pixels');await page.locator('#show-paths').check();
 await page.locator('#show-vortex').uncheck();const paths=await shot();assert.notDeepEqual(initial,paths,'surface must affect pixels');
 await page.locator('#show-volume').check();const volume=await shot();assert.notDeepEqual(paths,volume,'volume must affect pixels');fs.writeFileSync(path.join(dir,'paths-volume.png'),volume);
 await page.locator('#volume-opacity').fill('60');await page.locator('#volume-opacity').dispatchEvent('input');assert.notDeepEqual(volume,await shot(),'opacity must affect pixels');
 await page.locator('#hide-freestream').uncheck();assert.ok(await page.evaluate(()=>flow3dTest.opacity.getValue(30))>0);await page.locator('#hide-freestream').check();assert.equal(await page.evaluate(()=>flow3dTest.opacity.getValue(30)),0);
 await page.locator('#show-volume').uncheck();await page.locator('#show-vortex').check();await page.locator('#reset-btn').click();const reset=await shot();await page.locator('#reset-btn').click();assert.deepEqual(reset,await shot(),'reset idempotent');
 const box=await region.boundingBox();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.5+80,box.y+box.height*.5+40,{steps:6});await page.mouse.up();assert.notDeepEqual(reset,await shot(),'orbit must affect pixels');
 await page.locator('#reset-btn').click();await page.screenshot({path:path.join(dir,'viewer-full.png'),fullPage:true,timeout:120000});
 assert.deepEqual(errors,[]);assert.deepEqual(consoleErrors,[]);assert.deepEqual(network,[]);
 await page.locator('#tip-btn').click();const tip=await shot();assert.notDeepEqual(reset,tip);await page.locator('#tip-btn').click();assert.deepEqual(tip,await shot());fs.writeFileSync(path.join(dir,'right-tip.png'),tip);
 const embedded=JSON.parse(await page.locator('#flow-data').textContent());assert.deepEqual(embedded,input);
 fs.writeFileSync(path.join(dir,'browser-verification.json'),JSON.stringify({status:'passed',loadMs,evidence,scalarCheck,errors,consoleErrors,network,nativePackageEqual:true},null,2));console.log(JSON.stringify({status:'passed',loadMs,evidence}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
