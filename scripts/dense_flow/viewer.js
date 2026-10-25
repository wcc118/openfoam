'use strict';
(() => {
const data=JSON.parse(document.getElementById('slice-data').textContent), $=id=>document.getElementById(id);
const points=data.samples.points, slices=data.slices, cases=data.cases, canvas=$('scene');
let ci=0, si=Math.max(0,slices.findIndex(s=>s.normal_axis===0)), yaw=-1.1,pitch=-.7,zoom=1,pan=[0,0],focus='slice',drag=null;
const colors=[[36,59,130],[38,124,186],[53,201,164],[244,214,92],[236,88,60]];
function color(value,range){const t=range[1]===range[0]?0:Math.max(0,Math.min(1,(value-range[0])/(range[1]-range[0])))*4,k=Math.min(3,Math.floor(t)),f=t-k;return `rgb(${colors[k].map((v,i)=>Math.round(v+(colors[k+1][i]-v)*f)).join(',')})`;}
function rotate(p){const x=p[0]*Math.cos(yaw)-p[1]*Math.sin(yaw),y=p[0]*Math.sin(yaw)+p[1]*Math.cos(yaw);return [x,-y*Math.cos(pitch)+p[2]*Math.sin(pitch),y*Math.sin(pitch)+p[2]*Math.cos(pitch)];}
function corners(s){return [0,s.u_values.length-1].flatMap(i=>[0,s.v_values.length-1].map(j=>{const p=[0,0,0];p[s.normal_axis]=s.position_m;p[s.u_axis]=s.u_values[i];p[s.v_axis]=s.v_values[j];return p;}));}
function camera(w,h){const fit=(focus==='wing'?data.wing.points:corners(slices[si])).map(rotate),lo=[Infinity,Infinity],hi=[-Infinity,-Infinity];for(const p of fit)for(let k=0;k<2;k++){lo[k]=Math.min(lo[k],p[k]);hi[k]=Math.max(hi[k],p[k]);}const scale=Math.min((w-100)/Math.max(hi[0]-lo[0],.03),(h-90)/Math.max(hi[1]-lo[1],.03))*zoom;return p=>{const q=rotate(p);return [(q[0]-(lo[0]+hi[0])/2)*scale+w/2+pan[0],(q[1]-(lo[1]+hi[1])/2)*scale+h/2+pan[1],q[2]];};}
function normalView(){const a=slices[si].normal_axis;[yaw,pitch]=a===0?[-Math.PI/2,-Math.PI/2]:a===1?[0,-Math.PI/2]:[0,0];}
function resetCamera(){zoom=1;pan=[0,0];}
function changeSlice(i){si=i;$('slice').value=String(si);$('sliceIndex').value=String(si);if($('view').value==='normal')normalView();resetCamera();draw();}
function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.appendChild(o);}
cases.forEach((c,i)=>option($('angle'),i,`${c.alpha_deg}°`));slices.forEach((s,i)=>option($('slice'),i,s.label));$('sliceIndex').max=slices.length-1;$('slice').value=si;$('sliceIndex').value=si;
$('angle').onchange=()=>{ci=Number($('angle').value);draw();};$('slice').onchange=()=>changeSlice(Number($('slice').value));$('sliceIndex').oninput=()=>changeSlice(Number($('sliceIndex').value));
for(const id of ['field','vector','density','arrows'])$(id).onchange=()=>draw();$('wingOpacity').oninput=()=>draw();
$('focusSlice').onclick=()=>{focus='slice';resetCamera();draw();};$('fitWing').onclick=()=>{focus='wing';resetCamera();draw();};
$('view').onchange=()=>{const v=$('view').value;if(v==='normal'){normalView();focus='slice';}else [yaw,pitch]=({iso:[-1.1,-.7],top:[0,0],side:[0,-Math.PI/2],tip:[-Math.PI/2,-Math.PI/2]})[v];resetCamera();draw();};
$('reset').onclick=()=>{focus='slice';yaw=-1.1;pitch=-.7;$('view').value='iso';resetCamera();draw();};
// Cached scalar values and quads are independent of camera and arrow density.
const scalarCache=new Map(), quadCache=new Map();
function scalars(){const key=ci+':'+$('field').value;if(!scalarCache.has(key)){const c=cases[ci],f=$('field').value;scalarCache.set(key,points.map((_,i)=>f==='speed'?Math.hypot(...c.U[i]):f==='cp'?(c.p[i]-data.reference.reference_pressure_kinematic)/data.reference.dynamic_pressure_kinematic:Math.hypot(c.U[i][1]-c.freestream_velocity_m_s[1],c.U[i][2]-c.freestream_velocity_m_s[2])));}return scalarCache.get(key);}
function quads(){if(!quadCache.has(si)){const s=slices[si],n=s.u_values.length,out=[];for(let r=0;r<s.v_values.length-1;r++)for(let col=0;col<n-1;col++){const ids=[s.indices[r*n+col],s.indices[r*n+col+1],s.indices[(r+1)*n+col+1],s.indices[(r+1)*n+col]];if(ids.every(i=>i>=0))out.push(ids);}quadCache.set(si,out);}return quadCache.get(si);}
function draw(){
 const box=canvas.getBoundingClientRect(),w=Math.round(box.width),h=Math.round(box.height),dpr=Math.min(devicePixelRatio||1,2);if(canvas.width!==w*dpr||canvas.height!==h*dpr){canvas.width=w*dpr;canvas.height=h*dpr;}const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 const project=camera(w,h),s=slices[si],c=cases[ci],values=scalars(),range=data.color_ranges[$('field').value],items=[],alpha=Number($('wingOpacity').value),projected=new Map();
 const pp=i=>{if(!projected.has(i))projected.set(i,project(points[i]));return projected.get(i);};
 for(const ids of quads()){const q=ids.map(pp);items.push({q,depth:q.reduce((a,p)=>a+p[2],0)/4,color:color(ids.reduce((a,i)=>a+values[i]/4,0),range),alpha:1});}
 if(alpha>0)for(const tri of data.wing.triangles){const q=tri.map(i=>project(data.wing.points[i]));items.push({q,depth:q.reduce((a,p)=>a+p[2],0)/3,color:'#788ea8',alpha});}
 items.sort((a,b)=>a.depth-b.depth);for(const item of items){ctx.globalAlpha=item.alpha;ctx.fillStyle=item.color;ctx.beginPath();item.q.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fill();}ctx.globalAlpha=1;
 // Arrows are an explicit overlay on the selected plane, visible through the wing.
 const cross=$('vector').value==='crossflow',scale=cross?.003:.0007,n=s.u_values.length,step=Math.max(1,Math.ceil(Math.max(n,s.v_values.length)/({low:12,medium:22,high:38}[$('density').value])));
 if($('arrows').checked)for(let r=0;r<s.v_values.length;r+=step)for(let col=0;col<n;col+=step){const i=s.indices[r*n+col];if(i<0)continue;const p=points[i],u=cross?[0,c.U[i][1]-c.freestream_velocity_m_s[1],c.U[i][2]-c.freestream_velocity_m_s[2]]:c.U[i],a=pp(i),b=project(p.map((v,k)=>v+u[k]*scale)),dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);if(len<1||a[0]<0||a[0]>w||a[1]<0||a[1]>h)continue;const head=Math.min(5,len*.35);ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.lineTo(b[0]-dx/len*head-dy/len*head*.55,b[1]-dy/len*head+dx/len*head*.55);ctx.moveTo(b[0],b[1]);ctx.lineTo(b[0]-dx/len*head+dy/len*head*.55,b[1]-dy/len*head-dx/len*head*.55);ctx.strokeStyle='#102033';ctx.lineWidth=2.7;ctx.stroke();ctx.strokeStyle='#ffffff';ctx.lineWidth=1.1;ctx.stroke();}
 for(const [label,p,col] of [['x',[1,0,0],'#ff8d82'],['y',[0,1,0],'#8ce1a0'],['z',[0,0,1],'#88d5ff']]){const q=rotate(p);ctx.strokeStyle=col;ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(40,h-40);ctx.lineTo(40+q[0]*30,h-40+q[1]*30);ctx.stroke();ctx.fillText(label,40+q[0]*42,h-40+q[1]*42);}
 $('legendMin').textContent=range[0].toPrecision(4);$('legendMax').textContent=range[1].toPrecision(4);$('legendUnits').textContent=({'speed':'Total speed (m/s)','cp':'Cp','crossflow':'Induced crossflow magnitude (m/s)'})[$('field').value]+' · fixed across angles';
 $('vectorLegend').textContent=`${cross?'Induced crossflow':'Total velocity'} arrows: 1 m/s = ${scale*1000} mm in model coordinates. Display overlay through wing; fixed scale across angles, not particle paths.`;
 $('scope').textContent=`${c.alpha_deg}° · ${s.label} · steady iteration ${c.steady_iteration} (not physical time)`;
 $('provenance').textContent=`Solver: ${c.solver}\nRevision: ${c.source_revision}\nMesh SHA256: ${c.mesh_sha256}\nField SHA256: ${c.field_sha256}\nSamples/case: ${points.length}`;
 $('limitations').replaceChildren(...c.limitations.map(t=>{const li=document.createElement('li');li.textContent=t;return li;}));
}
canvas.onpointerdown=e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);};canvas.onpointermove=e=>{if(!drag)return;const dx=e.clientX-drag[0],dy=e.clientY-drag[1];if(e.shiftKey){pan[0]+=dx;pan[1]+=dy;}else{yaw+=dx*.008;pitch+=dy*.008;}drag=[e.clientX,e.clientY];draw();};canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.2,Math.min(15,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});window.addEventListener('resize',draw);draw();
})();
