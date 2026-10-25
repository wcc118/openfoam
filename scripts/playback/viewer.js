'use strict';
(() => {
const data = JSON.parse(document.getElementById('flow-data').textContent);
const $ = id => document.getElementById(id);
const frames = data.frames, points = data.samples.points, groups = data.samples.groups;
let index = 0, playing = false, epoch = 0, origin = frames[0].time_s, raf = 0;
let yaw = -0.7, pitch = 1.0, zoom = 1, pan = [0,0], drag = null;
const duration = frames.at(-1).time_s - frames[0].time_s;
const secondsPerWallSecond = duration / 10; // Full saved physical interval occupies ten wall seconds at Normal.
const scene = $('scene'), history = $('history');
$('meta').textContent = `${data.run.id} · ${data.run.solver} · source ${data.run.source_revision}`;
$('scope').textContent = `${frames.length} saved frames; ${points.length.toLocaleString()} fixed sample points. Read the limitations before interpreting this initial flow segment.`;
for (const text of data.run.limitations) { const li=document.createElement('li'); li.textContent=text; $('limitations').append(li); }
$('frame').max = frames.length-1;
function dimensions(canvas) {
 const box=canvas.getBoundingClientRect(), dpr=Math.min(devicePixelRatio || 1,2);
 const w=Math.round(box.width), h=Math.round(box.height);
 if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}
 const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return [ctx,w,h];
}
function rotated(p) {
 const x=p[0]*Math.cos(yaw)-p[1]*Math.sin(yaw), y=p[0]*Math.sin(yaw)+p[1]*Math.cos(yaw);
 return [x,-(y*Math.cos(pitch)-p[2]*Math.sin(pitch)),y*Math.sin(pitch)+p[2]*Math.cos(pitch)];
}
function color(v,range) {
 const t=range[1]===range[0]?0.5:Math.max(0,Math.min(1,(v-range[0])/(range[1]-range[0])));
 return `hsl(${240*(1-t)},85%,58%)`;
}
function camera(w,h) {
 const g=$('group').value;
 const selected=points.filter((p,i)=>g==='all'||groups[i]===g);
 const fit=(g==='all'?selected.concat(data.wing.points):selected).map(rotated);
 const lo=[Infinity,Infinity],hi=[-Infinity,-Infinity];
 for(const p of fit)for(let k=0;k<2;k++){lo[k]=Math.min(lo[k],p[k]);hi[k]=Math.max(hi[k],p[k]);}
 const scale=Math.min((w-70)/Math.max(hi[0]-lo[0],0.03),(h-70)/Math.max(hi[1]-lo[1],0.03))*zoom;
 return {scale,project(p){const r=rotated(p);return [(r[0]-(lo[0]+hi[0])/2)*scale+w/2+pan[0],(r[1]-(lo[1]+hi[1])/2)*scale+h/2+pan[1],r[2]];}};
}
function drawScene() {
 const [ctx,w,h]=dimensions(scene);ctx.clearRect(0,0,w,h);
 const cam=camera(w,h), f=frames[index], field=$('field').value, range=data.color_ranges[field], g=$('group').value;
 const wp=data.wing.points.map(cam.project), items=[];
 for(const tri of data.wing.triangles){const p=tri.map(i=>wp[i]);items.push({depth:p.reduce((a,v)=>a+v[2],0)/3,tri:p});}
 const stride=Math.max(1,Math.ceil(points.length/180));
 for(let i=0;i<points.length;i++) {
  if(g!=='all'&&groups[i]!==g)continue;
  const q=cam.project(points[i]);if(q[0]<-30||q[0]>w+30||q[1]<-30||q[1]>h+30)continue;
  const val=field==='speed'?Math.hypot(...f.U[i]):(f.p[i]-data.run.reference_pressure_kinematic)/data.run.dynamic_pressure_kinematic;
  items.push({depth:q[2],q,i,col:color(val,range),arrow:$('arrows').checked&&i%stride===0});
 }
 items.sort((a,b)=>a.depth-b.depth);
 for(const item of items) {
  if(item.tri){ctx.beginPath();item.tri.forEach((v,j)=>j?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1]));ctx.closePath();ctx.fillStyle='#566b82';ctx.fill();ctx.strokeStyle='#899aaa';ctx.lineWidth=0.25;ctx.stroke();}
  else {
   const [x,y]=item.q;ctx.fillStyle=item.col;ctx.beginPath();ctx.arc(x,y,g==='all'?2.0:2.7,0,Math.PI*2);ctx.fill();
   if(item.arrow){const p=points[item.i],u=f.U[item.i],end=cam.project(p.map((v,k)=>v+u[k]*0.0007));const dx=end[0]-x,dy=end[1]-y,L=Math.hypot(dx,dy);if(L>2){ctx.strokeStyle=item.col;ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(end[0],end[1]);ctx.moveTo(end[0]-dx/L*5-dy/L*3,end[1]-dy/L*5+dx/L*3);ctx.lineTo(end[0],end[1]);ctx.lineTo(end[0]-dx/L*5+dy/L*3,end[1]-dy/L*5-dx/L*3);ctx.stroke();}}
  }
 }
 const base=[45,h-45];[['x',[1,0,0],'#ff8a80'],['y',[0,1,0],'#8ee5a4'],['z',[0,0,1],'#8acaff']].forEach(([name,v,col])=>{const r=rotated(v);ctx.strokeStyle=col;ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(...base);ctx.lineTo(base[0]+r[0]*30,base[1]+r[1]*30);ctx.stroke();ctx.font='13px system-ui';ctx.fillText(name,base[0]+r[0]*39,base[1]+r[1]*39);});
 $('legendMin').textContent=range[0].toPrecision(4);$('legendMax').textContent=range[1].toPrecision(4);$('legendUnits').textContent=field==='speed'?'m/s · fixed across all frames':'Cp · fixed across all frames';
}
function drawHistory() {
 const [ctx,w,h]=dimensions(history);ctx.clearRect(0,0,w,h);
 if(!data.loads.length){$('loadStatus').textContent='Load history unavailable for this input.';return;}
 const current=frames[index].time_s, loads=data.loads;
 let nearest=loads[0];for(const r of loads)if(Math.abs(r.time_s-current)<Math.abs(nearest.time_s-current))nearest=r;
 $('loadStatus').textContent=`Nearest saved load sample: ${(nearest.time_s*1000).toPrecision(7)} ms · CL ${nearest.CL.toFixed(5)} · CD ${nearest.CD.toFixed(5)} · Cm ${nearest.Cm.toFixed(5)}. Cursor marks the selected CFD frame time.`;
 const t0=Math.min(loads[0].time_s,frames[0].time_s),t1=Math.max(loads.at(-1).time_s,frames.at(-1).time_s);
 ['CL','CD','Cm'].forEach((key,panel)=>{
  const left=panel*w/3+55,right=(panel+1)*w/3-20,top=25,bottom=h-42;
  let low=Infinity,high=-Infinity;for(const r of loads){low=Math.min(low,r[key]);high=Math.max(high,r[key]);}
  const pad=Math.max((high-low)*0.1,1e-6);low-=pad;high+=pad;
  const x=t=>left+(t-t0)/(t1-t0)*(right-left),y=v=>bottom-(v-low)/(high-low)*(bottom-top);
  ctx.strokeStyle='#496078';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,bottom);ctx.lineTo(right,bottom);ctx.stroke();
  ctx.font='12px system-ui';ctx.fillStyle='#bacbdb';ctx.fillText(key,left,16);ctx.fillText(high.toPrecision(3),left-49,top+5);ctx.fillText(low.toPrecision(3),left-49,bottom);ctx.fillText((t0*1000).toPrecision(3),left,bottom+18);ctx.fillText((t1*1000).toPrecision(3),right-45,bottom+18);ctx.fillText('Physical time (ms)',left+8,h-4);
  ctx.strokeStyle=['#55d9e9','#f3b85c','#bc9bff'][panel];ctx.lineWidth=1.5;ctx.beginPath();loads.forEach((r,j)=>j?ctx.lineTo(x(r.time_s),y(r[key])):ctx.moveTo(x(r.time_s),y(r[key])));ctx.stroke();
  ctx.strokeStyle='#fff';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(x(current),top);ctx.lineTo(x(current),bottom);ctx.stroke();ctx.setLineDash([]);
 });
}
function draw() {
 $('frame').value=index;const t=frames[index].time_s;
 $('time').textContent=`t = ${(t*1000).toPrecision(8)} ms · tU/c = ${(t*data.run.speed_m_s/data.run.chord_m).toPrecision(5)} · frame ${index+1}/${frames.length}`;
 const rate=Number($('rate').value), slowed=1/(secondsPerWallSecond*rate);
 $('playbackNote').textContent=`Physical interval ${(frames[0].time_s*1000).toPrecision(6)}–${(frames.at(-1).time_s*1000).toPrecision(6)} ms. Playback is slowed by ${slowed.toLocaleString(undefined,{maximumFractionDigits:0})}×; actual irregular frame timing is preserved. Replay repeats this saved segment, not a periodic-flow claim.`;
 drawScene();drawHistory();
}
function pause(){if(raf)cancelAnimationFrame(raf);raf=0;playing=false;$('play').textContent='Play';}
function tick(now) {
 if(!playing)return;
 let target=origin+(now-epoch)/1000*secondsPerWallSecond*Number($('rate').value);
 if(target>=frames.at(-1).time_s){index=frames.length-1;draw();if($('replay').checked){index=0;origin=frames[0].time_s;epoch=now;}else{pause();return;}}
 else {let k=0;while(k+1<frames.length&&frames[k+1].time_s<=target)k++;if(k!==index){index=k;draw();}}
 raf=requestAnimationFrame(tick);
}
$('play').onclick=()=>{if(playing){pause();return;}if(index===frames.length-1)index=0;playing=true;epoch=performance.now();origin=frames[index].time_s;$('play').textContent='Pause';draw();raf=requestAnimationFrame(tick);};
$('frame').oninput=()=>{pause();index=Number($('frame').value);draw();};
$('previous').onclick=()=>{pause();index=Math.max(0,index-1);draw();};
$('next').onclick=()=>{pause();index=Math.min(frames.length-1,index+1);draw();};
$('rate').onchange=()=>{if(playing){origin=frames[index].time_s;epoch=performance.now();}draw();};
$('field').onchange=draw;$('arrows').onchange=draw;
$('group').onchange=()=>{zoom=1;pan=[0,0];draw();};
function preset(){const v=$('view').value;[yaw,pitch]=({iso:[-0.7,1.0],top:[0,0],side:[0,Math.PI/2],tip:[Math.PI/2,Math.PI/2]})[v];zoom=1;pan=[0,0];draw();}
$('view').onchange=preset;$('reset').onclick=()=>{$('view').value='iso';preset();};
scene.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY};scene.setPointerCapture(e.pointerId);};
scene.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(e.shiftKey){pan[0]+=dx;pan[1]+=dy;}else{yaw+=dx*0.008;pitch+=dy*0.008;}drag={x:e.clientX,y:e.clientY};draw();};
scene.onpointerup=scene.onpointercancel=()=>{drag=null;};
scene.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(0.2,Math.min(15,zoom*Math.exp(-e.deltaY*0.001)));draw();},{passive:false});
window.addEventListener('resize',draw);draw();
})();
