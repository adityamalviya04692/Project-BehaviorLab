export const $ = s => document.querySelector(s);
export const fmt = n => Number(n || 0).toLocaleString('en-IN');
export const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'The pipeline is unavailable. Please try again.');
  return result;
}
let toastTimer;
export function toast(message) {
  const element = $('#toast');
  if (!element) return;
  element.textContent = message; element.classList.add('visible');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => element.classList.remove('visible'), 6000);
}
export async function setupShell() {
  document.querySelectorAll('.site-nav a').forEach(a => {if(a.getAttribute('href') === location.pathname){a.classList.add('current');a.setAttribute('aria-current','page')}});
  try {
    const health = await api('/api/health');
    const status = $('#runtime-status');
    const recent = health.workers.filter(w => Date.now() - new Date(w.updated_at).getTime() < 15000);
    const ready = health.mode === 'local' || ['publisher','consumer'].every(name=>recent.some(w=>w.name===name && w.status==='running'));
    if(status) status.textContent = health.mode === 'local' ? 'Local processor · SQLite' : ready ? 'Kafka pipeline · workers active' : 'Kafka configured · workers pending';
    return {...health, ready};
  } catch(error) {if($('#runtime-status'))$('#runtime-status').textContent='Pipeline unavailable';toast(error.message);return {mode:'offline',ready:false}}
}
export async function loadSample(button) {
  const label = button.textContent;
  button.disabled = true;button.textContent='Adding sample visitors…';
  try {const result=await api('/api/simulate',{});toast(result.created ? '60 synthetic visitors queued. Watch them move through the pipeline.' : 'Your sample audience is already loaded.');return result}
  catch(error){toast(error.message);throw error}
  finally {button.disabled=false;button.textContent=label}
}
export function sourceControl(onChange) {
  document.querySelectorAll('[data-source]').forEach(button=>button.addEventListener('click',()=>{
    document.querySelectorAll('[data-source]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button))});
    onChange(button.dataset.source);
  }));
}
