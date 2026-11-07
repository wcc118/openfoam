import {launchBrowser} from './behavior_browser_session.mjs';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
if(process.argv.length<4)throw new Error('Usage: node tests/behavior_browser.mjs BUILT_VIEWER_DIR AUDIT_OUTPUT_DIR');
const input=path.resolve(process.argv[2]),base=path.resolve(process.argv[3]);await mkdir(base,{recursive:true});
const d=JSON.parse(await readFile(input+'/data.json','utf8'));
const b=await launchBrowser(pathToFileURL(input+'/index.html').href);let cases=0;
try{
for(let i=0;i<20;i++){
 const r=await b.evaluate(`(()=>{const e=document.getElementById('speedSelect');e.value=${i};e.dispatchEvent(new Event('change'));return {q:behaviorQA.snapshot(),tip:document.getElementById('tipMetric').textContent,motionHidden:document.getElementById('motionControls').hidden,cfdDisabled:document.getElementById('cfdSelect').disabled};})()`);
 assert.equal(r.q.speed,d.speeds[i].speed_kn);assert.equal(r.q.scale,1);assert.equal(r.q.perturb,1);assert.equal(r.motionHidden,!d.speeds[i].transient);assert.equal(r.cfdDisabled,!d.speeds[i].cfd.length);
 for(const n of [0,10,768,1567])for(let a=0;a<3;a++){let v=d.geometry.points_m[n][a];for(let m=0;m<20;m++)v+=d.geometry.basis_xyz_per_q[m][n][a]*d.speeds[i].uvlm.q[m];assert.ok(Math.abs(r.q.points[n][a]-v)<1e-12);}
 for(let j=0;j<d.speeds[i].cfd.length;j++){const result=await b.evaluate(`(()=>{const e=document.getElementById('cfdSelect');e.value=${j};e.dispatchEvent(new Event('change'));return {lift:document.getElementById('cfdLiftCompare').textContent,status:document.getElementById('statusList').textContent};})()`);assert.equal(result.lift,d.speeds[i].cfd[j].lift_lbf.toFixed(3)+' lbf');for(const status of d.speeds[i].cfd[j].status)assert.ok(result.status.includes(status));cases++;}
}
for(const i of [0,9,19]){const t=d.speeds[i].transient,k=333,tm=t.time_s[k];const r=await b.evaluate(`(()=>{const e=document.getElementById('speedSelect');e.value=${i};e.dispatchEvent(new Event('change'));document.getElementById('motionEnabled').click();const z=document.getElementById('deformScale');z.value=5;z.dispatchEvent(new Event('change'));const p=document.getElementById('perturbScale');p.value=100;p.dispatchEvent(new Event('change'));const s=document.getElementById('motionTime');s.value=${tm};s.dispatchEvent(new Event('input'));return behaviorQA.snapshot();})()`);
// Slider rounds to its stated step: independently interpolate retained samples at the actual UI time.
let lo=0;while(lo<t.time_s.length-2&&t.time_s[lo+1]<=r.time)lo++;let f=(r.time-t.time_s[lo])/(t.time_s[lo+1]-t.time_s[lo]);for(const n of [0,10,768,1567])for(let a=0;a<3;a++){let v=d.geometry.points_m[n][a];for(let m=0;m<20;m++)v+=d.geometry.basis_xyz_per_q[m][n][a]*(5*d.speeds[i].uvlm.q[m]+100*(t.q_delta[lo][m]+f*(t.q_delta[lo+1][m]-t.q_delta[lo][m])));assert.ok(Math.abs(r.points[n][a]-v)<1e-12);}}
await b.evaluate(`document.getElementById('playMotion').click()`);await new Promise(r=>setTimeout(r,300));let playing=await b.evaluate('behaviorQA.snapshot()');assert.ok(playing.playing);await b.evaluate(`document.getElementById('speedSelect').value=1;document.getElementById('speedSelect').dispatchEvent(new Event('change'))`);assert.equal((await b.evaluate('behaviorQA.snapshot()')).playing,false);
await b.evaluate(`document.getElementById('speedSelect').value=0;document.getElementById('speedSelect').dispatchEvent(new Event('change'));document.getElementById('deformScale').value=1;document.getElementById('deformScale').dispatchEvent(new Event('change'));document.getElementById('perturbScale').value=1;document.getElementById('resetCamera').click()`);
await b.screenshot(base+'/desktop.png');await b.send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});await b.screenshot(base+'/mobile.png');assert.equal(await b.evaluate('document.documentElement.scrollWidth<=window.innerWidth'),true);
const errors=b.events.filter(e=>e.method==='Runtime.exceptionThrown');assert.deepEqual(errors,[]);const external=b.events.filter(e=>e.method==='Network.requestWillBeSent'&&/^https?:/.test(e.params.request.url));assert.deepEqual(external,[]);await writeFile(base+'/browser-audit.json',JSON.stringify({passed:true,speeds:20,cfdCases:cases,transientReconstructions:3,externalRequests:external.length,browserErrors:errors.length},null,2));console.log('PASS all speeds, CFD cases, vector scaling, recorded motion, missing states, offline desktop/mobile');
}finally{await b.close();}
