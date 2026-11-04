import {api,$,escape as esc,setupShell,loadSample} from './shared.js';
setupShell();
let catalog, state, business, page='discover', selected='c1', filter='All', cart=null, receipt=null, busy=false;
const money = cents => new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD'}).format(cents/100);
const event = id => catalog.find(e=>e.id===id);
const owned = action => business.records.filter(r=>r.action===action && r.user_id===state.user_id);
const action = (label,key) => `<button class="phone-action" data-go="${key}">${label}</button>`;
const art = e => `<div class="event-art ${e.art}"><small>NORTHLINE / CANADA</small><strong>${e.title}</strong></div>`;
const heading = (label,title) => `<div class="eyebrow">${label}</div><h2>${title}</h2>`;
const card = e => `<article class="event-card"><button data-event="${e.id}" class="story-open">${art(e)}<p>${e.city} · ${e.date}</p><b>${money(e.price_cents)} CAD</b></button></article>`;
const selectEvent = () => `<label>Event<select name="event" data-event-select>${catalog.map(e=>`<option value="${e.id}" ${selected===e.id?'selected':''}>${e.title}</option>`).join('')}</select></label>`;
const sales = () => business.records.filter(r=>r.event_id===selected);
const registered = rows => rows.filter(r=>r.action==='ticket_purchase').reduce((n,r)=>n+r.quantity,0);
const entryCode = (id,index) => 'NL-'+id.slice(0,8).toUpperCase()+'-'+index;

function phone(){
  const e=event(selected), rows=sales();
  const screens = {
    discover:()=>heading('CORPORATE EVENTS ACROSS CANADA','Find your next event.')+`<div class="filters">${['All',...Object.keys(state.scores)].map(t=>`<button data-filter="${t}" aria-pressed="${filter===t}">${t}</button>`).join('')}</div>`+catalog.filter(e=>filter==='All'||e.topic===filter).map(card).join(''),
    detail:()=>art(e)+heading(e.topic.toUpperCase(),e.title)+`<p>${e.date} · ${e.time} · ${e.timezone}</p><p>${e.venue}, ${e.city}</p><p>${e.description}</p><p><b>${Math.max(0,e.capacity-registered(rows))} seats available</b></p><h3>Agenda</h3><ul>${e.agenda.map(a=>`<li>${a}</li>`).join('')}</ul><button class="phone-action" data-item="ticket">Get tickets · ${money(e.price_cents)}</button><button class="phone-secondary" data-save>${state.saved.includes(e.id)?'Remove from saved':'Save event'}</button>`+action('Book a planning meeting','meetings'),
    shop:()=>heading('EVENT EXTRAS','Northline shop')+selectEvent()+Object.entries(business.products).map(([id,[name,price]])=>`<article class="phone-card"><b>${name}</b><p>${money(price)} CAD · event pickup</p><button class="phone-action" data-item="${id}">Buy ${name.toLowerCase()}</button></article>`).join(''),
    checkout:()=>heading('DEMO CHECKOUT','Review your order')+`<p>${e.title} · ${e.city}</p><p>${cart==='ticket'?'General admission':business.products[cart][0]} · ${money(cart==='ticket'?e.price_cents:business.products[cart][1])} CAD each</p><form data-form="${cart==='ticket'?'ticket_purchase':'product_purchase'}"><label>Quantity<input type="number" name="quantity" value="1" min="1" max="10" required></label><p id="order-total"></p><button class="phone-action">Place demo order</button></form><p>Demo checkout. No payment details required.</p>`,
    ticket:()=>heading('ORDER CONFIRMED','You’re all set.')+`<p>${esc(receipt?.name)} × ${receipt?.quantity} · ${money(receipt?.total_cents||0)} CAD</p><p>Order ${receipt?.id.slice(0,8).toUpperCase()}</p>`+action('Open tickets & orders','tickets'),
    tickets:()=>heading('YOUR PASSES & PURCHASES','Tickets & orders')+([...owned('ticket_purchase'),...owned('product_purchase')].map(r=>`<article class="phone-card"><b>${event(r.event_id).title}</b><p>${esc(r.name)} × ${r.quantity} · ${money(r.total_cents)} CAD</p>${r.action==='ticket_purchase'?Array.from({length:r.quantity},(_,i)=>`<div class="ticket-entry"><code>${entryCode(r.id,i+1)}</code>${owned('ticket_checkin').some(x=>x.record===r.id&&x.index===i+1)?'<span>Checked in</span>':`<button class="phone-secondary" data-checkin="${r.id}" data-index="${i+1}">Simulate entry</button>`}</div>`).join(''):'<small>Collect at the event shop.</small>'}</article>`).join('')||'<p>Your tickets and orders will appear here after checkout.</p>'),
    meetings:()=>heading('PLAN WITH NORTHLINE','Book a meeting')+`<form data-form="meeting_booked">${selectEvent()}<label>30-minute consultation<select name="slot" required><option value="">Choose a time</option>${business.slots.map(s=>`<option ${business.records.some(r=>r.slot===s)?'disabled':''}>${s}</option>`).join('')}</select></label><button class="phone-action">Book demo meeting</button></form><h3>Your appointments</h3>${owned('meeting_booked').map(r=>`<p>${esc(r.slot)} · ${event(r.event_id).title}</p>`).join('')||'<p>No appointments yet.</p>'}`,
    organize:()=>heading('EVENT PLANNING','Build an event brief')+`<form data-form="event_brief_created">${selectEvent()}<p>Choose a related event, then outline your own.</p><label>Event name<input name="title" maxlength="100" required placeholder="Partner summit"></label><label>City<input name="city" maxlength="60" required placeholder="Toronto"></label><label>Preferred date<input type="date" name="date" required></label><label>Expected guests<input type="number" name="guests" min="1" max="5000" required></label><fieldset id="requirements"><legend>Planning requirements</legend>${['Venue','Catering','AV','Accessibility'].map(x=>`<label>${x}<input name="req:${x}" maxlength="300" placeholder="To be confirmed"></label>`).join('')}</fieldset><button type="button" class="phone-secondary" id="add-requirement">Add requirement</button><button class="phone-action">Save event brief</button></form>`+action('View saved briefs','brief'),
    brief:()=>heading('EVENT PLANNING','Saved briefs')+(owned('event_brief_created').map(r=>`<article class="phone-card"><b>${esc(r.title)}</b><p>${esc(r.city)} · ${esc(r.date)} · ${r.guests} guests</p><ul>${Object.entries(r.requirements).map(([k,v])=>`<li>${esc(k)} · ${esc(v||'To be confirmed')}</li>`).join('')}</ul>${owned('proposal_requested').some(x=>x.record===r.id)?'<small>Demo proposal requested</small>':`<button class="phone-action" data-proposal="${r.id}">Request demo proposal</button>`}</article>`).join('')||'<p>Save a brief to review it here.</p>'),
    dashboard:()=>heading('ORGANIZER WORKSPACE','Event dashboard')+selectEvent()+`<div class="phone-stats"><div><b>${registered(rows)}</b>Tickets issued</div><div><b>${rows.filter(r=>r.action==='ticket_checkin').length}</b>Checked in</div><div><b>${money(rows.reduce((n,r)=>n+(r.total_cents||0),0))}</b>Demo sales</div></div><p>Includes demo activity and any loaded sample audience.</p>`+action('View audience','attendees')+action('View sales','sales')+`<button class="phone-secondary" id="seed-phone">Load sample audience</button>`,
    attendees:()=>heading('ORGANIZER WORKSPACE','Audience & entry')+selectEvent()+(rows.filter(r=>r.action==='ticket_purchase').map(r=>`<article class="phone-card"><b>${esc(r.alias)}</b><p>${r.quantity} issued · ${rows.filter(x=>x.action==='ticket_checkin'&&x.record===r.id).length} checked in · ${r.source}</p></article>`).join('')||'<p>No registrations for this event yet.</p>'),
    sales:()=>heading('ORGANIZER WORKSPACE','Event sales')+selectEvent()+(Object.values(rows.filter(r=>r.total_cents).reduce((a,r)=>{const x=a[r.item]||={name:r.name,quantity:0,total:0};x.quantity+=r.quantity;x.total+=r.total_cents;return a},{})).map(r=>`<article class="phone-card"><b>${esc(r.name)}</b><p>${r.quantity} sold · ${money(r.total)} CAD</p></article>`).join('')||'<p>No demo sales for this event yet.</p>')+`<h3>Purchases by client</h3>`+rows.filter(r=>r.total_cents).map(r=>`<p>${esc(r.alias)} · ${esc(r.name)} × ${r.quantity}</p>`).join(''),
    profile:()=>heading('CLIENT & ORGANIZER TOOLS','Your workspace')+action('Saved events','saved')+action('Book a meeting','meetings')+action('Plan an event','organize')+action('Saved event briefs','brief')+action('Organizer dashboard','dashboard')+'<h3>Suggested events</h3>'+state.recommendations.slice(0,2).map(id=>card(event(id))).join(''),
    saved:()=>heading('YOUR SHORTLIST','Saved events')+(state.saved.map(id=>card(event(id))).join('')||'<p>Save an event to build your shortlist.</p>'),
  };
  $('#screen').innerHTML=(['discover','shop','tickets','profile'].includes(page)?'':`<button class="back" data-go="${['detail','checkout'].includes(page)?'discover':'profile'}">← Back</button>`)+screens[page]();
  $('#phone-nav').innerHTML=[['discover','⌂','Events'],['shop','◇','Shop'],['tickets','▣','Tickets'],['profile','◉','Workspace']].map(([id,icon,label])=>`<button data-go="${id}" class="${page===id?'active':''}"><span>${icon}</span>${label}</button>`).join('');
  total();
}

function total(){
  const el=$('#order-total');
  if(el)el.textContent='Total · '+money(Number($('#screen [name=quantity]').value)*(cart==='ticket'?event(selected).price_cents:business.products[cart][1]))+' CAD';
}
function analytics(){
  $('#scores').innerHTML=Object.entries(state.scores).sort((a,b)=>b[1]-a[1]).map(([name,n])=>`<div class="score"><div><span>${name}</span><b>${n} pts</b></div><div class="track"><span style="width:${state.total?100*n/state.total:0}%"></span></div></div>`).join('');
  const commitments=owned('meeting_booked').length+owned('proposal_requested').length;
  const purchases=owned('ticket_purchase').length+owned('product_purchase').length;
  $('#insight').innerHTML=`<span>CLIENT FOLLOW-UP</span><p>${commitments?'Follow up on the booked meeting or requested proposal.':purchases?'Offer event extras or a relevant follow-up event.':state.saved.length?'Send relevant event information if the client opts in.':'Explore, save, or purchase an event to build evidence.'}</p><small>${purchases} demo orders · ${commitments} explicit follow-up signals</small>`;
  $('#event-count').textContent=state.events.length;$('#count-badge').textContent=state.events.length;$('#views').textContent=state.viewed.length;$('#saves').textContent=state.saved.length;
  $('#event-list').innerHTML=[...state.events].reverse().slice(0,50).map(e=>`<details class="event"><summary><span><b>${e.type}</b><small>${e.content_id?event(e.content_id).title:e.page}</small></span><span>${e.weight>0?'+':''}${e.weight}</span><time>${new Date(e.timestamp).toLocaleTimeString()}</time></summary><pre>${esc(JSON.stringify(e,null,2))}</pre></details>`).join('')||'<div class="empty-stream">Interact with the phone to see events here.</div>';
}
async function signal(type,content_id=null,extra={}){
  state=await api('/api/events',{id:crypto.randomUUID(),type,page,content_id,...extra});
  status(type);
}
async function transact(type,data={}){
  const result=await api('/api/business',{id:crypto.randomUUID(),action:type,event:selected,...data});
  state=result.state;business=result.business;status(type);
  return business.records.find(r=>r.id===result.id);
}
function status(type){
  $('#stage-detail').textContent=type+' → validated → stored → '+(state.pending?'awaiting processing':'profile updated');
}
async function run(fn,scroll=true){
  if(busy||!state)return;busy=true;
  try{await fn();phone();analytics();$('#error').textContent='';if(scroll)$('#screen').scrollTop=0}
  catch(e){$('#error').textContent=e.message;const box=$('#phone-error');if(box)box.textContent=e.message}
  finally{busy=false}
}
document.addEventListener('click',e=>{
  const b=e.target.closest('button');if(!b||!state)return;
  if(b.dataset.go)run(async()=>{page=b.dataset.go;await signal('page_view')});
  if(b.dataset.event)run(async()=>{selected=b.dataset.event;page='detail';await signal('content_view',selected)});
  if(b.dataset.filter)run(async()=>{filter=b.dataset.filter;await signal('topic_filter',null,{filter_value:filter})});
  if(b.hasAttribute('data-save'))run(()=>signal(state.saved.includes(selected)?'bookmark_remove':'bookmark_add',selected),false);
  if(b.dataset.item)run(async()=>{cart=b.dataset.item;await transact('checkout_started');page='checkout'});
  if(b.dataset.checkin||b.dataset.proposal)run(async()=>{
    const r=business.records.find(r=>r.id===(b.dataset.checkin||b.dataset.proposal));
    await transact(b.dataset.checkin?'ticket_checkin':'proposal_requested',{record:r.id,event:r.event_id,index:Number(b.dataset.index||1)});
  },false);
  if(b.id==='seed-phone')run(async()=>{await loadSample(b);business=await api('/api/business')},false);
  if(b.id==='add-requirement'){
    const root=$('#requirements'),i=root.querySelectorAll('[name^=custom]').length;
    if(i<8)root.insertAdjacentHTML('beforeend',`<label>Requirement name<input maxlength="60" name="custom:${i}"></label><label>Requirement details<input maxlength="300" name="value:${i}"></label>`);
  }
  if(b.dataset.stage)$('#stage-detail').textContent=['The phone sends actions with event IDs.','The server validates event IDs, prices, capacity, and ownership.','SQLite stores each action with an outbox entry. Kafka routes business actions to their own topics.','The materializer updates scores. Organizer reports aggregate issued tickets, entry, and demo orders.'][Number(b.dataset.stage)];
});
$('#screen').addEventListener('change',e=>{if(e.target.matches('[data-event-select]')){selected=e.target.value;if(['dashboard','sales','attendees'].includes(page))run(()=>signal('page_view'),false)}});
$('#screen').addEventListener('input',total);
$('#screen').addEventListener('submit',e=>{
  e.preventDefault();const form=e.target,type=form.dataset.form,data=Object.fromEntries(new FormData(form));
  if(data.quantity)data.quantity=Number(data.quantity);
  if(type==='event_brief_created'){
    data.guests=Number(data.guests);data.requirements=Object.create(null);
    for(const [k,v] of Object.entries(data)){
      if(k.startsWith('req:'))data.requirements[k.slice(4)]=v;
      if(k.startsWith('custom:')&&v.trim())data.requirements[v.trim()]=data['value:'+k.slice(7)]||'';
    }
  }
  if(type==='product_purchase')data.item=cart;
  run(async()=>{const r=await transact(type,data);if(type.endsWith('_purchase')){receipt=r;page='ticket'}if(type==='event_brief_created')page='brief'});
});
$('#reset').onclick=()=>{if(confirm('Clear your demo orders, tickets, briefs and activity?'))run(async()=>{state=await api('/api/reset',{});business=await api('/api/business');page='discover';filter='All'})};
$('#export').onclick=async()=>{const blob=new Blob([JSON.stringify(await api('/api/export'),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='northline-events.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
try{[catalog,state,business]=await Promise.all([api('/api/catalog'),api('/api/state'),api('/api/business')]);phone();analytics()}catch(e){$('#error').textContent=e.message}
setInterval(async()=>{if(!document.hidden&&!busy&&state?.pending){state=await api('/api/state');analytics()}},1500);
