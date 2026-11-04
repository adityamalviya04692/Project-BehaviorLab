import {setupShell, $, loadSample} from './shared.js';
setupShell();
const stage=$('#swarm-stage'), layer=$('#cursor-layer'), reduce=matchMedia('(prefers-reduced-motion: reduce)');
let paused=reduce.matches, animations=[], visible=true, timer, tick=0, total=128;
const colors=['#28766c','#547c90','#a87946','#7f6e91','#6a8272'];
const labels=['visitor_012','visitor_024','visitor_048','visitor_096','visitor_128','visitor_203'];
const cursors=Array.from({length:30},(_,i)=>{
 const el=document.createElement('div');el.className='swarm-cursor';el.style.color=colors[i%colors.length];
 el.innerHTML=`<svg viewBox="0 0 24 30"><path d="M2 2L21 17L12 18L8 27Z" fill="currentColor" stroke="white" stroke-width="1.5"/></svg>${i<6?`<span>${labels[i]}</span>`:''}`;
 layer.append(el);return el;
});
function buildMotion(){
 animations.forEach(a=>a.cancel());animations=[];
 const width=stage.clientWidth,height=stage.clientHeight;
 // Bounded visual crowd: thirty representatives, never millions of DOM nodes.
 cursors.forEach((el,i)=>{
  const targetX=width*(.13+((i*17)%25)/100),targetY=height*(.32+((i*13)%39)/100);
  const startX=width*((i*37%100)/100),startY=height*((i*23%90)/100);
  el.style.transform=`translate(${targetX}px,${targetY}px)`;
  const animation=el.animate([
   {transform:`translate(${startX}px,${startY}px)`,opacity:0,offset:0},
   {transform:`translate(${startX}px,${startY}px)`,opacity:.8,offset:.08},
   {transform:`translate(${targetX}px,${targetY}px)`,opacity:1,offset:.43},
   {transform:`translate(${targetX}px,${targetY}px) scale(.88)`,opacity:1,offset:.48},
   {transform:`translate(${targetX+12}px,${targetY-7}px) scale(1)`,opacity:.9,offset:.56},
   {transform:`translate(${width*.83}px,${height*(.25+(i%5)*.1)}px)`,opacity:0,offset:1}
  ],{duration:7000+(i%7)*650,delay:-i*430,iterations:Infinity,easing:'cubic-bezier(0.77, 0, 0.175, 1)'});
  animations.push(animation);
 });
 sync();
}
function sync(){
 const stopped=paused||document.hidden||!visible;
 animations.forEach(a=>stopped?a.pause():a.play());
 $('#pause-swarm').textContent=paused?'Play animation ▷':'Pause animation Ⅱ';
 $('#pause-swarm').setAttribute('aria-pressed',String(paused));
 clearInterval(timer);
 if(!stopped)timer=setInterval(updateSignals,1300);
}
function updateSignals(){
 tick++;total+=3+tick%7;
 const topics=['design','travel','food','technology'],actions=['content_view','bookmark_add','like_add'];
 $('#hero-count').textContent=total.toLocaleString();$('#hero-event').textContent=actions[tick%3];
 $('#hero-topic').textContent='behavior.'+topics[tick%4];$('#hero-user').textContent=labels[tick%labels.length];
 ['design','travel','food'].forEach((t,i)=>$('#'+t+'-count').textContent=Math.floor(total*(.29-i*.04)));
 const points=Array.from({length:9},(_,i)=>[i*30,85-i*7+Math.sin((tick+i)*.8)*9]);
 const line=points.map(([x,y],i)=>`${i?'L':'M'}${x} ${y}`).join(' ');
 $('#swarm-line').setAttribute('d',line);$('#swarm-area').setAttribute('d',line+' L240 105 L0 105 Z');
}
$('#pause-swarm').onclick=()=>{paused=!paused;sync()};
reduce.addEventListener('change',()=>{paused=reduce.matches;sync()});
document.addEventListener('visibilitychange',sync);
new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync()},{threshold:.1}).observe(stage);
let resizeTimer;new ResizeObserver(()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(buildMotion,120)}).observe(stage);
$('#load-audience').onclick=async()=>{try {await loadSample($('#load-audience'));$('#seed-status').innerHTML='Sample queued. <a href="/architecture">Watch the pipeline →</a> or <a href="/insights">explore the audience →</a>'}catch{}};
buildMotion();
