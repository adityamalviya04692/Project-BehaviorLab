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
 if(!stopped)timer=setInterval(updateSignals,2900);
}
const scenes=[
 ['Events','North Summit 2026','Toronto · Dec 8','View event','content_view','behavior.conferences'],
 ['Event details','North Summit 2026','Harbour Hall · General admission','Get tickets · CAD 149','checkout_started','business.commerce'],
 ['Checkout','Two summit passes','Demo total · CAD 298','Place demo order','ticket_purchase','business.commerce'],
 ['Tickets','Your passes are ready','NL-SUMMIT-01 · General admission','Simulate entry','ticket_checkin','business.attendance'],
 ['Event shop','Northline tote','Pickup at Harbour Hall · CAD 32','Buy tote','product_purchase','business.commerce'],
 ['Meetings','Plan with Northline','Dec 1 · 10:00 ET','Book meeting','meeting_booked','business.meetings'],
 ['Event brief','Partner summit','Toronto · 120 guests · Venue and AV','Save brief','event_brief_created','business.planning'],
 ['Organizer','North Summit dashboard','Tickets issued · Entry · Shop sales','View sales','page_view','behavior.navigation'],
];
let sceneIndex=0, counts=[0,0,0];
function showScene(){
 const [label,title,detail,cta]=scenes[sceneIndex];
 $('#mini-scene').innerHTML=`<div class="mini-scene-label">${label} · ${sceneIndex+1}/${scenes.length}</div><div class="mini-event-art"><span>NORTHLINE EVENTS</span><b>${title}</b></div><p>${detail}</p><div class="mini-tap">${cta}</div>`;
}
function updateSignals(){
 const current=scenes[sceneIndex], target=$('.mini-tap').getBoundingClientRect(), bounds=stage.getBoundingClientRect();
 const x=target.right-bounds.left-15,y=target.top-bounds.top+target.height/2;
 const pointer=$('#featured-cursor');
 if(!reduce.matches)pointer.animate([{transform:`translate(${x+35}px,${y-35}px)`,opacity:0},{transform:`translate(${x}px,${y}px)`,opacity:1},{transform:`translate(${x}px,${y}px) scale(.85)`,opacity:0}],{duration:420,easing:'cubic-bezier(.23,1,.32,1)'});
 tick++;total++;
 if(current[4]==='ticket_purchase')counts[0]+=2;
 if(current[4]==='meeting_booked')counts[1]++;
 if(current[4]==='product_purchase')counts[2]++;
 $('#hero-count').textContent=total.toLocaleString();
 $('#hero-event').textContent=current[4];$('#hero-topic').textContent=current[5];$('#hero-user').textContent=labels[tick%labels.length];
 ['design','travel','food'].forEach((t,i)=>$('#'+t+'-count').textContent=counts[i]);
 const points=Array.from({length:9},(_,i)=>[i*30,85-i*7+Math.sin((tick+i)*.8)*9]);
 const line=points.map(([x,y],i)=>`${i?'L':'M'}${x} ${y}`).join(' ');
 $('#swarm-line').setAttribute('d',line);$('#swarm-area').setAttribute('d',line+' L240 105 L0 105 Z');
 sceneIndex=(sceneIndex+1)%scenes.length;showScene();
}
const featured=document.createElement('div');
featured.id='featured-cursor';featured.textContent='➤';layer.append(featured);
showScene();
const next=document.createElement('button');
next.textContent='Next interaction →';next.className='mini-next';
$('.stage-topline').append(next);next.onclick=updateSignals;
$('#pause-swarm').onclick=()=>{paused=!paused;sync()};
reduce.addEventListener('change',()=>{paused=reduce.matches;sync()});
document.addEventListener('visibilitychange',sync);
new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;sync()},{threshold:.1}).observe(stage);
let resizeTimer;new ResizeObserver(()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(buildMotion,120)}).observe(stage);
$('#load-audience').onclick=async()=>{try {await loadSample($('#load-audience'));$('#seed-status').innerHTML='Sample queued. <a href="/architecture">Watch the pipeline →</a> or <a href="/insights">explore the audience →</a>'}catch{}};
buildMotion();
