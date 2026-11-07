import {spawn} from 'node:child_process';
import {mkdtemp,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
export async function launchBrowser(url) {
 const profile=await mkdtemp(path.join(tmpdir(),'openfoam-behavior-browser-'));
 const proc=spawn('/usr/bin/google-chrome',['--headless','--no-sandbox','--disable-gpu','--disable-background-networking','--remote-debugging-port=0',`--user-data-dir=${profile}`,'--allow-file-access-from-files','--window-size=1440,1100','about:blank'],{stdio:['ignore','ignore','pipe']});
 let stderr='';
 const port=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(new Error('Chrome debug startup timeout')),15000);proc.stderr.on('data',chunk=>{stderr+=chunk.toString();const m=stderr.match(/DevTools listening on ws:\/\/127\.0\.0\.1:(\d+)/);if(m){clearTimeout(timeout);resolve(m[1]);}});proc.on('exit',c=>reject(new Error('Chrome exited '+c)));});
 const pages=await(await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const socket=new WebSocket(pages.find(p=>p.type==='page').webSocketDebuggerUrl);
 await new Promise((resolve,reject)=>{socket.addEventListener('open',resolve,{once:true});socket.addEventListener('error',reject,{once:true});});
 let serial=0;const pending=new Map();const events=[];
 socket.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(!p)return;pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}else events.push(m);});
 function send(method,params={}){return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout '+method));},15000);pending.set(id,{resolve,reject,timer});socket.send(JSON.stringify({id,method,params}));});}
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setBlockedURLs',{urls:['http://*','https://*']});await send('Page.navigate',{url});
 async function evaluate(expression){const r=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
 for(let i=0;i<100;i++){await new Promise(r=>setTimeout(r,100));if(await evaluate('document.readyState')==='complete')break;}
 return {proc,profile,events,send,evaluate,async screenshot(file){const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await writeFile(file,Buffer.from(r.data,'base64'));return r.data;},async close(){socket.close();proc.kill('SIGTERM');await new Promise(resolve=>{if(proc.exitCode!==null)resolve();else proc.once('exit',resolve);});}};
}
