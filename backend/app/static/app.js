/* GridOS control-room console */
let last=null,baseline=null,charts={},topo=null,runTimer=null,n1cache=null,almShow='ALL';
let openLines=new Set(),acked=new Set(),soeCache=[];
const $=id=>document.getElementById(id);
async function api(p,o){const r=await fetch(p,o);if(!r.ok)throw new Error(await r.text());return r.json();}
function toast(m){const t=document.createElement('div');t.className='toast';t.textContent=m;$('toasts').appendChild(t);setTimeout(()=>t.remove(),2600);}
function tick(){const d=new Date();$('clock').textContent=d.toLocaleTimeString('en-GB');}
setInterval(tick,1000);tick();
function paintSlider(el){const pc=(el.value-el.min)/(el.max-el.min)*100;el.style.setProperty('--fill',pc+'%');}
function syncLabels(){const l=+$('load').value,s=+$('solar').value;
  $('loadVal').textContent=l.toFixed(2)+' pu';$('solarVal').textContent=s.toFixed(2)+' pu';
  $('loadMw').textContent=(2.5*l).toFixed(2)+' MW';$('solarMw').textContent=(0.7*s).toFixed(2)+' MW';
  paintSlider($('load'));paintSlider($('solar'));}
$('load').oninput=()=>{syncLabels();autoGo();};
$('solar').oninput=()=>{syncLabels();autoGo();};
function autoGo(){if($('autoRun').checked){clearTimeout(runTimer);runTimer=setTimeout(runSim,350);}}
function preset(l,s){$('load').value=l;$('solar').value=s;syncLabels();runSim();}
function params(){return{load_multiplier:+$('load').value,solar_multiplier:+$('solar').value,open_lines:[...openLines]};}
function colorV(v){return v<0.1?'#555':v<0.95?'#f87171':v>1.05?'#fbbf24':'#34d399';}
function colorL(l){if(l==null||isNaN(l))return'#3a4666';return l>100?'#f87171':l>90?'#fbbf24':l>75?'#38bdf8':'#34d399';}
async function init(){
  syncLabels();
  try{const h=await api('/health');$('healthTxt').textContent='● '+(h.service||'gridos')+' '+ (h.version||'');$('health').classList.add('ok');}catch{$('healthTxt').textContent='● link down';}
  try{topo=await api('/grid');}catch{}
  buildBreakers();
  await runSim();
  loadHistory();loadEvents();
}
function buildBreakers(){
  const names=(topo&&topo.lines||[]).map(l=>l.name);
  const list=names.length?names:['L1-2','L2-3','L1-4','L4-5'];
  $('breakers').innerHTML=list.map(n=>`<div class="brk closed" id="brk-${n}" onclick="toggleLine('${n}')"><span class="cb"></span><span><b>${n}</b><small>11kV feeder CB</small></span><span class="st">CLOSED</span></div>`).join('');
}
async function toggleLine(n){
  const wasOpen=openLines.has(n);
  if(wasOpen)openLines.delete(n);else openLines.add(n);
  const el=$('brk-'+n);
  if(el){el.classList.toggle('open',!wasOpen);el.classList.toggle('closed',wasOpen);el.querySelector('.st').textContent=wasOpen?'CLOSED':'OPEN';}
  await api('/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'switching',asset:n,message:(wasOpen?'Closed ':'Opened ')+n+' CB (study switching)',actor:$('opName').textContent})});
  loadEvents();runSim();
}
async function runSim(){
  try{
    const res=await api('/simulate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params())});
    last=res;window._last=res;if(!baseline&&openLines.size===0)baseline=res;
    render(res);
  }catch(e){toast('Load flow failed: '+e.message);}
}
async function runN1(){
  toast('Running N-1 screen…');
  const p=params();
  n1cache=await api(`/contingency?load_multiplier=${p.load_multiplier}&solar_multiplier=${p.solar_multiplier}`);
  switchTab('t',document.querySelectorAll('.tabs .tab')[3]);
  drawN1();
  const worst=n1cache.results.filter(r=>r.outage!=='(none — intact)').sort((a,b)=>b.p1-a.p1)[0];
  toast(`N-1 done — worst: ${worst.outage} (${worst.p1} P1)`);
}
async function saveScenario(){
  const p=params();
  const rec=await api('/scenarios',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:`${p.load_multiplier}pu/${p.solar_multiplier}pv ${p.open_lines.length?'['+p.open_lines.join('+')+']':''}`,...p})});
  toast('Case #'+rec.id+' saved');loadHistory();loadEvents();
}
async function compareBase(){
  const c=await api('/compare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({baseline:{load_multiplier:1,solar_multiplier:1,open_lines:[]},scenario:params()})});
  render(c.scenario,c.baseline);
  const d=c.delta_p1;
  $('compareBox').innerHTML=`<div class="cmp">⚖ <b>vs base case:</b> Δlosses <b>${c.delta_losses_mw>0?'+':''}${c.delta_losses_mw} MW</b> · ΔT1 <b>${c.delta_trafo_loading>0?'+':''}${c.delta_trafo_loading}%</b> · ΔP1 <b style="color:${d>0?'var(--bad)':d<0?'var(--ok)':'inherit'}">${d>0?'+':''}${d}</b></div>`;
}
function exportCsv(which){const p=params();window.open(`/export/${which}?load_multiplier=${p.load_multiplier}&solar_multiplier=${p.solar_multiplier}`,'_blank');}
async function loadHistory(){
  try{const list=await api('/scenarios');
    $('history').innerHTML=list.length?list.slice().reverse().map(s=>`<div class="hist-row" onclick='replay(${s.id})'><span>#${s.id} ${s.name}</span><span class="mono">${s.result.total_losses_mw}MW · P1:${(s.result.alarms||[]).filter(a=>a.priority==='P1').length}</span></div>`).join(''):'<span class="muted">None yet.</span>';
    window._hist=list;}catch{}
}
async function replay(id){const r=await api('/scenarios/'+id);openLines=new Set(r.open_lines||[]);buildBreakers();[...openLines].forEach(n=>{const el=$('brk-'+n);if(el){el.classList.add('open');el.classList.remove('closed');el.querySelector('.st').textContent='OPEN';}});$('load').value=r.load_multiplier;$('solar').value=r.solar_multiplier;syncLabels();last=r.result;window._last=r.result;render(r.result);toast('Case #'+id+' loaded');}
async function loadEvents(){
  try{soeCache=await api('/events?limit=40');
    $('soe').innerHTML=soeCache.length?soeCache.map(e=>`<div class="soe-row"><span class="t">${e.ts.slice(11,19)}</span><span class="k ${e.type}">${e.type}</span><span>${e.asset?'<b>'+e.asset+'</b> ':''}${e.message} <span class="muted">· ${e.actor}</span></span></div>`).join(''):'<span class="muted">No entries.</span>';}catch{}
}
async function addNote(){const t=$('noteTxt').value.trim();if(!t)return;await api('/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'note',asset:'',message:t,actor:$('opName').textContent})});$('noteTxt').value='';loadEvents();}
async function ackAlarm(asset,type){
  acked.add(asset+type);
  await api('/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'alarm_ack',asset:asset,message:'Acknowledged '+type+' on '+asset,actor:$('opName').textContent})});
  loadEvents();if(last)renderAlarms(last);
}
function almFilter(p,btn){almShow=p;document.querySelectorAll('.alm-filter .tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');if(last)renderAlarms(last);}
function copyJson(){navigator.clipboard.writeText($('json').textContent);toast('Copied ✓');}
function downloadJson(){const b=new Blob([$('json').textContent],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='gridos_telemetry.json';a.click();}
function switchTab(k,btn){if(btn){document.querySelectorAll('.tabs .tab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');}['v','l','e','t'].forEach(x=>$('box'+x.toUpperCase()).classList.toggle('hidden',x!==k));}
/* ---------- render ---------- */
function sysStatus(res){
  const p1=res.alarms.filter(a=>a.priority==='P1').length;
  const p2=res.alarms.filter(a=>a.priority==='P2').length;
  if(!res.converged)return['✖ LOAD FLOW DIVERGED','solver non-convergence — check study setpoints','crit'];
  if(p1)return[`● ${p1} CRITICAL ALARM${p1>1?'S':''}`,'take corrective action — see alarm list','crit'];
  if(p2)return[`● ${p2} HIGH-PRIORITY ALARM${p2>1?'S':''}`,'prepare contingency — monitor closely','warn'];
  return['● SYSTEM NORMAL','all feeders energized · within SO limits','ok'];
}
function render(res,base){
  $('json').textContent=JSON.stringify(res,null,2);
  const[txt,sub,cls]=sysStatus(res);
  $('sysState').textContent=txt;$('sysSub').textContent=sub;
  $('sysBand').className='sysband '+cls;
  const c={P1:0,P2:0,P3:0};res.alarms.forEach(a=>{if(c[a.priority]!=null)c[a.priority]++;});
  $('cP1').textContent=c.P1;$('cP2').textContent=c.P2;$('cP3').textContent=c.P3;
  $('cP1').style.color=c.P1?'var(--bad)':'inherit';
  const vmin=Math.min(...res.buses.filter(b=>b.energized!==false).map(b=>b.voltage_pu),1);
  const lmax=Math.max(...res.lines.filter(l=>l.in_service!==false).map(l=>l.loading_percent),res.transformer_loading_percent);
  $('kVmin').textContent=vmin.toFixed(4);
  $('kVmin').style.color=vmin<0.95?'var(--bad)':'var(--ok)';
  $('kLdmax').textContent=(isFinite(lmax)?lmax:0).toFixed(1)+'%';
  $('kLoss').textContent=res.total_losses_mw+' MW';
  $('kPf').textContent=res.pf.toFixed(2);
  renderAlarms(res);drawGrid(res);drawCharts(res);drawFeeders(res);
}
function renderAlarms(res){
  const list=res.alarms.filter(a=>almShow==='ALL'||a.priority===almShow);
  const now=new Date().toLocaleTimeString('en-GB');
  $('alarms').innerHTML=list.length?list.map(a=>{const k=a.asset+a.type;const ak=acked.has(k);
    return `<div class="alm ${a.priority}${a.priority==='P1'&&!ak?' flash':''}${ak?' acked':''}"><span class="apri">${a.priority}</span><span class="amsg"><b>${a.asset}</b> — ${a.message}<br><span class="atime">${now} · ${a.type} · obs ${a.observed} ${a.unit||''} / lim ${a.limit}</span></span>${ak?'<span class="atime">ACK ✓</span>':`<button class="ack" onclick="ackAlarm('${a.asset}','${a.type}')">ACK</button>`}</div>`;}).join(''):`<div class="alm P3"><span class="apri">—</span><span class="amsg">No ${almShow==='ALL'?'':almShow+' '}alarms at this operating point. System within limits.</span><span></span></div>`;
}
/* ---------- single-line (substation bay layout, left -> right) ---------- */
/*  x: SRC(60) -> T1(170) -> BB(300) -> F1(430) -> F2(600) ; rows y=110 (Fdr A), y=250 (Fdr B) */
const POS = {
  'Grid Supply': [60, 180], 'LV Main': [300, 180],
  'Feeder A1': [455, 105], 'Feeder A2': [625, 105],
  'Feeder B1': [455, 255], 'Feeder B2': [625, 255],
};
function drawGrid(res) {
  const svg = $('gridSvg');
  const vmap = {}; res.buses.forEach(b => vmap[b.name] = b);
  const lmap = {}; res.lines.forEach(l => lmap[l.name] = l);
  const tx = res.transformer || {};
  const txC = colorL(tx.loading_percent);
  let s = `<defs><marker id="arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5b8cff"/></marker></defs>`;
  const feed = (a, b) => {
    // orthogonal feeder run: horizontal out of busbar, elbow, horizontal to load
    const [x1, y1] = POS[a], [x2, y2] = POS[b];
    const midX = (x1 + x2) / 2;
    return `M${x1},${y1} H${midX} V${y2} H${x2}`;
  };
  const linkBadge = (nm, mx, my, ld, open) => {
    const c = open ? 'var(--bad)' : colorL(ld);
    const txt = open ? `✕ ${nm} OPEN` : `${nm}  ${ld != null ? ld + '%' : ''}`;
    return `<g class="edge" data-nm="${nm}" style="cursor:pointer" onclick="showAsset('${nm}',window._last)"><rect x="${mx - 52}" y="${my - 12}" width="104" height="22" rx="11" fill="#0b1120" stroke="${c}" stroke-width="1.3"/><text x="${mx}" y="${my + 4}" class="lbl" text-anchor="middle" style="font-size:11.5px">${txt}</text></g>`;
  };
  const cbMark = (nm, x, y, open) =>
    `<g class="edge" style="cursor:pointer" onclick="toggleLine('${nm}')"><rect x="${x - 8}" y="${y - 8}" width="16" height="16" rx="3" fill="${open ? '#0b1120' : 'rgba(52,211,153,.25)'}" stroke="${open ? 'var(--bad)' : '#34d399'}" stroke-width="2"/><line x1="${x - 8}" y1="${y - 8}" x2="${x + 8}" y2="${y + 8}" stroke="${open ? 'var(--bad)' : 'transparent'}" stroke-width="2"/><title>${nm} CB \u2014 click to ${open ? 'CLOSE' : 'OPEN'}</title></g>`;
  const trimEnd = (d, gap) => d.replace(/H(\d+(?:\.\d+)?)\s*$/, (m, x) => `H${(+x - gap)}`);
  const flowSeg = (d, nm, open, ld) => {
    if (open) return `<path d="${d}" fill="none" stroke="#3a4666" stroke-width="2" stroke-dasharray="4 5"/>`;
    const w = 3 + Math.min(ld || 0, 150) / 30;
    const c = colorL(ld);
    return `<path d="${d}" fill="none" stroke="#1c2540" stroke-width="${w + 5}" stroke-linecap="round" stroke-linejoin="round"/><path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="9 6" class="flow" marker-end="url(#arr)" data-nm="${nm}" style="cursor:pointer" onclick="showAsset('${nm}',window._last)"/>`;
  };
  // ---- 33 kV source bay ----
  const src = vmap['Grid Supply'];
  s += `<g class="node" style="cursor:pointer" onclick="showAsset('Grid Supply',window._last)">`
    + `<rect x="28" y="152" width="64" height="56" rx="8" fill="#0b1120" stroke="#5b8cff" stroke-width="1.6"/>`
    + `<circle cx="60" cy="170" r="11" fill="none" stroke="#5b8cff" stroke-width="2"/><path d="M60,163 L65,174 L55,174 Z" fill="#5b8cff"/>`
    + `<text x="60" y="198" class="nval">${src ? src.voltage_pu : ''}</text></g>`
    + `<text x="60" y="140" class="nlbl" text-anchor="middle">GRID 33kV</text>`
    + `<text x="60" y="224" class="nlbl" text-anchor="middle">SRC</text>`;
  // source -> transformer HV link
  s += `<line x1="92" y1="180" x2="128" y2="180" stroke="#5b8cff" stroke-width="3"/>`;
  // ---- T1 two-circle transformer symbol ----
  s += `<g class="node" style="cursor:pointer" onclick="showAsset('T1',window._last)">`
    + `<circle cx="152" cy="168" r="14" fill="#0b1120" stroke="${txC}" stroke-width="2.5"/>`
    + `<circle cx="152" cy="194" r="14" fill="#0b1120" stroke="${txC}" stroke-width="2.5"/>`
    + `<text x="152" y="128" class="nlbl" text-anchor="middle">T1 \u00b7 ONAN 5MVA</text>`
    + `<text x="152" y="228" class="lbl" text-anchor="middle" fill="${txC}">T1 ${tx.loading_percent != null ? tx.loading_percent + '%' : ''}</text></g>`;
  // transformer LV -> busbar link
  s += `<line x1="166" y1="194" x2="288" y2="194" stroke="${txC}" stroke-width="3"/>`;
  // ---- 11 kV busbar (vertical bar, feeders tap off top/bottom ends) ----
  s += `<rect x="292" y="96" width="14" height="168" rx="4" fill="#c7d2f5" opacity="0.92"/>`
    + `<text x="252" y="84" class="nlbl" text-anchor="middle">11 kV BB ${vmap['LV Main'] ? vmap['LV Main'].voltage_pu + ' pu' : ''}</text>`;
  // ---- feeder branches ----
  const branches = [
    ['LV Main', 'Feeder A1', 'L1-2'], ['Feeder A1', 'Feeder A2', 'L2-3'],
    ['LV Main', 'Feeder B1', 'L1-4'], ['Feeder B1', 'Feeder B2', 'L4-5'],
  ];
  branches.forEach(([a, b, nm]) => {
    const L = lmap[nm];
    const open = L && L.in_service === false;
    const ld = open ? 0 : (L ? L.loading_percent : null);
    let d;
    if (a === 'LV Main') {
      // busbar edge -> elbow -> load node (leave a gap so CB sits on the line)
      const [x2, y2] = POS[b];
      d = `M306,${y2} H${x2 - 14}`;
    } else {
      const [x1, y1] = POS[a], [x2, y2] = POS[b];
      d = `M${x1 + 14},${y1} H${x2 - 14}`;
    }
    s += flowSeg(trimEnd(d, 32), nm, open, ld);
    // midpoint badge (offset above/below so it never sits on the wire)
    const [bx1, by1] = a === 'LV Main' ? [306, POS[b][1]] : POS[a];
    const [bx2, by2] = POS[b];
    const isHead = (a === 'LV Main');
    const dirSign = by2 < 180 ? -1 : 1;
    const mx = isHead ? (open ? bx1 + (bx2 - bx1) * 0.28 : bx1 + (bx2 - bx1) * 0.40) : (bx1 + bx2) / 2, my = (by1 + by2) / 2 + 30 * dirSign;
    s += linkBadge(nm, mx, my, ld, open);
    // CB at sending end
    const cx = a === 'LV Main' ? 330 : POS[a][0] + 34;
    s += cbMark(nm, cx, POS[b][1], open);
  });
  // ---- load / PV nodes ----
  ['Feeder A1', 'Feeder A2', 'Feeder B1', 'Feeder B2'].forEach(nm => {
    const b = vmap[nm];
    const [x, y] = POS[nm];
    const en = b && b.energized !== false;
    const c = !b ? '#3a4666' : colorV(b.voltage_pu);
    const hasPV = (nm === 'Feeder A2' || nm === 'Feeder B2');
    s += `<g class="node" style="cursor:pointer" onclick="showAsset('${nm}',window._last)">`
      + (en
        ? `<circle cx="${x}" cy="${y}" r="22" fill="#0b1120" stroke="${c}" stroke-width="2.5"/><circle cx="${x}" cy="${y}" r="22" fill="${c}" opacity="0.10"/>`
        : `<circle cx="${x}" cy="${y}" r="22" fill="#0b1120" stroke="#3a4666" stroke-width="2" stroke-dasharray="4 3"/>`)
      + `<text x="${x}" y="${y - 1}" text-anchor="middle" font-size="13">${en ? (hasPV ? '\u2600\ufe0f' : '\ud83d\udd0c') : '\u26ab'}</text>`
      + `<text x="${x}" y="${y + 13}" class="nval">${!b ? '\u2014' : (en ? b.voltage_pu : 'DEAD')}</text></g>`
      + `<text x="${x}" y="${y + 38}" class="nlbl" text-anchor="middle">${nm}</text>`
      + (b && b.p_mw != null ? `<text x="${x}" y="${y + 51}" class="lbl" text-anchor="middle">${b.p_mw} MW${hasPV ? ' \u00b7 PV' : ''}</text>` : '');
  });
  svg.innerHTML = s;
  svg.setAttribute('viewBox', '0 0 710 340');
}
function showAsset(nm, res) {

  let h='<b>'+nm+'</b>';
  const b=res.buses.find(b=>b.name===nm);
  if(b){h+=` — <b style="color:${colorV(b.voltage_pu)}">${b.voltage_pu} pu (${b.voltage_kv} kV)</b> · ∠${b.angle_deg}° · P ${b.p_mw} MW / Q ${b.q_mvar} Mvar · ${b.energized===false?'<b style="color:var(--bad)">DE-ENERGIZED</b>':'energized'} · ${b.vn_kv} kV bay`;}
  if(nm==='T1'&&res.transformer){const t=res.transformer;h+=` — ONAN ${t.sn_mva} MVA · <b style="color:${colorL(t.loading_percent)}">${t.loading_percent}%</b> · HV ${t.p_hv_mw} MW / ${t.q_hv_mvar} Mvar · loss ${t.loss_mw} MW`;
    h+=' · vector Dyn11 · uk 10% (model)';}
  const l=res.lines.find(l=>l.name===nm);
  if(l){h+=` — <b style="color:${colorL(l.loading_percent)}">${l.in_service===false?'OPEN (out of service)':l.loading_percent+'%'}</b> · ${l.from_bus} → ${l.to_bus} · ${l.current_a} A / ${l.rated_a} A rated · ${l.p_from_mw} MW · loss ${l.loss_mw} MW · click CB ☐ on diagram to switch`;}
  $('assetDetail').innerHTML=h;
}
/* ---------- charts ---------- */
function drawCharts(res){
  Chart.defaults.color='#8b96b5';Chart.defaults.font.family='Inter';
  Object.values(charts).forEach(c=>{try{c.destroy();}catch{}});charts={};
  const band={id:'band',beforeDatasetsDraw(c){const{ctx,scales:{y}}=c;ctx.save();ctx.fillStyle='rgba(52,211,153,.07)';const t=y.getPixelForValue(1.05),b=y.getPixelForValue(0.95);ctx.fillRect(c.chartArea.left,t,c.chartArea.right-c.chartArea.left,b-t);ctx.restore();}};
  charts.v=new Chart($('voltChart'),{type:'bar',data:{labels:res.buses.map(b=>b.name),datasets:[{data:res.buses.map(b=>b.voltage_pu),backgroundColor:res.buses.map(b=>colorV(b.voltage_pu)),borderRadius:6,barThickness:40}]},options:{plugins:{legend:{display:false}},scales:{y:{min:0.9,max:1.1,grid:{color:'#1c2540'},ticks:{callback:v=>v.toFixed(2)}}}}},[band]);
  const ll=[...res.lines.map(l=>({n:l.name+(l.in_service===false?' (open)':''),v:l.in_service===false?0:l.loading_percent})),{n:'T1 TX',v:res.transformer_loading_percent}];
  charts.l=new Chart($('loadChart'),{type:'bar',data:{labels:ll.map(x=>x.n),datasets:[{data:ll.map(x=>x.v),backgroundColor:ll.map(x=>colorL(x.v)),borderRadius:6,barThickness:40}]},options:{plugins:{legend:{display:false},annotation:{}},scales:{y:{beginAtZero:true,suggestedMax:120,grid:{color:'#1c2540'},ticks:{callback:v=>v+'%'}}}}});
  charts.e=new Chart($('energyChart'),{type:'doughnut',data:{labels:['PV infeed','Grid import','Losses'],datasets:[{data:[res.total_solar_mw,Math.max(res.grid_import_mw,0),res.total_losses_mw],backgroundColor:['#fbbf24','#5b8cff','#f87171'],borderWidth:0}]},options:{cutout:'60%',plugins:{legend:{position:'right'}}}});
  if(n1cache)drawN1();
}
function drawN1(){
  if(!n1cache)return;
  const rows=n1cache.results;
  charts.t=new Chart($('n1Chart'),{type:'bar',data:{labels:rows.map(r=>r.outage),datasets:[{label:'P1 alarms',data:rows.map(r=>r.p1),backgroundColor:rows.map(r=>r.p1?'#f87171':'#34d399'),borderRadius:6}]},options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true,ticks:{stepSize:1},grid:{color:'#1c2540'}}}}});
  $('n1Table').innerHTML='<table><tr><th>Outage</th><th>P1</th><th>Worst LD%</th><th>Vmin pu</th><th>Notes</th></tr>'+rows.map(r=>`<tr><td>${r.outage}</td><td style="color:${r.p1?'var(--bad)':'var(--ok)'}">${r.p1}</td><td>${r.worst_loading}</td><td>${r.min_v}</td><td class="muted">${(r.alarms||[]).join('; ')||'—'}</td></tr>`).join('')+'</table>';
}
function drawFeeders(res){
  const byBus={};res.buses.forEach(b=>byBus[b.name]=b);
  const head={'A':res.lines.find(l=>l.name==='L1-2'),'B':res.lines.find(l=>l.name==='L1-4')};
  const pvA=0.4*+$('solar').value,pvB=0.3*+$('solar').value;
  const ld=+$('load').value;
  const card=(f,load,pv)=>{const h=head[f];const pct=h?(h.in_service===false?0:h.loading_percent):0;
    return `<div class="fdr"><h4>Feeder ${f} — 11 kV ${h&&h.in_service===false?'· <b style="color:var(--bad)">HEAD-END OPEN</b>':''}</h4><div class="frow"><span>Demand</span><b>${load.toFixed(2)} MW</b></div><div class="frow"><span>PV infeed</span><b>${pv.toFixed(2)} MW</b></div><div class="frow"><span>Net</span><b>${(load-pv).toFixed(2)} MW</b></div><div class="bar"><i style="width:${Math.min(pct,100)}%;background:${colorL(pct)}"></i></div><div class="frow"><span>Head-end ${h?h.name:''}</span><b>${h?(h.in_service===false?'OPEN':h.current_a+' A / '+h.rated_a+' A · '+pct+'%'):'—'}</b></div></div>`;};
  $('feeders').innerHTML=card('A',1.1*ld,pvA)+card('B',1.4*ld,pvB);
}
init();
