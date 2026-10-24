/* CityLens map UI — design by the team (docs/design), wired to real pipeline data.
   Data: public/data/ui.json (tracts + ACS), comments.json (voice: Legistar letters real, emails simulated),
   requests_311_by_tract.json (real 311, separate family), inbox.json (email attachments metadata).
   Channel rule: voice and 311 are never summed; they meet only through per-1k-rate percentiles. */
import * as d3 from 'd3'
import './cvm.css'

const COL={support:'#1F7A6E',oppose:'#B3412B',neutral:'#6B7280',unclear:'#8A6D3B',amber:'#B7791F'};
const GAP=['#EDE9F7','#C9BEE8','#9F8AD3','#7357B4','#4A2C8C'];
const GAPM=['#D9D6CE','#CDC2EC','#9F8AD3','#7357B4','#4A2C8C'];
const RAW=['#E4E0D8','#F6CFC2','#E8957D','#C8553D','#8E2A1C'];
const PROB=['#E3F1EF','#A9D8D1','#5FB3A8','#22877C','#0B5249'];
const RAWZ=`repeating-linear-gradient(45deg,#E4E0D8 0 3px,#C9C4BA 3px 4.5px)`;
const CATS=[];const CATN={};const ITEM={};
const STANCES=['support','oppose','neutral','unclear'];
/* thresholds come from public/data/ui.json (written from fairness/meta.json); labels are filled in at load */
const ATTRS={renter:{l:'Renter-majority',s:'Renter-majority',f:null,acs:'ACS B25003',key:'renter_majority'},income:{l:'Below-median income',s:'Below-median-income',f:null,acs:'ACS B19013',key:'low_income'},nonwhite:{l:'Majority non-white',s:'Majority non-white',f:null,acs:'ACS B03002',key:'majority_nonwhite'},lep:{l:'High limited-English',s:'High limited-English',f:null,acs:'ACS C16002',key:'high_lep'}};
const ITEMS={};
const EAST_REGION=(()=>{const pts=[];const cx=-121.832,cy=37.334;for(let i=0;i<44;i++){const a=i/44*Math.PI*2;const r=1+0.07*Math.sin(a*3+1)+0.04*Math.sin(a*7)+0.03*Math.cos(a*11);pts.push([+(cx+Math.cos(a)*0.034*r).toFixed(4),+(cy+Math.sin(a)*0.021*r*(a>Math.PI?1.08:0.95)).toFixed(4)])}return pts})();
const WG_REGION=(()=>{const pts=[];const cx=-121.902,cy=37.298;for(let i=0;i<36;i++){const a=i/36*Math.PI*2;const r=1+0.06*Math.sin(a*4)+0.04*Math.cos(a*9);pts.push([+(cx+Math.cos(a)*0.028*r).toFixed(4),+(cy+Math.sin(a)*0.019*r).toFixed(4)])}return pts})();
function rng(s){return function(){s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function seedOf(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
function inRing(p,r){let x=p[0],y=p[1],ins=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];if(((yi>y)!=(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))ins=!ins}return ins}
function inGeom(p,g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;return P.some(pl=>inRing(p,pl[0])&&!pl.slice(1).some(h=>inRing(p,h)))}
function bbox(g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;let a=[1e9,1e9,-1e9,-1e9];P.forEach(pl=>pl[0].forEach(c=>{a[0]=Math.min(a[0],c[0]);a[1]=Math.min(a[1],c[1]);a[2]=Math.max(a[2],c[0]);a[3]=Math.max(a[3],c[1])}));return a}
const fmt=n=>n.toLocaleString('en-US');
const pct=x=>Math.round(x*100)+'%';
const sgn=n=>(n>0?'+':n<0?'−':'')+Math.abs(n);
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;');
const fdate=c=>c.when?c.when.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}):'date unknown';
const fdi=f=>f.di==null?'—':f.di.toFixed(2);
const LANG={en:'English',es:'Spanish',vi:'Vietnamese'};
const clip=(s,n)=>{s=String(s||'');return s.length>n?s.slice(0,n).replace(/\s+\S*$/,'')+'…':s};
const ICON={
 support:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="4.2" fill="${COL.support}"/></svg>`,
 oppose:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><polygon points="5,0.8 9.6,9.2 0.4,9.2" fill="${COL.oppose}"/></svg>`,
 neutral:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><rect x="1.2" y="1.2" width="7.6" height="7.6" fill="${COL.neutral}"/></svg>`,
 unclear:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><polygon points="5,0.6 9.4,5 5,9.4 0.6,5" fill="none" stroke="${COL.unclear}" stroke-width="1.6"/></svg>`,
 chevL:'<svg width="12" height="12" viewBox="0 0 12 12"><path d="M7.5 2.5 4 6l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
 chevR:'<svg width="12" height="12" viewBox="0 0 12 12"><path d="M4.5 2.5 8 6l-3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
 chevD:'<svg width="12" height="12" viewBox="0 0 12 12"><path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>',
 split:'<svg width="15" height="13" viewBox="0 0 15 13"><rect x=".7" y=".7" width="13.6" height="11.6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M7.5 .7v11.6" stroke="currentColor" stroke-width="1.3"/></svg>',
 pen:'<svg width="14" height="14" viewBox="0 0 14 14"><path d="M2 12l1-3.2 6.6-6.6 2.2 2.2L5.2 11 2 12z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>',
 filter:'<svg width="16" height="16" viewBox="0 0 16 16"><path d="M2 4h12M4 8h8M6 12h4" stroke="currentColor" stroke-width="1.4"/></svg>',
 gauge:'<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 13V8M8 13V3M13 13V6" stroke="currentColor" stroke-width="1.6"/></svg>',
 shape:'<svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 5c2-3 8-3 10 0s0 8-5 8-7-5-5-8z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-dasharray="2 1.5"/></svg>',
 list:'<svg width="16" height="16" viewBox="0 0 16 16"><path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" stroke-width="1.4"/></svg>',
 gapI:'<svg width="16" height="16" viewBox="0 0 16 16"><rect x="2" y="2" width="5" height="5" fill="currentColor"/><rect x="9" y="2" width="5" height="5" fill="none" stroke="currentColor"/><rect x="2" y="9" width="5" height="5" fill="none" stroke="currentColor"/><rect x="9" y="9" width="5" height="5" fill="currentColor" opacity=".5"/></svg>',
 chat:'<svg width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 3h11v7.5H7L4 13v-2.5H2.5z" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>'};
const stLabel={support:'Support',oppose:'Oppose',neutral:'Neutral',unclear:'Unclear'};
const stIco=(s,z)=>(ICON[s]||ICON.unclear)(z);

/* ---------- data ---------- */
const D={};
const BASE=(import.meta.env.BASE_URL||'/').replace(/\/$/,'');
const getJ=p=>fetch(`${BASE}/data/${p}`).then(r=>{if(!r.ok)throw new Error(`${p}: HTTP ${r.status}`);return r.json()});
function jitter(c,t){const R=rng(seedOf(c.id));const bb=t.cb||bbox(t.geometry);let p,k=0;do{p=[bb[0]+R()*(bb[2]-bb[0]),bb[1]+R()*(bb[3]-bb[1])];k++}while(!(inGeom(p,t.geometry)&&inGeom(p,D.city.geometry))&&k<400);return k>=400?t.c:p}
async function load(){
 if(D.ready)return D;
 const [ui,voice,p311,inbox]=await Promise.all([getJ('ui.json'),getJ('comments.json'),getJ('requests_311_by_tract.json'),getJ('inbox.json').catch(()=>({emails:[]}))]);
 D.city={type:'Feature',geometry:ui.city,properties:{}};
 D.tracts=ui.tracts;D.thr=ui.thresholds;D.acsYears=ui.acs_years;D.attrMeta=ui.attributes;
 const T=D.tracts;
 const rew=g=>{const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;P.forEach(pl=>pl.forEach(r=>{if(d3.geoArea({type:'Polygon',coordinates:[r]})>2*Math.PI)r.reverse()}))};
 rew(D.city.geometry);T.forEach(t=>rew(t.geometry));
 const th=D.thr;D.medInc=th.low_income;
 ATTRS.income.f=t=>t.income<th.low_income;ATTRS.renter.f=t=>t.renter>th.renter_majority;
 ATTRS.nonwhite.f=t=>t.nonwhite>th.majority_nonwhite;ATTRS.lep.f=t=>t.lep>th.high_lep;
 D.totPop=T.reduce((s,t)=>s+t.pop,0);
 T.forEach(t=>{const P=t.geometry.type==='Polygon'?[t.geometry.coordinates]:t.geometry.coordinates;let a=[1e9,1e9,-1e9,-1e9],n=0;P.forEach(pl=>pl[0].forEach(v=>{if(inGeom(v,D.city.geometry)){n++;a[0]=Math.min(a[0],v[0]);a[1]=Math.min(a[1],v[1]);a[2]=Math.max(a[2],v[0]);a[3]=Math.max(a[3],v[1])}}));if(n<3){const d=0.004;a=[t.c[0]-d,t.c[1]-d,t.c[0]+d,t.c[1]+d]}t.cb=a;t.e=Math.max(0,Math.min(1,(t.c[0]+121.88)/0.08))});
 D.byTract=Object.fromEntries(T.map(t=>[t.id,t]));
 /* voice comments: one record per unique comment (duplicate_of rows are counted in raw totals only) */
 const att={};(inbox.emails||[]).forEach(e=>{att[e.comment_id]=e.attachments||[]});
 const campSize={};voice.comments.forEach(c=>{if(c.campaign_id)campSize[c.campaign_id]=(campSize[c.campaign_id]||0)+1});
 D.rawRows=voice.comments.length;D.catDefs=voice.categories;
 D.voice=voice.comments.filter(c=>!c.duplicate_of).map(c=>{const t=c.tract_id?D.byTract[c.tract_id]:null;const a=att[c.comment_id]||[];
  return {id:c.comment_id,catKey:c.category,subKey:c.subcategory,tract:t?t.id:null,t,stance:STANCES.includes(c.stance)?c.stance:'unclear',
   text:c.text||'',subject:c.subject||'',lang:LANG[c.language]||c.language||'Unknown',langCode:c.language,tier:c.location_precision||'none',locSrc:c.location_source||'',basis:c.location_basis||'',
   src:c.channel==='letter'?'Letter':c.channel==='email'?'Email':'Site',mock:!!c.mock,when:c.received_at?new Date(c.received_at):null,
   attach:a,photo:a.some(x=>x.kind==='image'),camp:c.campaign_id||null,campSize:c.campaign_id?campSize[c.campaign_id]:0,
   evq:c.evidence_quote||'',sev:c.stance_evidence||'',conf:c.confidence,engine:c.engine||'',agenda:c.item,agendaTitle:c.item_title||'',meeting:c.meeting_date||'',
   ocr:!!c.ocr,pages:c.pages_total,exhibit:c.pages_exhibit,srcUrl:c.source_url||'',office:c.to_office||'',via:c.submitted_via||'',commenter:c.commenter_type||'',inherited:c.inherited_from||''}});
 D.voice.forEach(c=>{if(c.t)c.ll=jitter(c,c.t)});
 /* 311: problem reports per tract per category, summed over the window (separate family) */
 D.p311={all:{}};D.m311=p311.months_covered;D.p311Labels=p311.category_labels||{};
 Object.entries(p311.by_tract).forEach(([t,cats])=>Object.entries(cats).forEach(([k,m])=>{const n=Object.values(m).reduce((a,b)=>a+b,0);(D.p311[k]=D.p311[k]||{})[t]=((D.p311[k]||{})[t]||0)+n;D.p311.all[t]=(D.p311.all[t]||0)+n}));
 /* sections (Bob's categories) become the picker items; 'all' aggregates voice only */
 const srcOf=list=>{const o={};list.forEach(c=>{const k=c.src+(c.mock?' (simulated)':'');o[k]=(o[k]||0)+1});return o};
 const sum311=k=>Object.values(D.p311[k]||{}).reduce((a,b)=>a+b,0);
 voice.categories.forEach(cat=>{const list=D.voice.filter(c=>c.catKey===cat.key);if(!list.length)return;
  ITEMS[cat.key]={id:cat.key,title:cat.label,desc:cat.description,src:srcOf(list),n311:sum311(cat.key)||null,
   subs:cat.subcategories.map(s=>({k:'sub:'+s.key,n:s.label,count:list.filter(c=>c.subKey===s.key).length})).filter(s=>s.count>0),total:list.length}});
 const order=Object.values(ITEMS).sort((a,b)=>b.total-a.total).map(d=>d.id);
 ITEMS.all={id:'all',title:'All sections',desc:'Every voice comment, all sections',src:srcOf(D.voice),n311:sum311('all')||null,
  subs:voice.categories.map(c=>({k:'cat:'+c.key,n:c.label,count:D.voice.filter(x=>x.catKey===c.key).length})).filter(s=>s.count>0),total:D.voice.length};
 D.itemOrder=['all',...order];
 D.ready=true;setItem('all');return D;
}
function itemTotal(id){return ITEMS[id].total}
function srcLine(d){const e=Object.entries(d.src).sort((a,b)=>b[1]-a[1]);return e.map(([k,v])=>`${v} ${k.replace(/^(\w+)/,m=>m.toLowerCase()+(v===1?'':'s'))}`).join(', ')}
function n311(d){return d.n311?fmt(d.n311)+' reported problems':'No reported-problem data'}
function setItem(id){const T=D.tracts;const def=ITEMS[id];
 CATS.length=0;Object.keys(CATN).forEach(k=>delete CATN[k]);def.subs.forEach(c=>{CATS.push(c);CATN[c.k]=c.n});
 const all=D.voice.filter(c=>id==='all'||c.catKey===id);all.forEach(c=>{c.item=id;c.cat=id==='all'?'cat:'+c.catKey:'sub:'+c.subKey;if(!CATN[c.cat]){CATN[c.cat]=c.subKey||c.catKey}});
 const C=all.filter(c=>c.t);
 const cnt={};T.forEach(t=>cnt[t.id]=0);C.forEach(c=>cnt[c.tract]++);
 T.forEach(t=>t.n=cnt[t.id]);const located=C.length;
 T.forEach(t=>{t.exp=+(t.pop/D.totPop*located).toFixed(1);t.gap=t.exp>0?Math.round((t.n-t.exp)/t.exp*100):0;const tc=C.filter(c=>c.tract===t.id);t.prec=[tc.filter(c=>c.tier==='address').length,tc.filter(c=>c.tier==='neighborhood').length,tc.filter(c=>c.tier==='zip').length]});
 /* citywide median comment rate for this section, computed once over all tracts (never per region) */
 const rates=T.map(t=>t.n/t.pop*1000).sort((a,b)=>a-b);D.vMed=rates[Math.floor(rates.length/2)];D.hvTh=D.vMed;
 const p=D.p311[id]||{};T.forEach(t=>{t.p311=def.n311?(p[t.id]||0):0});
 C.sort((a,b)=>(b.when||0)-(a.when||0));D.comments=C;D.itemAll=all;D.located=located;
 for(const k in ITEM)delete ITEM[k];Object.assign(ITEM,def);ITEM.total=all.length;ITEM.pct=all.length?Math.round(located/all.length*100):0;
 ITEM.tiers=['address','neighborhood','zip','district','none'].map(k=>[k,all.filter(c=>c.tier===k).length]);
 ITEM.simulated=all.filter(c=>c.mock).length;ITEM.fallback=all.filter(c=>c.engine&&c.engine!=='bob').length}
/* Fairness per section, voice family: a tract is "heard" when its comment rate is above the citywide median
   (D.vMed). DI = P(heard|group)/P(heard|other); SPD = difference. Same definition as scripts/fairness.py. */
function fairness(tracts,ak){const f=ATTRS[ak].f;const u=tracts.filter(f),p=tracts.filter(t=>!f(t));const hv=t=>t.n/t.pop*1000>D.vMed;const hu=u.filter(hv).length,hp=p.filter(hv).length;
 const r={nu:u.length,np:p.length,hu,hp,pu:u.length?hu/u.length:0,pp:p.length?hp/p.length:0};r.few=tracts.length<5||u.length<2||p.length<2;r.spd=r.pu-r.pp;r.di=r.pp?r.pu/r.pp:null;return r}
function weights(comments,mode,ak){
 if(mode==='raw')return comments.map(()=>1);
 if(mode==='pop')return comments.map(c=>c.t.pop/Math.max(1,c.t.n)/400);
 const f=ATTRS[ak||'renter'].f;const T=D.tracts;const popU=T.filter(f).reduce((s,t)=>s+t.pop,0)/D.totPop;const cu=D.comments.filter(c=>f(c.t)).length/Math.max(1,D.comments.length);
 const wu=popU/Math.max(.01,cu),wp=(1-popU)/Math.max(.01,1-cu);return comments.map(c=>f(c.t)?wu:wp)}
function catTotals(comments,mode,ak){const w=weights(comments,mode,ak);const o={};CATS.forEach(c=>o[c.k]={k:c.k,n:c.n,tot:0,support:0,oppose:0,neutral:0,unclear:0,count:0});comments.forEach((c,i)=>{const x=o[c.cat];if(!x)return;x.tot+=w[i];x[c.stance]+=w[i];x.count++});return Object.values(o)}
function ranks(comments,ak){const m={};['raw','rw','pop'].forEach(mode=>{const t=catTotals(comments,mode,ak).sort((a,b)=>b.tot-a.tot);t.forEach((x,i)=>{(m[x.k]=m[x.k]||{k:x.k,n:x.n})[mode]=i+1})});return Object.values(m).sort((a,b)=>a.raw-b.raw)}
function gapBin(t){const g=t.gap;return g>=0?0:g>-30?1:g>-55?2:g>-80?3:4}
function rawBin(t){const n=t.n;return n===0?0:n<5?1:n<10?2:n<18?3:4}
function popBin(t){const r=t.n/t.pop*1000;return r===0?0:r<0.6?1:r<1.2?2:r<2.2?3:4}
/* percentile = share of tracts with a strictly lower rate (same rule as scripts/families.py) */
function pctRanks(vals){const s=[...vals].sort((a,b)=>a-b);const n=s.length;return vals.map(v=>{let lo=0,hi=n;while(lo<hi){const m=(lo+hi)>>1;if(s[m]<v)lo=m+1;else hi=m}return 100*lo/n})}
const _rtc=new WeakMap();
function regionTracts(poly){if(poly==='city')return D.tracts;if(poly&&poly.tract)return [D.byTract[poly.tract]];if(_rtc.has(poly)&&_rtc.get(poly).T===D.tracts)return _rtc.get(poly).r;
 const r=D.tracts.filter(t=>{if(inRing(t.c,poly))return true;const P=t.geometry.type==='Polygon'?[t.geometry.coordinates]:t.geometry.coordinates;let n=0,k=0;P.forEach(pl=>pl[0].forEach(v=>{n++;if(inRing(v,poly))k++}));return n&&k/n>=0.3});_rtc.set(poly,{T:D.tracts,r});return r}
