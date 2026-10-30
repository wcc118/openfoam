'use strict';
(() => {
const data=JSON.parse(document.getElementById('eq-data').textContent), $=id=>document.getElementById(id);
const {cases,models}=data, nodes=data.mesh.nodes, colors=['#55d9e9','#f0b44d'];
let time=0, playing=false, last=0, raf=0, yaw=-.7, pitch=-1, zoom=1, pan=[0,0], drag=null;
const maxY=Math.max(...nodes.map(p=>p[1])), tips=nodes.map((p,i)=>Math.abs(p[1]-maxY)<1e-9?i:-1).filter(i=>i>=0);
const xc=tips.reduce((s,i)=>s+nodes[i][0],0)/tips.length, zc=tips.reduce((s,i)=>s+nodes[i][2],0)/tips.length;
const den=tips.reduce((s,i)=>s+(nodes[i][0]-xc)**2+(nodes[i][2]-zc)**2,0);
const maps={};
for(const [tag,m] of Object.entries(models)) maps[tag]=m.modes.map(mode=>({
 z:tips.reduce((s,i)=>s+mode[i][2],0)/tips.length/Math.sqrt(2),
 twist:den?tips.reduce((s,i)=>s+(nodes[i][2]-zc)*mode[i][0]-(nodes[i][0]-xc)*mode[i][2],0)/den/Math.sqrt(2)*180/Math.PI:0,
 bound:Math.max(...mode.map(p=>Math.hypot(...p)))/Math.sqrt(2)
}));
const selected=()=>[Number($('leftCase').value),Number($('rightCase').value)];
const relative=()=>$('displayMode').value==='perturbation';
function bounds(){const cs=selected().map(i=>cases[i]);return [Math.max(...cs.map(c=>c.frames[0][0])),Math.min(...cs.map(c=>c.frames.at(-1)[0]))];}
function interp(frames,t){
 if(t<=frames[0][0]) return frames[0].slice(1);
 if(t>=frames.at(-1)[0]) return frames.at(-1).slice(1);
 let lo=0,hi=frames.length-1;
 while(hi-lo>1){const mid=(lo+hi)>>1;if(frames[mid][0]<=t)lo=mid;else hi=mid;}
 const s=(t-frames[lo][0])/(frames[hi][0]-frames[lo][0]);
 return frames[lo].slice(1).map((q,i)=>q+s*(frames[hi][i+1]-q));
}
function effective(q,c){return q.map((v,i)=>v-(relative()?c.reference_q[i]:0));}
function metric(q,tag){return {tip_z_m:q.reduce((s,v,i)=>s+v*maps[tag][i].z,0),twist_degrees:q.reduce((s,v,i)=>s+v*maps[tag][i].twist,0)};}
function displacement(q,tag){return nodes.map((_,i)=>[0,1,2].map(k=>q.reduce((s,v,j)=>s+v*models[tag].modes[j][i][k],0)/Math.sqrt(2)));}
function dimensions(id){const canvas=$(id),r=canvas.getBoundingClientRect(),dpr=Math.min(devicePixelRatio||1,2),w=Math.round(r.width),h=Math.round(r.height);if(canvas.width!==w*dpr||canvas.height!==h*dpr){canvas.width=w*dpr;canvas.height=h*dpr;}const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);return [ctx,w,h];}
function rotate(p){const x=p[0]*Math.cos(yaw)-p[1]*Math.sin(yaw),y=p[0]*Math.sin(yaw)+p[1]*Math.cos(yaw);return [x,-y*Math.cos(pitch)+p[2]*Math.sin(pitch),y*Math.sin(pitch)+p[2]*Math.cos(pitch)];}
function scene(id,c,q,colorRange){
 const [ctx,w,h]=dimensions(id),rot=nodes.map(rotate),lo=[0,1].map(k=>Math.min(...rot.map(p=>p[k]))),hi=[0,1].map(k=>Math.max(...rot.map(p=>p[k])));
 const scale=Math.min((w-70)/Math.max(hi[0]-lo[0],.03),(h-70)/Math.max(hi[1]-lo[1],.03))*.82*zoom;
 const project=p=>{const r=rotate(p);return [(r[0]-(lo[0]+hi[0])/2)*scale+w/2+pan[0],(r[1]-(lo[1]+hi[1])/2)*scale+h/2+pan[1],r[2]];};
 const u=displacement(q,c.model),mag=Number($('defScale').value),pts=nodes.map((p,i)=>project(p.map((v,k)=>v+mag*u[i][k])));
 const polys=data.mesh.quads.map(quad=>({pts:quad.map(i=>pts[i]),depth:quad.reduce((s,i)=>s+pts[i][2],0)/4,value:quad.reduce((s,i)=>s+Math.hypot(...u[i]),0)/4})).sort((a,b)=>a.depth-b.depth);
 for(const p of polys){ctx.beginPath();p.pts.forEach((v,j)=>j?ctx.lineTo(v[0],v[1]):ctx.moveTo(v[0],v[1]));ctx.closePath();ctx.fillStyle=`hsl(${240*(1-Math.min(1,p.value/colorRange))},85%,58%)`;ctx.fill();}
 ctx.strokeStyle='rgba(217,231,239,.15)';ctx.lineWidth=.5;ctx.beginPath();
 for(const quad of data.mesh.quads){quad.forEach((i,j)=>{const p=project(nodes[i]);j?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]);});const p=project(nodes[quad[0]]);ctx.lineTo(p[0],p[1]);}ctx.stroke();
 const origin=[40,h-40];[['x',[1,0,0],'#ff8a80'],['y',[0,1,0],'#8ee5a4'],['z',[0,0,1],'#8acaff']].forEach(([label,v,col])=>{const r=rotate(v);ctx.strokeStyle=col;ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(...origin);ctx.lineTo(origin[0]+30*r[0],origin[1]+30*r[1]);ctx.stroke();ctx.fillText(label,origin[0]+40*r[0],origin[1]+40*r[1]);});
 return {projectionScale:scale};
}
let cacheKey='', histories=[],colorRange=1;
function prepare(){const key=selected().join(',')+relative();if(key===cacheKey)return;cacheKey=key;
 histories=selected().map(i=>{const c=cases[i];return c.frames.map(f=>{const q=effective(f.slice(1),c);return {t:f[0],...metric(q,c.model),bound:q.reduce((s,v,j)=>s+Math.abs(v)*maps[c.model][j].bound,0)};});});
 colorRange=Math.max(1e-9,...histories.flat().map(p=>p.bound));
}
function trace(id,field,factor,unit){
 const [ctx,w,h]=dimensions(id),[t0,t1]=bounds(),values=histories.flat().filter(p=>p.t>=t0&&p.t<=t1).map(p=>p[field]*factor);
 let lo=Math.min(...values),hi=Math.max(...values);const pad=Math.max((hi-lo)*.1,1e-6);lo-=pad;hi+=pad;
 const left=80,right=w-20,top=25,bottom=h-35,x=t=>left+(t-t0)/(t1-t0)*(right-left),y=v=>bottom-(v-lo)/(hi-lo)*(bottom-top);
 ctx.strokeStyle='#496078';ctx.beginPath();ctx.moveTo(left,top);ctx.lineTo(left,bottom);ctx.lineTo(right,bottom);ctx.stroke();ctx.fillStyle='#bacbdb';ctx.font='12px system-ui';ctx.fillText(unit,left,15);ctx.fillText(hi.toPrecision(4),3,top+5);ctx.fillText(lo.toPrecision(4),3,bottom);ctx.fillText(t0.toFixed(3),left,bottom+20);ctx.fillText(t1.toFixed(3)+' s',right-65,bottom+20);
 ctx.save();ctx.beginPath();ctx.rect(left,top,right-left,bottom-top);ctx.clip();
 histories.forEach((hist,i)=>{ctx.strokeStyle=colors[i];ctx.lineWidth=1.7;ctx.beginPath();hist.forEach((p,j)=>j?ctx.lineTo(x(p.t),y(p[field]*factor)):ctx.moveTo(x(p.t),y(p[field]*factor)));ctx.stroke();});
 ctx.strokeStyle='#fff';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(x(time),top);ctx.lineTo(x(time),bottom);ctx.stroke();ctx.restore();ctx.setLineDash([]);
 return {min:lo,max:hi,unit};
}
function draw(){
 prepare();const [t0,t1]=bounds();time=Math.max(t0,Math.min(t1,time));$('scrub').min=t0;$('scrub').max=t1;$('scrub').value=time;$('time').textContent=time.toFixed(6)+' s';
 const states=selected().map((i,j)=>{const c=cases[i],q=effective(interp(c.frames,time),c),m=metric(q,c.model),camera=scene('canvas'+(j+1),c,q,colorRange);
 $('metrics'+j).textContent=`${(m.tip_z_m*1000).toFixed(5)} mm tip z · ${m.twist_degrees.toFixed(6)}° tip twist`;
 const model=models[c.model];$('info'+j).textContent=`${(model.thickness_m*1000).toFixed(3)} mm skin · ${model.mass_kg.toFixed(6)} kg half-wing · ${model.modes.length} modes. ${c.note||''}${c.stopped_at_50mm_guard?' STOPPED at experimental guard.':''}`;
 return {name:c.name,q,...m,...camera};});
 $('legendMin').textContent='0';$('legendMax').textContent=(colorRange*1000).toPrecision(4);$('legendUnits').textContent=`mm actual displacement magnitude · common color range · geometry ${$('defScale').value}×`;
 const axes={z:trace('history','tip_z_m',1000,'Mean tip z (mm)'),twist:trace('twistHistory','twist_degrees',1,'Tip twist (degrees)')};
 $('traceLegend').replaceChildren(...states.map((s,i)=>{const span=document.createElement('span');span.style.color=colors[i];span.textContent=(i?'Right: ':'Left: ')+s.name;return span;}));
 window.comparisonDebug={time,relative:relative(),states,axes,colorRange,playing};
}
function pause(){playing=false;cancelAnimationFrame(raf);$('play').textContent='Play';}
function tick(now){if(!playing)return;time+=(now-last)/1000*Number($('rate').value);last=now;if(time>=bounds()[1]){time=bounds()[1];pause();}draw();if(playing)raf=requestAnimationFrame(tick);}
for(const [id,value] of [['leftCase',0],['rightCase',1]]){cases.forEach((c,i)=>{const opt=document.createElement('option');opt.value=i;opt.textContent=c.name;$(id).appendChild(opt);});$(id).value=Math.min(value,cases.length-1);$(id).onchange=()=>{pause();draw();};}
$('play').onclick=()=>{if(playing)pause();else{if(time>=bounds()[1])time=bounds()[0];playing=true;last=performance.now();$('play').textContent='Pause';raf=requestAnimationFrame(tick);}draw();};
$('restart').onclick=()=>{pause();time=bounds()[0];draw();};$('scrub').oninput=()=>{pause();time=Number($('scrub').value);draw();};
$('displayMode').onchange=draw;$('defScale').oninput=draw;$('rate').onchange=()=>{last=performance.now();};
for(const id of ['canvas1','canvas2']){const c=$(id);c.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY};c.setPointerCapture(e.pointerId);};c.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(e.shiftKey){pan[0]+=dx;pan[1]+=dy;}else{yaw+=dx*.008;pitch+=dy*.008;}drag={x:e.clientX,y:e.clientY};draw();};c.onpointerup=c.onpointercancel=()=>{drag=null;};c.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.2,Math.min(15,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});}
$('title').textContent=data.title;$('meta').textContent='Select two histories. Shared time, camera, magnification and physical trace axes.';$('scope').textContent=data.scope;$('provenance').textContent=data.source;
window.addEventListener('resize',draw);draw();
})();
