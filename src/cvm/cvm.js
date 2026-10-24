/* CityLens map UI — design by the team (docs/design), wired to real pipeline data.
   Data: public/data/ui.json (census tracts + ACS), comments.json (voice: Legistar letters real, emails simulated),
   requests_311_by_tract.json (real 311, separate family), inbox.json (email attachments metadata).
   Channel rule: voice and 311 are never summed; they meet only through per-1k-rate percentiles. */
import * as d3 from 'd3'
import './cvm.css'
import { askAssistant } from './assistant.js'
import CONTEXT_MD from '../../docs/CONTEXT_SAN_JOSE.md?raw'
import { union as tUnion, polygon as tPoly, featureCollection as tFC } from '@turf/turf'

const COL={support:'#1F7A6E',oppose:'#B3412B',neutral:'#6B7280',unclear:'#8A6D3B',none:'#9A9A94',amber:'#B7791F'};
const CMPC=['#4A2C8C','#C2410C'];/* compared places: first, second */
const GAP=['#EDE9F7','#C9BEE8','#9F8AD3','#7357B4','#4A2C8C'];
const GAPM=['#D9D6CE','#CDC2EC','#9F8AD3','#7357B4','#4A2C8C'];
const RAW=['#E4E0D8','#F6CFC2','#E8957D','#C8553D','#8E2A1C'];
const PROB=['#E3F1EF','#A9D8D1','#5FB3A8','#22877C','#0B5249'];
const RAWZ=`repeating-linear-gradient(45deg,#E4E0D8 0 3px,#C9C4BA 3px 4.5px)`;
const CATS=[];const CATN={};const ITEM={};
const STANCES=['support','oppose','neutral','unclear'];
const S_KEY={open:false};
/* thresholds come from public/data/ui.json (written from fairness/meta.json); labels are filled in at load */
const ATTRS={renter:{l:'Renter-majority',s:'Renter-majority',f:null,acs:'ACS B25003',key:'renter_majority'},income:{l:'Below-median income',s:'Below-median-income',f:null,acs:'ACS B19013',key:'low_income'},nonwhite:{l:'Majority non-white',s:'Majority non-white',f:null,acs:'ACS B03002',key:'majority_nonwhite'},lep:{l:'High limited-English',s:'High limited-English',f:null,acs:'ACS C16002',key:'high_lep'}};
const ITEMS={};
const EAST_REGION=(()=>{const pts=[];const cx=-121.832,cy=37.334;for(let i=0;i<44;i++){const a=i/44*Math.PI*2;const r=1+0.07*Math.sin(a*3+1)+0.04*Math.sin(a*7)+0.03*Math.cos(a*11);pts.push([+(cx+Math.cos(a)*0.034*r).toFixed(4),+(cy+Math.sin(a)*0.021*r*(a>Math.PI?1.08:0.95)).toFixed(4)])}return pts})();
const WG_REGION=(()=>{const pts=[];const cx=-121.902,cy=37.298;for(let i=0;i<36;i++){const a=i/36*Math.PI*2;const r=1+0.06*Math.sin(a*4)+0.04*Math.cos(a*9);pts.push([+(cx+Math.cos(a)*0.028*r).toFixed(4),+(cy+Math.sin(a)*0.019*r).toFixed(4)])}return pts})();
function rng(s){return function(){s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function seedOf(str){let h=2166136261;for(let i=0;i<str.length;i++){h^=str.charCodeAt(i);h=Math.imul(h,16777619)}return h>>>0}
/* a drawn region is one ring [[lon,lat],…] or several disjoint rings [[[lon,lat],…],…] */
const isMulti=poly=>Array.isArray(poly)&&Array.isArray(poly[0])&&Array.isArray(poly[0][0]);
const ringsOf=poly=>!Array.isArray(poly)?[]:isMulti(poly)?poly:[poly];
const ptsOf=poly=>ringsOf(poly).flat();
const inPoly=(p,poly)=>ringsOf(poly).some(r=>inRing(p,r));
function mergeRings(list,ring){/* union the new ring with every ring it overlaps; disjoint rings stay separate */
 const close=r=>[...r,r[0]];let cur=ring,rest=[...list],changed=true;
 while(changed){changed=false;for(let i=0;i<rest.length;i++){let u=null;try{u=tUnion(tFC([tPoly([close(cur)]),tPoly([close(rest[i])])]))}catch(e){u=null}
  if(u&&u.geometry.type==='Polygon'){cur=u.geometry.coordinates[0].slice(0,-1);rest.splice(i,1);changed=true;break}}}
 return [...rest,cur]}
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
 none:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="2.6" fill="${COL.none}"/></svg>`,
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
const stLabel={support:'Support',oppose:'Oppose',neutral:'Neutral',unclear:'Unclear',none:'Report or request'};
const stV=c=>ITEM.id==='all'?'none':c.stance
const DEFS={"Residents": "People living here (ACS 5-year estimate, 2020–2024).", "English-only households": "Share of households where only English is spoken at home.", "Limited-English": "Share of households where no one 14 or older speaks English very well.", "Renters": "Share of occupied homes that are rented rather than owned.", "Median income": "Middle household income here compared with the San José median. High or Low means 10% or more above or below.", "Equity Priority": "Census tracts the regional planning agency (MTC) flags as Equity Priority Communities: many low-income residents plus other disadvantage factors.", "Comments (no copies)": "Public comments counted once each. Exact duplicates and form-letter copies are folded into one.", "Comments located here": "Comments whose writer’s location falls inside this area.", "Residents where we heard nothing": "Share of residents living in census tracts that sent zero located comments.", "311 problem reports / 1,000 / yr": "311 service requests per 1,000 residents per year. Shows where people report problems, separate from public comments.", "311 problem reports": "311 service requests per 1,000 residents per year. Shows where people report problems, separate from public comments.", "Ask for a specific fix": "Share of comments that report a concrete problem or request a specific city action, not just a support or oppose vote.", "Representation ratio": "Comments received divided by comments expected from this area’s share of residents. 1.0 means a fair share; below 0.5 means underheard.", "Placed on the map": "Share of comments we could place in a census tract from an address, intersection, neighborhood or ZIP.", "Real (not simulated)": "Share of comments from real public letters. The rest are simulated emails used for the demo.", "Average AI label confidence": "How sure the AI was, on average, about each comment’s section label (0–100%).", "Labeled by IBM Bob": "Share of comments labeled by IBM Bob. The newer simulated emails were labeled by the build agent (also AI). None have been reviewed by staff yet.", "How much to trust these numbers": "Data-quality checks. Low values mean the numbers below are rougher.", "Who we are not hearing from": "Census tracts sending under half the comments their population share would predict, and that either report many problems to 311 or have many limited-English households. Quiet census tracts with few problems are left out. Voice for its problems compares its messages with its 311 reports, against the city: red means problems are reported but few people write in.", "Local or citywide?": "For each section, the share of its located comments that come from its single busiest census tract.", "Support vs opposition": "For policy sections only: comments for minus comments against, as a share of those taking a side.", "What people write about": "Comments by section, as labeled by IBM Bob.", "What people report to 311": "311 service requests grouped into the same sections as comments.", "When comments arrived": "Comments per month by the date they were received.", "Who is writing": "How many different people wrote, how many comments are form-letter copies, and how many came from organizations.", "Languages": "Language of each comment, compared with the languages spoken at home here.", "Here vs citywide": "This area’s share for each section compared with the whole city.", "311 problem reports over time": "311 service requests per month."};
const defA=l=>DEFS[l]?` data-def="${esc(DEFS[l])}"`:'';
const stIco=(s,z)=>(ICON[s]||ICON.unclear)(z);

/* ---------- data ---------- */
const D={};
const BASE=(import.meta.env.BASE_URL||'/').replace(/\/$/,'');
const getJ=p=>fetch(`${BASE}/data/${p}`).then(r=>{if(!r.ok)throw new Error(`${p}: HTTP ${r.status}`);return r.json()});
function jitter(c,t){const R=rng(seedOf(c.id));const bb=t.cb||bbox(t.geometry);let p,k=0;do{p=[bb[0]+R()*(bb[2]-bb[0]),bb[1]+R()*(bb[3]-bb[1])];k++}while(!(inGeom(p,t.geometry)&&inGeom(p,D.city.geometry))&&k<400);return k>=400?t.c:p}
async function load(){
 if(D.ready)return D;
 const [ui,voice,p311,inbox,cfg,met]=await Promise.all([getJ('ui.json'),getJ('comments.json'),getJ('requests_311_by_tract.json'),getJ('inbox.json').catch(()=>({emails:[]})),getJ('config.json').catch(()=>({})),getJ('metrics.json').catch(()=>({metrics:{}}))]);
 D.metrics=(met&&met.metrics)||{};
 D.cfg=Object.assign({underrepresented_ratio:0.5,underheard_rule:{problems_vs_city:1,limited_english_vs_city:1.5},policy_sections:[],low_confidence:0.8,small_n:10},cfg);
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
 D.rawRows=voice.comments.length;D.catDefs=voice.categories;const POL=new Set(D.cfg.policy_sections);
 D.voice=voice.comments.filter(c=>!c.duplicate_of).map(c=>{const t=c.tract_id?D.byTract[c.tract_id]:null;const a=att[c.comment_id]||[];
  return {id:c.comment_id,catKey:c.category,subKey:c.subcategory,tract:t?t.id:null,t,stance:!POL.has(c.category)?'none':STANCES.includes(c.stance)?c.stance:'unclear',
   text:c.text||'',subject:c.subject||'',lang:LANG[c.language]||c.language||'Unknown',langCode:c.language,tier:c.location_precision||'none',locSrc:c.location_source||'',basis:c.location_basis||'',
   src:c.channel==='letter'?'Letter':c.channel==='email'?'Email':'Site',mock:!!c.mock,when:c.received_at?new Date(c.received_at):null,
   attach:a,photo:a.some(x=>x.kind==='image'),camp:c.campaign_id||null,campSize:c.campaign_id?campSize[c.campaign_id]:0,
   evq:c.evidence_quote||'',sev:c.stance_evidence||'',conf:c.confidence,engine:c.engine||'',agenda:c.item,agendaTitle:c.item_title||'',meeting:c.meeting_date||'',
   ocr:!!c.ocr,pages:c.pages_total,actionable:c.actionable??null,actReason:c.actionable_reason||'',participant:c.participant||'',exhibit:c.pages_exhibit,srcUrl:c.source_url||'',office:c.to_office||'',via:c.submitted_via||'',commenter:c.commenter_type||'',inherited:c.inherited_from||''}});
 D.voice.forEach(c=>{if(c.t)c.ll=jitter(c,c.t)});
 /* 311: problem reports per census tract per category, summed over the window (separate family) */
 D.p311={all:{}};D.m311=p311.months_covered;D.p311Labels=p311.category_labels||{};D.p311Tax=p311.taxonomy||[];
 D.p311m={};D.p311months=p311.months;Object.entries(p311.by_tract).forEach(([t,cats])=>Object.values(cats).forEach(m=>Object.entries(m).forEach(([mo,n])=>{(D.p311m[t]=D.p311m[t]||{})[mo]=((D.p311m[t]||{})[mo]||0)+n})));
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
 T.forEach(t=>{t.exp=t.pop/D.totPop*located;t.gap=t.exp>0?Math.round((t.n-t.exp)/t.exp*100):0;const tc=C.filter(c=>c.tract===t.id);t.prec=[tc.filter(c=>c.tier==='address').length,tc.filter(c=>c.tier==='neighborhood').length,tc.filter(c=>c.tier==='zip').length]});
 /* citywide median comment rate for this section, computed once over all census tracts (never per region) */
 const rates=T.map(t=>t.n/t.pop*1000).sort((a,b)=>a-b);D.vMed=rates[Math.floor(rates.length/2)];D.hvTh=D.vMed;
 const p=D.p311[id]||{};T.forEach(t=>{t.p311=def.n311?(p[t.id]||0):0});
 C.sort((a,b)=>(b.when||0)-(a.when||0));D.comments=C;D.itemAll=all;D.located=located;
 for(const k in ITEM)delete ITEM[k];Object.assign(ITEM,def);ITEM.total=all.length;ITEM.pct=all.length?Math.round(located/all.length*100):0;
 ITEM.tiers=['address','neighborhood','zip','district','none'].map(k=>[k,all.filter(c=>c.tier===k).length]);
 ITEM.simulated=all.filter(c=>c.mock).length;ITEM.fallback=all.filter(c=>c.engine&&c.engine!=='bob'&&c.engine!=='build-agent').length}
/* Fairness per section, voice family: a census tract is "heard" when its comment rate is above the citywide median
   (D.vMed). DI = P(heard|group)/P(heard|other); SPD = difference. Same definition as scripts/fairness.py. */
function fairness(tracts,ak){const f=ATTRS[ak].f;const u=tracts.filter(f),p=tracts.filter(t=>!f(t));const hv=t=>t.n/t.pop*1000>D.vMed;const hu=u.filter(hv).length,hp=p.filter(hv).length;
 const r={nu:u.length,np:p.length,hu,hp,pu:u.length?hu/u.length:0,pp:p.length?hp/p.length:0};r.few=tracts.length<5||u.length<2||p.length<2;r.spd=r.pu-r.pp;r.di=r.pp?r.pu/r.pp:null;return r}
function weights(comments,mode,ak){
 if(mode==='raw')return comments.map(()=>1);
 if(mode==='pop')return comments.map(c=>c.t.pop/Math.max(1,c.t.n)/400);
 const f=ATTRS[ak||'renter'].f;const T=D.tracts;const popU=T.filter(f).reduce((s,t)=>s+t.pop,0)/D.totPop;const cu=D.comments.filter(c=>f(c.t)).length/Math.max(1,D.comments.length);
 const wu=popU/Math.max(.01,cu),wp=(1-popU)/Math.max(.01,1-cu);return comments.map(c=>f(c.t)?wu:wp)}
function catTotals(comments,mode,ak){const w=weights(comments,mode,ak);const o={};CATS.forEach(c=>o[c.k]={k:c.k,n:c.n,tot:0,support:0,oppose:0,neutral:0,unclear:0,none:0,count:0});comments.forEach((c,i)=>{const x=o[c.cat];if(!x)return;x.tot+=w[i];x[c.stance]+=w[i];x.count++});return Object.values(o)}
function ranks(comments,ak){const m={};['raw','rw','pop'].forEach(mode=>{const t=catTotals(comments,mode,ak).sort((a,b)=>b.tot-a.tot);t.forEach((x,i)=>{(m[x.k]=m[x.k]||{k:x.k,n:x.n})[mode]=i+1})});return Object.values(m).sort((a,b)=>a.raw-b.raw)}
function gapBin(t){const g=t.gap;return g>=0?0:g>-30?1:g>-55?2:g>-80?3:4}
function rawBin(t){const n=t.n;return n===0?0:n<5?1:n<10?2:n<18?3:4}
function popBin(t){const r=t.n/t.pop*1000;return r===0?0:r<0.6?1:r<1.2?2:r<2.2?3:4}
/* percentile = share of census tracts with a strictly lower rate (same rule as scripts/families.py) */
function pctRanks(vals){const s=[...vals].sort((a,b)=>a-b);const n=s.length;return vals.map(v=>{let lo=0,hi=n;while(lo<hi){const m=(lo+hi)>>1;if(s[m]<v)lo=m+1;else hi=m}return 100*lo/n})}
const _rtc=new WeakMap();
function regionTracts(poly){if(poly==='city')return D.tracts;if(poly&&poly.tract)return [D.byTract[poly.tract]];if(_rtc.has(poly)&&_rtc.get(poly).T===D.tracts)return _rtc.get(poly).r;if(isMulti(poly)){const seen=new Set();return poly.flatMap(r=>regionTracts(r)).filter(t=>!seen.has(t.id)&&seen.add(t.id))}if(_rtc.has(poly)&&_rtc.get(poly).T===D.tracts)return _rtc.get(poly).r;
 const r=D.tracts.filter(t=>{if(inRing(t.c,poly))return true;const P=t.geometry.type==='Polygon'?[t.geometry.coordinates]:t.geometry.coordinates;let n=0,k=0;P.forEach(pl=>pl[0].forEach(v=>{n++;if(inRing(v,poly))k++}));return n&&k/n>=0.3});_rtc.set(poly,{T:D.tracts,r});return r}

/* ---------- map ---------- */
function MapView(el,o){
 this.el=el;this.o=o;const w=el.clientWidth,h=el.clientHeight;this.w=w;this.h=h;
 const pad=o.pad||28;
 this.proj=d3.geoMercator().fitExtent([[pad,pad+(o.padTop||0)],[w-pad,h-pad-(o.padBottom||0)]],D.city);
 if(o.focus){const f=o.focus;this.proj=d3.geoMercator().fitExtent([[pad,pad],[w-pad,h-pad]],{type:'Feature',geometry:{type:'Polygon',coordinates:[[ [f[0],f[1]],[f[0],f[3]],[f[2],f[3]],[f[2],f[1]],[f[0],f[1]] ]]}})}
 this.path=d3.geoPath(this.proj);
 const svg=this.svg=d3.select(el).append('svg').attr('width',w).attr('height',h);
 svg.append('defs').html(`<pattern id="hatchRaw" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="#E4E0D8"/><line x1="0" y1="0" x2="0" y2="5" stroke="#B9B3A8" stroke-width="1.2"/></pattern><pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="5" height="5" fill="${GAP[4]}"/><line x1="0" y1="0" x2="0" y2="5" stroke="#fff" stroke-opacity=".38" stroke-width="1.4"/></pattern><filter id="lift" x="-10%" y="-10%" width="120%" height="120%"><feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="#1B1B1B" flood-opacity=".28"/></filter>`);
 this.bg=svg.append('rect').attr('width',w).attr('height',h).attr('fill','transparent');
 this.gz=svg.append('g');
 const cid='cc'+Math.random().toString(36).slice(2,8);svg.select('defs').append('clipPath').attr('id',cid).append('path').attr('d',this.path(D.city));
 this.gT=this.gz.append('g').attr('clip-path',`url(#${cid})`);this.gH=this.gz.append('g').attr('clip-path',`url(#${cid})`);this.gMask=this.gz.append('g').attr('clip-path',`url(#${cid})`);this.gHi=this.gz.append('g');
 this.gCity=this.gz.append('g');this.gR=this.gz.append('g');this.selClip=svg.select('defs').append('clipPath').attr('id','s'+cid).append('path');this.gSel=this.gz.append('g').attr('clip-path',`url(#${cid})`).append('g').attr('clip-path',`url(#s${cid})`);
 [this.gH,this.gMask,this.gHi,this.gCity,this.gSel].forEach(g=>g.attr('pointer-events','none'));this.gR.raise();
 this.gD=svg.append('g');this.gP=svg.append('g');this.gDraw=svg.append('g');
 const self=this;
 this.tp=this.gT.selectAll('path').data(D.tracts).join('path').attr('d',d=>this.path(d.geometry)).attr('vector-effect','non-scaling-stroke')
  .on('mousemove',function(ev,d){if(self.o.onHover&&!self.drawing)self.o.onHover(d,d3.pointer(ev,self.svg.node()),self)})
  .on('mouseleave',function(){if(self.o.onHover)self.o.onHover(null,null,self)})
  .on('click',function(ev,d){if(self.armed||self.drawing||!self.o.onPick||Date.now()-(window.__drawEnd||0)<600)return;clearTimeout(self._ct);self._ct=setTimeout(()=>self.o.onPick(d,false),230)})
  .on('dblclick',function(ev,d){if(self.armed||self.drawing||!self.o.onPick||Date.now()-(window.__drawEnd||0)<600)return;ev.stopPropagation();clearTimeout(self._ct);self.o.onPick(d,true)});
 const outer=(g=>({type:'MultiPolygon',coordinates:(g.type==='Polygon'?[g.coordinates]:g.coordinates).map(p=>[p[0]])}))(D.city.geometry);this.gCity.append('path').attr('d',this.path(outer)).attr('fill','none').attr('stroke','#5C5C58').attr('stroke-width',1.2).attr('vector-effect','non-scaling-stroke');
 this.base=D.comments.map(c=>this.proj(c.ll));
 const sym={support:'M0,-2.1a2.1,2.1 0 1,0 0.01,0z',oppose:'M0,-2.6L2.4,1.8L-2.4,1.8z',neutral:'M-1.8,-1.8h3.6v3.6h-3.6z',unclear:'M0,-2.4L2.4,0L0,2.4L-2.4,0z',none:'M0,-1.6a1.6,1.6 0 1,0 0.01,0z'};
 this.dp=this.gD.selectAll('path').data([]).join('path').attr('d',c=>sym[stV(c)]).attr('fill',c=>COL[stV(c)]).attr('pointer-events','none');
 this.k=d3.zoomIdentity;
 if(!o.static){
  this.zoom=d3.zoom().scaleExtent([1,8]).filter(ev=>!self.drawing&&!self.armed&&(!ev.button||ev.type==='wheel')).on('zoom',ev=>{this.apply(ev.transform);if(!this._sync&&o.onZoom)o.onZoom(ev.transform,this)});
  svg.call(this.zoom).on('dblclick.zoom',null);
 }
 this.apply(d3.zoomIdentity);
}
MapView.prototype.apply=function(t){this.k=t;if(this.selT)this.placeSel();this.gz.attr('transform',t);const b=this.base;this.dp.attr('transform',(c,i)=>`translate(${(b[i][0]*t.k+t.x).toFixed(1)},${(b[i][1]*t.k+t.y).toFixed(1)})`);if(this.onApply)this.onApply()};
MapView.prototype.setT=function(t){this._sync=true;this.svg.call(this.zoom.transform,t);this._sync=false};
MapView.prototype.zoomBy=function(f){this.svg.transition().duration(250).call(this.zoom.scaleBy,f)};
MapView.prototype.reset=function(){this.svg.transition().duration(300).call(this.zoom.transform,d3.zoomIdentity)};
MapView.prototype.zoomTo=function(t){const [x,y]=this.proj(t.c);const k=Math.max(3,this.k.k);this.svg.transition().duration(500).call(this.zoom.transform,d3.zoomIdentity.translate(this.w/2-x*k,this.h/2-y*k).scale(k))};
MapView.prototype.fitTo=function(geo,box){let b;if(geo.pts){const P=geo.pts.map(p=>this.proj(p));b=[[Math.min(...P.map(p=>p[0])),Math.min(...P.map(p=>p[1]))],[Math.max(...P.map(p=>p[0])),Math.max(...P.map(p=>p[1]))]]}else b=this.path.bounds(geo);const bw=b[1][0]-b[0][0],bh=b[1][1]-b[0][1];const k=Math.max(1,Math.min(6,0.85*Math.min((box[2]-box[0])/bw,(box[3]-box[1])/bh)));const cx=(b[0][0]+b[1][0])/2,cy=(b[0][1]+b[1][1])/2;this.svg.transition().duration(450).call(this.zoom.transform,d3.zoomIdentity.translate((box[0]+box[2])/2-cx*k,(box[1]+box[3])/2-cy*k).scale(k))};
MapView.prototype.screen=function(ll){const p=this.proj(ll);return this.k.apply(p)};
MapView.prototype.toLL=function(p){return this.proj.invert(this.k.invert(p))};
MapView.prototype.style=function(st){
 const sch=st.scheme==='raw'||st.scheme==='pop'?'voice':st.scheme,inR=st.inRegion,hasR=!!inR;
 const cnt=st.cnt||{};const th=D.th||[1,5,10,18],sc=D.thSc||1;const hb=t=>{const n=cnt[t.id]??t.n;if(sch==='pop'){const r=n/t.pop*1000/sc;return r<0.6?1:r<1.2?2:r<2.2?3:4}return n<th[1]?1:n<th[2]?2:n<th[3]?3:4};
 const qb=D.qb||{voice:[1,2,3],prob:[1,2,3],gap:[1,2,3]};const qbin=(v,b)=>v<b[0]?1:v<b[1]?2:v<b[2]?3:4;const has311=!!ITEM.n311;
 const fill=t=>{if(sch==='prob')return !has311?'#ECEBE7':t.p311===0?'url(#hatchRaw)':PROB[qbin(t.prate,qb.prob)];
  if(sch==='gap'){if(!has311)return t.n===0?'url(#hatch)':GAPM[gapBin(t)];return t.pgap<=0?GAPM[0]:GAPM[qbin(t.pgap,qb.gap)]}
  return (cnt[t.id]??t.n)===0?'url(#hatchRaw)':RAW[qbin(t.vrate||0,qb.voice)]};
 const stroke='#FFFFFF';
 this.tp.attr('fill',st.empty?'#F7F7F5':fill).attr('stroke',st.empty?'#D6D6D0':stroke).attr('stroke-width',.8).attr('opacity',1);
 const polys=(st.polys||[]);const inP=ll=>!polys.length||polys.some(p=>inRing(ll,p));
 const ring=p=>'M'+p.map(q=>this.proj(q).join(',')).join('L')+'Z';
 this.gMask.selectAll('path').data(polys.length?[0]:[]).join('path').attr('d',`M-5000,-5000H${this.w+5000}V${this.h+5000}H-5000Z`+polys.map(ring).join('')).attr('fill-rule','evenodd').attr('fill','#FFFFFF').attr('fill-opacity',.6).attr('pointer-events','none');
 const vis=st.dotFilter;
 const op=st.empty?0:(sch==='gap'?.25:sch==='pop'?.4:.6);
 this.dp.attr('opacity',c=>(!vis(c))?0:(polys.length&&!inP(c.ll)?op*.3:op)).attr('display',c=>vis(c)?null:'none');
};
MapView.prototype.hover=function(t){this.gH.selectAll('path').data(t?[t]:[]).join('path').attr('d',d=>this.path(d.geometry)).attr('fill','none').attr('stroke','#1B1B1B').attr('stroke-width',2).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none')};
MapView.prototype.select=function(t){this.selT=t;this.selClip.attr('d',t?this.path(t.geometry):null);this.gSel.selectAll('path').data(t?[0,1]:[]).join('path').attr('d',i=>t?(i?this.path(D.city):this.path(t.geometry)):null).attr('fill',i=>i?'none':'rgba(255,241,168,.6)').attr('stroke','#1B1B1B').attr('stroke-width',5).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
 let lb=this.el.querySelector('.sellabel');if(!t){if(lb)lb.remove();return}if(!lb){lb=document.createElement('div');lb.className='sellabel';this.el.appendChild(lb)}lb.innerHTML=`<b>${t.nbhd}</b><span>Census tract ${t.id}</span>`;this.placeSel()};
MapView.prototype.placeSel=function(){const lb=this.el.querySelector('.sellabel');if(!lb||!this.selT)return;const cb=this.selT.cb||[this.selT.c[0],this.selT.c[1],this.selT.c[0],this.selT.c[1]];const p=this.k.apply(this.proj([(cb[0]+cb[2])/2,cb[3]]));lb.style.left=p[0]+'px';lb.style.top=(p[1]-8)+'px'};
MapView.prototype.regions=function(list){list=list.filter(r=>r.poly!=='city');const self=this;this.gR.raise();const at=ev=>{const ll=self.toLL(d3.pointer(ev,self.svg.node()));return D.tracts.find(t=>inGeom(ll,t.geometry))};
 const line=d3.line().curve(d3.curveLinearClosed);
 this.gR.selectAll('path').data(list).join('path').attr('d',r=>ringsOf(r.poly).map(g=>line(g.map(p=>this.proj(p)))).join('')).attr('fill',(r,i)=>list.length>1?CMPC[i%2]:GAP[4]).attr('fill-opacity',.1).attr('stroke',(r,i)=>list.length>1?CMPC[i%2]:GAP[4]).attr('stroke-width',2).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
 this.gR.selectAll('path').attr('pointer-events',this.o.static?'none':'all').style('cursor','pointer')
  .on('mousemove',function(ev,r){if(self.armed||self.drawing)return;const open=self.o.regionOpen&&self.o.regionOpen(r);d3.select(this).attr('fill-opacity',open?.1:.2);if(!open){if(self.o.onHover)self.o.onHover(null,null,self);return}const t=at(ev);if(self.o.onHover)self.o.onHover(t||null,t?d3.pointer(ev,self.svg.node()):null,self)})
  .on('mouseleave',function(){d3.select(this).attr('fill-opacity',.1);if(self.o.onHover)self.o.onHover(null,null,self)})
  .on('click',(ev,r)=>{if(self.armed||self.drawing||!self.o.onRegion||Date.now()-(window.__drawEnd||0)<600)return;clearTimeout(self._ct);self._ct=setTimeout(()=>self.o.onRegion(r),230)})
  .on('dblclick',(ev,r)=>{ev.stopPropagation();if(self.armed||self.drawing||!self.o.onPick||Date.now()-(window.__drawEnd||0)<600)return;if(!(self.o.regionOpen&&self.o.regionOpen(r))){clearTimeout(self._ct);self.o.onRegion(r);return}clearTimeout(self._ct);const t=at(ev);if(t)self.o.onPick(t,true)});
};
MapView.prototype.pulse=function(c){this.gP.selectAll('*').remove();if(!c)return;const i=D.comments.indexOf(c);const p=this.k.apply(this.base[i]);
 this.gP.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',7).attr('fill','none').attr('stroke',COL[stV(c)]).attr('stroke-width',2).attr('class','pulse');
 this.gP.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',3.6).attr('fill',COL[stV(c)]).attr('stroke','#fff').attr('stroke-width',1.2)};
MapView.prototype.armDraw=function(on,done,hint){
 this.armed=on;d3.select(this.el).classed('draw',on);const self=this,svg=this.svg;
 svg.on('click.draw',null).on('mousemove.draw',null).on('dblclick.draw',null).on('mouseleave.draw',null);d3.select(window).on('keydown.draw',null);
 this.gDraw.selectAll('*').remove();if(!on)return;
 let pts=[],cur=null;const SNAP=12;
 const fillEl=this.gDraw.append('path').attr('fill',GAP[4]).attr('fill-opacity',.08).attr('stroke','none');
 const lineEl=this.gDraw.append('path').attr('fill','none').attr('stroke',GAP[4]).attr('stroke-width',2);
 const rubber=this.gDraw.append('path').attr('fill','none').attr('stroke',GAP[4]).attr('stroke-width',1.5).attr('stroke-dasharray','5 4');
 const vg=this.gDraw.append('g');
 const near=p=>pts.length>=3&&Math.hypot(p[0]-pts[0][0],p[1]-pts[0][1])<SNAP;
 const upd=()=>{const snap=cur&&near(cur);const tip=snap?pts[0]:cur;
  lineEl.attr('d',pts.length>1?'M'+pts.map(p=>p.join(',')).join('L'):null);
  rubber.attr('d',pts.length&&tip?`M${pts[pts.length-1].join(',')}L${tip.join(',')}`+(pts.length>=2&&!snap?`L${pts[0].join(',')}`:''):null);
  fillEl.attr('d',pts.length>=2?'M'+[...pts,...(tip?[tip]:[])].map(p=>p.join(',')).join('L')+'Z':null);
  vg.selectAll('circle').data(pts).join('circle').attr('cx',d=>d[0]).attr('cy',d=>d[1]).attr('r',(d,i)=>i===0&&snap?7:i===0?5:3.5).attr('fill',(d,i)=>i===0?GAP[4]:'#fff').attr('stroke',(d,i)=>i===0&&snap?'#fff':GAP[4]).attr('stroke-width',(d,i)=>i===0?2:1.5);
  hint(!pts.length?'Click to place the first point':pts.length<3?'Click to add points':snap?'Click to close the shape':'Click the first point or double-click to finish · Backspace undoes · Esc cancels')};
 const finish=()=>{if(pts.length<3)return;self.drawing=false;const ll=pts.map(p=>self.toLL(p));self.armDraw(false);done(ll)};
 svg.on('click.draw',ev=>{const p=d3.pointer(ev,svg.node());if(near(p)){finish();return}if(ev.detail>1)return;pts.push(p);self.drawing=true;upd()})
 .on('dblclick.draw',ev=>{ev.preventDefault();finish()})
 .on('mousemove.draw',ev=>{cur=d3.pointer(ev,svg.node());upd()})
 .on('mouseleave.draw',()=>{cur=null;upd()});
 d3.select(window).on('keydown.draw',ev=>{if(ev.key==='Backspace'&&pts.length){ev.preventDefault();pts.pop();upd()}if(ev.key==='Enter')finish()});
 upd();
};

/* ---------- html helpers ---------- */
const H={};
H.legend=(sch)=>{
 if(sch==='raw'||sch==='pop')sch='voice';const qb=D.qb||{voice:[1,2,3],prob:[1,2,3],gap:[1,2,3]};const f=v=>v>=10?Math.round(v):v>=1?v.toFixed(1):v.toFixed(2);
 const lab=b=>{const r=(a,c)=>f(a)===f(c)?f(a):`${f(a)}–${f(c)}`;return ['0',`<${f(b[0])}`,r(b[0],b[1]),r(b[1],b[2]),`${f(b[2])}+`]};
 const ramp=(P,z)=>`<div class="ramp">${P.map((c,i)=>`<div style="background:${i?c:z}"></div>`).join('')}</div>`;
 const keyAll=`<details class="mapkey"${S_KEY.open?' open':''}><summary>Map key · all colors</summary>
  <div class="kr"><div class="ramp">${RAW.map((c,i)=>`<div style="background:${i?c:RAWZ}"></div>`).join('')}</div><b>Voice</b> · comments per 1,000 people</div>
  ${ITEM.n311?`<div class="kr"><div class="ramp">${PROB.map(c=>`<div style="background:${c}"></div>`).join('')}</div><b>Problems</b> · reports per 1,000 people a year</div>`:'<div class="kr muted"><b>Problems</b> · no data for this section</div>'}
  <div class="kr"><div class="ramp">${GAPM.map(c=>`<div style="background:${c}"></div>`).join('')}</div><b>Underheard</b> · ${ITEM.n311?'many problems, few comments':'fewest comments for its size'}</div></details>`;
 const L=(t,sub,r,l)=>`<div class="legend"><div class="lt">${t}</div><div class="small muted" style="margin:-4px 0 6px">${sub}</div>${r}<div class="rampl">${l.map(x=>`<span>${x}</span>`).join('')}</div>${keyAll}</div>`;
 if(sch==='prob'){if(!ITEM.n311)return '';return L('Problems · 311','Reported problems per 1,000 residents per year',ramp(PROB,PROB[0]),lab(qb.prob))}
 if(sch==='gap'){if(!ITEM.n311)return L('Underheard · participation gap','Comments vs. population share',ramp(GAPM,GAPM[0]),['0%','−30%','−55%','−80%','−100%']);
  return L('Underheard · problems without voice','Reported-problems rank − comment rank (0–100 each, per 1,000 residents)',ramp(GAPM,GAPM[0]),['≤0',`<${Math.round(qb.gap[0])}`,`${Math.round(qb.gap[0])}+`,`${Math.round(qb.gap[1])}+`,`${Math.round(qb.gap[2])}+`])}
 return L('Voice','Comments per 1,000 residents',ramp(RAW,RAWZ),lab(qb.voice))};
H.tip=(t)=>{const ex=t.exp.toFixed(1);if(t.n===0)return `<div class="h">${t.nbhd}</div><div class="s">Census tract ${t.id}</div><div class="zero">No comments located here</div><dl><dt>Expected from population share</dt><dd>${ex}</dd><dt>Population</dt><dd>${fmt(t.pop)}</dd><dt>Comments per 1k</dt><dd>${(t.vrate||0).toFixed(2)}</dd>${ITEM.n311?`<dt>Reported problems per 1k / yr</dt><dd>${(t.prate||0).toFixed(1)}</dd><dt>Reported problems rank</dt><dd class="gp">${Math.round(t.ppct||0)} of 100</dd><dt>Comments rank</dt><dd class="gp">${Math.round(t.vpct||0)} of 100</dd>${t.pwv?'<dt>Problems without voice</dt><dd class="gp">Yes</dd>':''}`:''}<dt>Renter households</dt><dd>${pct(t.renter)}</dd><dt>Limited-English households</dt><dd>${pct(t.lep)}</dd></dl>`;
 const tot=t.prec[0]+t.prec[1]+t.prec[2];
 return `<div class="h">${t.nbhd}</div><div class="s">Census tract ${t.id}</div><dl><dt>Population</dt><dd>${fmt(t.pop)}</dd><dt>Comments per 1k</dt><dd>${(t.vrate||0).toFixed(2)}</dd>${ITEM.n311?`<dt>Reported problems per 1k / yr</dt><dd>${(t.prate||0).toFixed(1)}</dd><dt>Reported problems rank</dt><dd class="gp">${Math.round(t.ppct||0)} of 100</dd><dt>Comments rank</dt><dd class="gp">${Math.round(t.vpct||0)} of 100</dd>${t.pwv?'<dt>Problems without voice</dt><dd class="gp">Yes</dd>':''}`:''}<dt>Comments located</dt><dd>${t.n}</dd><dt>Expected from population share</dt><dd>${ex}</dd><dt>Participation gap</dt><dd class="gp">${sgn(t.gap)}%</dd><dt>Renter households</dt><dd>${pct(t.renter)}</dd><dt>Limited-English households</dt><dd>${pct(t.lep)}</dd></dl><div class="pstrip"><div class="pbar"><i style="flex:${t.prec[1]};background:#5C5C58"></i><i style="flex:${t.prec[0]};background:#1B1B1B"></i><i style="flex:${t.prec[2]};background:#B6B0A5"></i></div><div class="small muted">located by: ${t.prec[1]} neighborhood · ${t.prec[0]} address · ${t.prec[2]} zip</div></div>`};
H.cite=(c,extra='')=>`<button class="cite" data-act="cite" data-id="${c.id}" data-src="Comment ${c.id} · ${c.src}${c.mock?' (simulated)':''} · ${fdate(c)}">${stIco(stV(c),9)}<code>${c.id.slice(0,7)}…</code><span class="tn">${c.t?c.t.nbhd:c.src}</span>${extra}</button>`;
H.src=(txt,src)=>`<span class="src" data-src="${esc(src)}">${txt}</span>`;
const incLabel=t=>{const r=t.income/D.medInc;return r<0.9?'Below San José median income':r>1.1?'Above San José median income':'Average San José median income'};
H.acs=(t)=>`<span class="acs">${pct(t.renter)} renters</span><span class="acs">${pct(t.lep)} limited-English</span><span class="acs">${incLabel(t)}</span>`;
H.howi=(src)=>`<span class="howi src" style="text-decoration:none" data-src="${esc(src)}">?</span>`;
H.thumb=(lab,id)=>`<div class="thumb" data-act="lightbox" data-lab="${esc(lab)}" data-id="${id||''}"><span class="bz">withheld</span><span class="lb">${lab}</span></div>`;
H.gauge=(di)=>{const sc=v=>Math.min(100,v/1.2*100);return `<div class="gauge"><div class="tr"></div><div class="fl" style="width:${sc(di)}%"></div><div class="th" style="left:${sc(.8)}%"></div><div class="tl" style="left:${sc(.8)}%;transform:translateX(calc(-100% - 5px))">0.8 threshold</div></div>`};
function briefFor(t,cs){const tc=cs.filter(c=>c.tract===t.id);const cats={};tc.forEach(c=>cats[c.cat]=(cats[c.cat]||0)+1);const top=Object.entries(cats).sort((a,b)=>b[1]-a[1])[0];
 let s=`${H.src(`${pct(t.renter)} of households in ${t.nbhd} (census tract ${t.id}) rent`,'ACS 5-year '+D.acsYears+' B25003 · tenure')} and ${H.src(`${pct(t.lep)} are limited-English households`,'ACS 5-year '+D.acsYears+' C16002 · household language')}. ${H.src(`${t.n} comment${t.n===1?' was':'s were'} located here against ${t.exp.toFixed(1)} expected from population share`,'Pipeline · census tract count vs. population share (ACS B01003)')}${t.n===0?'; no comments were located, so this brief makes no statement about residents’ views.':'.'} `;
 if(top&&tc.length){const c=tc.find(x=>x.cat===top[0]);s+=`The comments that were received most often concern ${H.src(CATN[top[0]].toLowerCase(),'Comment '+c.id+' and '+(top[1]-1)+' others')}. `}
 if(t.p311&&ITEM.n311)s+=`${H.src(`${fmt(t.p311)} problem reports in this section came from here through 311`,'San José 311 · '+D.m311+' months')}. `;
 s+=t.lep>D.thr.high_lep?'A notice in the main household languages and an in-person session nearby would reach the limited-English households counted here.':'A mailer and an in-person session nearby would reach the households counted here.';return s}

/* ---------- app ---------- */
async function mount(root,init){
 await load();
 const S=Object.assign({scheme:'voice',tab:'comments',sbs:false,left:true,right:true,fairOpen:false,filtersOpen:true,attr:'renter',drawer:false,region:null,regions:[],compare:false,rmode:'raw',stance:{support:1,oppose:1,neutral:1,unclear:1},cats:{},mvOpen:-1,affected:new Set(),state:null,chatRegion:true,inspector:null,lightbox:null,menu:null,armed:false,hint:null,pin:null,chatExtra:[],regionState:null,chat:[],chatBusy:false},init||{});
 const circ=(c,r)=>Array.from({length:28},(_,i)=>{const a=i/28*Math.PI*2;return [c[0]+Math.cos(a)*r*1.25,c[1]+Math.sin(a)*r]});
 const EAST={name:'East Side — Story Rd corridor',poly:EAST_REGION},WG={name:'Willow Glen — Lincoln Ave',poly:WG_REGION};
 if(S.region==='east')S.region=EAST;
 if(S.region==='tiny'){const t=[...D.tracts].sort((a,b)=>b.n-a.n)[0];S.region={name:t.nbhd+' — single census tract',poly:circ(t.c,0.0025)}}
 if(S.region==='empty')S.region={name:'Untitled region',poly:circ([-121.715,37.318],0.006)};
 if(S.compareInit){S.regions=[EAST,WG];S.region=EAST;S.compare=true}
 if(S.inspectKind){S.inspector=D.comments.find(c=>c.src==='Email'&&c.cat==='xwalk'&&c.t.e>0.4&&!c.tr)||D.comments.find(c=>c.src==='Email')}
 if(S.region&&!S.regions.length)S.regions=[S.region];
 S.saved=[EAST,WG];if(S.tab==='region'){S.modal=true;S.tab='chat'}if(!S.region&&!S.tractDetail&&S.state!=='noitem'){S.region={name:'All of San José',poly:'city'};S.regions=[S.region]}if(S.tab==='comments')S.tab='chat';
 const stage=document.createElement('div');stage.id='stage';root.appendChild(stage);
 /* Fill the window: scale so the 1440x900 design fits, then grow the canvas to the window's aspect. Extra width goes
    mostly to the chat panel (--rp), the rest to the map. Maps are measured at render, so a resize re-renders. */
 const BW=init.W||1440,BH=init.H||900;let _rt=null;
 const fit=()=>{const s=Math.min(innerWidth/BW,innerHeight/BH);const W=Math.max(BW,Math.floor(innerWidth/s)),Hh=Math.max(BH,Math.floor(innerHeight/s));
  stage.style.width=W+'px';stage.style.height=Hh+'px';stage.style.transform=`scale(${s})`;stage._s=s;
  stage.style.setProperty('--rp',Math.round(Math.min(620,288+(W-BW)*0.65))+'px')};
 fit();addEventListener('resize',()=>{fit();clearTimeout(_rt);_rt=setTimeout(()=>{if(typeof render==='function')render()},120)});
 let maps=[];
 const dotFilter=c=>(stV(c)==='none'||S.stance[c.stance])&&(!Object.keys(S.cats).length||S.cats[c.cat]||S.cats['sub:'+c.subKey]);
 const filtered=()=>D.comments.filter(dotFilter);
 const city=fairness(D.tracts,S.attr);
 const R=()=>S.region?regionTracts(S.region.poly):null;

 function top(){if(S.scheme==='raw'||S.scheme==='pop'||(S.scheme==='prob'&&!ITEM.n311))S.scheme='voice';const sch=S.scheme;return `<div class="top"><div class="brand"><b>CityLens</b><span>San José · Council staff</span></div><div class="vsep"></div>
 ${S.state==='noitem'?`<button class="picker" data-act="menu" data-m="item"><div><div class="t">Select a section</div><div class="m">No section loaded</div></div><span class="caret"></span></button>`:`<button class="picker" data-act="menu" data-m="item"><div style="min-width:0"><div class="t">${ITEM.title}</div><div class="m" title="${fmt(ITEM.total)} comments · ${srcLine(ITEM)}">${fmt(ITEM.total)} comments · ${srcLine(ITEM)}</div></div>${ITEM.n311?`<span class="badge">${n311(ITEM)}</span>`:''}<span class="caret"></span></button>`}
 ${S.view==='analytics'?`<button class="tbtn" data-act="back">${ICON.chevL}Back to map</button>${(S.region&&S.region.poly==='city'&&!S.tractDetail)?'':'<button class="tbtn" data-act="cityan">'+ICON.gauge+'City analytics</button>'}`:`<div class="seg" role="tablist" aria-label="Map scheme">${[['voice','Voice'],...(ITEM.n311?[['prob','Problems']]:[]),['gap','Underheard']].map(([k,l])=>`<button data-def="${{voice:'Voice: public comments per 1,000 residents. Where people are writing in to Council.',prob:'Problems: reported problems (311 service requests) per 1,000 residents per year. Where people report issues. A separate family from comments.',gap:ITEM.n311?'Underheard: reported-problems rank minus comment rank (0–100 each, per 1,000 residents). High where problems are reported but few comments come in.':'Underheard: how far each census tract falls below its population share of comments.'}[k]}" class="${!S.sbs&&sch===k?'on':''}" data-act="scheme" data-v="${k}">${l}</button>`).join('')}</div>
 <button class="tbtn ${S.sbs?'on':''}" data-act="sbs">${ICON.split}Side-by-side</button>${ITEM.n311?'':'<span class="nodata" style="height:28px"><i></i>No reported-problem data</span>'}`}
 <div class="spacer"></div>
 ${S.view==='analytics'?'':`<button class="tbtn" data-act="cityan">${ICON.gauge}City analytics</button>`}
  <button class="tbtn" data-act="menu" data-m="saved">Saved regions <span class="cnt">${S.saved.length}</span>${ICON.chevD}</button>
 ${S.menu==='item'?`<div class="menu" style="left:186px;width:440px"><div class="mh">Section</div>${D.itemOrder.map(k=>ITEMS[k]).map(d=>`<div class="mi" data-act="pickitem" data-id="${d.id}"><div><div style="font-weight:500">${d.title}</div><div class="small muted">${fmt(d.total)} comments · ${srcLine(d)} ${d.n311?' · '+n311(d):''}</div></div>${ITEM.id===d.id?'<span style="margin-left:auto;font-size:12px;color:var(--ink2);padding-top:2px">Current</span>':''}</div>`).join('')}</div>`:''}
 ${S.menu==='saved'?`<div class="menu" style="right:16px;width:300px">${S.saved.map((r,i)=>`<div class="mi" data-act="loadregion" data-i="${i}"><span style="width:10px;height:10px;border:1.5px dashed ${GAP[4]};border-radius:50%;margin-top:4px;flex:none"></span><div style="flex:1"><div style="font-weight:500">${esc(r.name)}</div><div class="small muted">${regionTracts(r.poly).length} census tracts</div></div></div>`).join('')}${S.saved.length>1?'<div style="border-top:1px solid var(--line);margin:6px -6px 0;padding:8px 10px 2px"><button class="btn" data-act="compare">Compare first two</button></div>':''}</div>`:''}
 </div>`}

 /* sections picked in the All sections filter (a subsection counts as its section: 311 has no subsections) */
 function sel311(){if(ITEM.id!=='all')return null;const ks=new Set();Object.keys(S.cats).forEach(k=>{if(k.startsWith('cat:'))ks.add(k.slice(4));else if(k.startsWith('sub:')){const d=(D.catDefs||[]).find(x=>x.subcategories.some(s=>'sub:'+s.key===k));if(d)ks.add(d.key)}});return ks.size?[...ks]:null}
 const tot311=k=>Object.values(D.p311[k]||{}).reduce((a,b)=>a+b,0);
 /* Problems view: the filter list counts 311 reports, not comments */
 function filters311(){const any=Object.keys(S.cats).length;const head=`<div class="sech"><h4>Filters</h4><button class="link" data-act="togglefilters">${S.filtersOpen?'Hide':'Show'}</button></div>`;
  const shown=D.tracts.reduce((a,t)=>a+t.p311,0);const total=ITEM.id==='all'?tot311('all'):tot311(ITEM.id);
  const foot=`<div class="small muted" style="margin-top:10px"><b class="num" style="color:var(--ink)">${fmt(shown)}</b> of ${fmt(total)} 311 reports on the map</div>`;
  if(!S.filtersOpen)return `<div class="sec">${head}${foot}</div>`;
  if(ITEM.id==='all'){const ks=(D.catDefs||[]).map(c=>c.key);const mx=Math.max(1,...ks.map(tot311));const sel=new Set(sel311()||[]);
   const rows=ks.map(k=>{const n=tot311(k);const on=sel.has(k);const lab=(ITEMS[k]||{}).title||D.p311Labels[k]||k;
    return n?`<button class="subrow ${on?'on':''} ${any&&!on?'dim':''}" data-act="cat" data-v="cat:${k}" aria-pressed="${on}"><span class="sbx">${on?'✓':''}</span><span class="snm">${esc(lab)}</span><span class="sct num">${fmt(n)}</span><span class="sbar"><i style="width:${n/mx*100}%"></i></span></button>`
     :`<div class="subrow nodata none" title="No 311 reports map to this section"><span class="sbx"></span><span class="snm">${esc(lab)}</span><span class="sct num">—</span></div>`}).join('');
   return `<div class="sec">${head}<div class="lbl" style="margin-top:0">Section · 311 reports</div><div class="sublist">${rows}</div>${foot}</div>`}
  const types=D.p311Tax.filter(x=>x.category===ITEM.id).sort((a,b)=>b.count-a.count);const mx=Math.max(1,...types.map(x=>x.count));
  return `<div class="sec">${head}<div class="lbl" style="margin-top:0">311 report types in this section</div><div class="sublist">${types.slice(0,12).map(x=>`<div class="subrow nodata"><span class="sbx" style="visibility:hidden"></span><span class="snm">${esc(x.service_type)}</span><span class="sct num">${fmt(x.count)}</span><span class="sbar"><i style="width:${x.count/mx*100}%"></i></span></div>`).join('')}</div>
   <div class="small muted" style="margin-top:8px">311 reports are counted by section, not subsection, so the map shows the whole section. Counts are citywide since July 2025.</div>${foot}</div>`}
 function filters(){if(S.scheme==='prob'&&!S.sbs&&ITEM.n311)return filters311();const fc=filtered();/* counts are every voice comment (letters and emails), placed on the map or not */const cc={};D.itemAll.forEach(c=>cc[c.cat]=(cc[c.cat]||0)+1);const sc={};D.itemAll.forEach(c=>sc[c.stance]=(sc[c.stance]||0)+1);const fa=D.itemAll.filter(dotFilter);
 return `<div class="sec"><div class="sech"><h4>Filters</h4><button class="link" data-act="togglefilters">${S.filtersOpen?'Hide':'Show'}</button></div>${S.filtersOpen?`
 <div class="lbl" style="margin-top:0">${ITEM.id==='all'?'Section':'Subcategory'}</div><div class="sublist">${(()=>{const mx=Math.max(1,CATS.reduce((t,c)=>t+(cc[c.k]||0),0));const any=Object.keys(S.cats).length;
  const row=(k,label,n,mxv,cls='')=>{const on=!!S.cats[k];return `<button class="subrow ${cls} ${on?'on':''} ${any&&!on?'dim':''}" data-act="cat" data-v="${k}" aria-pressed="${on}"><span class="sbx">${on?'✓':''}</span><span class="snm">${label}</span><span class="sct num">${n}</span><span class="sbar"><i style="width:${n/mxv*100}%"></i></span></button>`};
  return CATS.map(c=>{const n=cc[c.k]||0;if(ITEM.id!=='all')return row(c.k,c.n,n,mx);
   /* All sections: each section can open to filter by one of its subsections */
   const key=c.k.slice(4);const def=(D.catDefs||[]).find(x=>x.key===key);const subs=def?def.subcategories:[];const open=!!(S.catExp||{})[key];
   const sc={};D.itemAll.forEach(x=>{if(x.catKey===key)sc[x.subKey]=(sc[x.subKey]||0)+1});const smx=Math.max(1,...Object.values(sc));
   return `<div class="subgrp${open?' open':''}">${row(c.k,c.n,n,mx)}${subs.length?`<button class="sexp" data-act="catexp" data-v="${key}" aria-expanded="${open}" aria-label="${open?'Hide':'Show'} subsections of ${esc(c.n)}">${open?'▴':'▾'}</button>`:''}</div>${open?`<div class="subnest">${subs.filter(x=>sc[x.key]).map(x=>row('sub:'+x.key,esc(x.label),sc[x.key],smx,'nested')).join('')}</div>`:''}`}).join('')})()}</div>
 ${ITEM.id==='all'||!D.comments.some(c=>c.stance!=='none')?'':`<div class="lbl">Stance</div><div class="chips">${STANCES.map(s=>`<button class="fchip ${S.stance[s]?'on':''}" data-act="stance" data-v="${s}" aria-pressed="${!!S.stance[s]}">${stIco(s,9)}${stLabel[s]}<span class="ct num">${sc[s]||0}</span></button>`).join('')}</div>`}
 <div class="small muted" style="margin-top:10px"><b class="num" style="color:var(--ink)">${fmt(fa.length)}</b> of ${fmt(D.itemAll.length)} comments · ${fmt(fc.length)} on the map</div>`:`<div class="small muted">${fmt(fa.length)} of ${fmt(D.itemAll.length)} comments · ${fmt(fc.length)} on the map</div>`}</div>`}

 function fairCard(){const f=fairness(D.tracts,S.attr);const A=ATTRS[S.attr];const rk=ranks(D.comments,S.attr);
 const spdC=`${A.l} census tracts are ${Math.abs(Math.round(f.spd*100))} points ${f.spd<0?'less':'more'} likely to ${D.vMed===0?'have any located comment':'be above the citywide median comment rate'}.`;
 const diC='';
 const tiles=`<div class="tiles"><div class="tile full"><div class="k">Statistical parity difference ${H.howi('P(heard | '+A.l+') − P(heard | other) = '+f.pu.toFixed(2)+' − '+f.pp.toFixed(2))}</div><div class="v">${f.spd<0?'−':''}${Math.abs(f.spd).toFixed(2)}</div><div class="c">${spdC}</div></div><div class="tile full"><div class="k" style="justify-content:space-between"><span style="display:flex;gap:4px;align-items:center">Disparate impact ${H.howi('P(heard | '+A.l+') ÷ P(heard | other) = '+f.pu.toFixed(2)+' ÷ '+f.pp.toFixed(2))}</span>${(f.di!=null&&f.di<0.8)?'<span class="flag"><i></i>Below 0.8</span>':''}</div><div class="v">${fdi(f)}</div>${H.gauge(f.di||0)}</div></div>`;
 if(!S.fairOpen)return `<div class="fcard"><div class="sech"><h4>Fairness</h4><button class="link" data-act="fairopen">Expand</button></div><div class="small muted" style="margin-bottom:8px">Protected attribute: <b style="color:var(--ink);font-weight:500">${A.l}</b></div><div class="tiles"><div class="tile sm"><div class="k">SPD</div><div class="v">${f.spd<0?'−':''}${Math.abs(f.spd).toFixed(2)}</div></div><div class="tile sm"><div class="k">DI</div><div class="v">${fdi(f)}</div>${(f.di!=null&&f.di<0.8)?'<div style="margin-top:4px"><span class="flag"><i></i>Below 0.8</span></div>':''}</div></div></div>`;
 return `<div class="fcard"><div class="sech"><h4>Fairness</h4><button class="link" data-act="fairopen">Collapse</button></div>
 <label class="small muted" style="display:flex;align-items:center;gap:8px">Compared by<select data-act-change="attr" style="flex:1;min-width:0;font:inherit;font-size:12.5px;color:var(--ink);height:28px;border:1px solid var(--line);border-radius:4px;background:var(--panel);padding:0 6px">${Object.entries(ATTRS).map(([k,a])=>`<option value="${k}" ${S.attr===k?'selected':''}>${a.l}</option>`).join('')}</select></label>
 <div style="height:10px"></div>${tiles}
 <div style="margin:10px 0 14px"><button class="link" data-act="drawer">How is this computed?</button></div>
 <div style="border-top:1px solid #EEEEEA;padding-top:10px;display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px"><span class="muted">Top issue, raw</span><span>${(rk.find(r=>r.raw===1)||{}).n}</span><span class="muted">Top issue, pop.-weighted</span><span style="font-weight:600">${(rk.find(r=>r.pop===1)||{}).n}</span></div>
 </div>`}

 function drawer(){const A=ATTRS[S.attr];const f=fairness(D.tracts,S.attr);const m=D.attrMeta[A.key]||{};const thr=D.thr[A.key];return `<div class="drawer"><div class="ph"><h3>How the fairness numbers are computed</h3><button class="colbtn" data-act="drawer" aria-label="Close">×</button></div><div class="scroll" style="padding:4px 20px 20px">
 <h5>Heard census tract</h5><p>A census tract counts as heard for this section when its comments per 1,000 residents are above the citywide median of all ${D.tracts.length} census tracts (${D.vMed.toFixed(2)} per 1,000${D.vMed===0?', so any located comment counts':''}). The median is computed once for the whole city and never per region. Only comments that could be located count.</p>
 <h5>Statistical parity difference</h5><div class="formula">SPD = P(heard | ${A.s}) − P(heard | other)<br>= ${f.pu.toFixed(3)} − ${f.pp.toFixed(3)} = ${f.spd.toFixed(3)}</div><p class="muted">0 means both groups are equally likely to be heard. Negative means the group is less likely.</p>
 <h5>Disparate impact</h5><div class="formula">DI = P(heard | ${A.s}) ÷ P(heard | other)<br>= ${f.pu.toFixed(3)} ÷ ${f.pp.toFixed(3)} = ${f.di==null?'undefined (no other census tract is heard)':f.di.toFixed(3)}</div><p class="muted">Below 0.8 fails the four-fifths rule used in U.S. employment guidance; it is a reference line here, not a legal finding. These compare census tracts with a characteristic, not people.</p>
 <h5>Group counts</h5><table class="gc"><thead><tr><th>Group</th><th>Census tracts</th><th>Heard</th><th>Rate</th></tr></thead><tbody><tr><td>${A.l}</td><td>${f.nu}</td><td>${f.hu}</td><td>${f.pu.toFixed(2)}</td></tr><tr><td>Other census tracts</td><td>${f.np}</td><td>${f.hp}</td><td>${f.pp.toFixed(2)}</td></tr><tr><td class="muted">All census tracts</td><td>${f.nu+f.np}</td><td>${f.hu+f.hp}</td><td>${((f.hu+f.hp)/(f.nu+f.np)).toFixed(2)}</td></tr></tbody></table>
 <h5>Group definition</h5><p>${A.l}: ${S.attr==='renter'?'more than '+pct(thr)+' of occupied housing units are renter-occupied':S.attr==='income'?'median household income below $'+fmt(Math.round(thr))+' (the median of San José census tract medians)':S.attr==='nonwhite'?'more than '+pct(thr)+' of residents are not non-Hispanic white':'more than '+(thr*100).toFixed(1)+'% of households are limited-English (the 75th percentile of census tracts)'} (${A.acs}, ACS 5-year ${D.acsYears}). Cutoffs are set in the pipeline configuration, not chosen per view.</p>
 <h5>Theme ranking weights</h5><p><b style="font-weight:500">Raw</b>: each comment counts once. <b style="font-weight:500">Reweighed</b>: comments from each group are weighted so the group’s share of comments matches its share of population (Reweighing, Kamiran &amp; Calders 2012). <b style="font-weight:500">Population-weighted</b>: each census tract’s comments are scaled to its population. Census tracts with no comments contribute nothing to any ranking.</p>
 <h5>Data</h5><p class="muted">Letters are real (Legistar). Emails are simulated for the demo; any number that includes them is illustrative. 311 is real and is never added to comment counts.</p></div></div>`}

 function leftRail(){if(!S.left)return `<aside class="rail col"><div class="iconrail"><button data-act="left" aria-label="Expand filters">${ICON.chevR}</button><button class="on" data-act="left" title="Filters">${ICON.filter}</button><button data-act="left" title="Fairness">${ICON.gauge}</button></div></aside>`;
 if(S.state==='loading')return `<aside class="rail"><div class="ph"><h3>Filters</h3></div><div class="pad">${[80,180,140,200,120].map(w=>`<div class="skel" style="height:12px;width:${w/2}%;margin:10px 0"></div><div class="skel" style="height:26px;width:${w*0.45}%;margin-bottom:14px"></div>`).join('')}<div class="skel" style="height:150px;margin-top:20px"></div></div></aside>`;
 if(S.state==='noitem')return `<aside class="rail"><div class="ph"><h3>Filters</h3><button class="colbtn" data-act="left">${ICON.chevL}</button></div><div class="pad muted small">Filters and fairness metrics appear once an agenda item is loaded.</div></aside>`;
 return `<aside class="rail"><div class="ph"><h3>Filters</h3><button class="colbtn" data-act="left" aria-label="Collapse">${ICON.chevL}</button></div><div class="scroll">${filters()}</div></aside>`}

 function commentsTab(){const fc=(S.region?filtered().filter(c=>R().some(t=>t.id===c.tract)):filtered());return `<div class="ph" style="border-bottom:1px solid var(--line)"><div><h3>${fmt(fc.length)} comments</h3><div class="small muted">${S.region?'In '+S.region.name:'Located comments, current filters'} · newest first</div></div></div><div class="scroll">${fc.slice(0,40).map(c=>`<div class="ccard" data-act="inspect" data-id="${c.id}"><div class="crow"><span class="st ${c.stance}">${stIco(stV(c),10)}${stLabel[stV(c)]}</span><span class="cat">${CATN[c.cat]}</span>${c.camp?'<span class="cat" style="background:var(--bg)">Campaign</span>':''}${c.mock?'<span class="cat" style="background:var(--amberbg)">Simulated</span>':''}<span style="margin-left:auto">${fdate(c)}</span></div><div class="ctext">${esc(clip(c.text,420))}${c.langCode&&c.langCode!=='en'?`<span class="tr">${c.lang} · shown as written, not translated</span>`:''}</div><div class="crow"><span>${c.t.nbhd}</span>${c.photo?'<span>· 1 photo</span>':''}</div></div>`).join('')}</div>`}

 /* underheard = few comments for its population AND a reason to expect more: many reported problems (311 at or above the
    city rate) or many limited-English households. Few comments with few problems and normal factors = quiet, not underheard. */
 function underRule(){const C=D.cfg,U=C.underheard_rule||{};const T=D.tracts,pop=Math.max(1,D.totPop);
  const c311=T.reduce((a,t)=>a+(t.prate||0)*t.pop,0)/pop;const hh=T.reduce((s,t)=>s+(t.households||0),0);const cLep=hh?T.reduce((s,t)=>s+t.lep*(t.households||0),0)/hh:0;
  const low=t=>(t.exp>0?t.n/t.exp:1)<C.underrepresented_ratio;const prob=t=>!!ITEM.n311&&(t.prate||0)>=c311*(U.problems_vs_city??1);const lep=t=>t.lep>=cLep*(U.limited_english_vs_city??1.5);
  return {c311,cLep,low,prob,lep,is:t=>low(t)&&(prob(t)||lep(t)),quiet:t=>low(t)&&!prob(t)&&!lep(t)}}
 function missingTop(){const u=underRule();return D.tracts.filter(u.is).sort((a,b)=>(b.exp-b.n)-(a.exp-a.n)).slice(0,5)}
 function missingTab(){const list=missingTop();return `<div class="ph"><h3>Most underheard census tracts</h3></div><div class="scroll">${list.map((t,i)=>{const open=S.mvOpen===i;const b=gapBin(t);return `<div class="mvrow"><div class="mvhead" data-act="mv" data-i="${i}" style="${open?'background:#FFF8D6;box-shadow:inset 3px 0 0 #1B1B1B':''}"><div class="rankn">${i+1}</div><div><div class="mvname"><div><b>${t.nbhd}</b><div class="tid">Census tract ${t.id}</div></div><span style="color:var(--ink2)">${ICON.chevR}</span></div>
 <div class="gbar" style="margin:8px 0"><span class="num" style="width:44px;font-weight:600;color:#33205F">${sgn(t.gap)}%</span><div class="b"><i style="width:${Math.min(100,Math.abs(t.gap))}%;background:${t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 3px,#7B62B8 3px 4.5px)`:GAPM[b]}"></i></div></div>
 <div class="small muted num">${t.n} of ${Math.round(t.exp)} expected comments</div></div></div>
 ${open?`<div class="brief"><div class="bh">Outreach brief</div><p>${briefFor(t,D.comments)}</p><div class="btnrow"><button class="btn" data-act="zoomto" data-t="${t.id}">Zoom to census tract</button><button class="btn" data-act="copy">Copy brief</button></div></div>`:''}</div>`}).join('')}</div>`}

 const stat=(v,l)=>`<div class="stat"><b>${v}</b><span>${l}</span></div>`;
 function saidBars(cs,narrow){const tots=catTotals(cs,S.rmode,S.attr).filter(x=>x.count>0).sort((a,b)=>b.count-a.count).slice(0,5);if(!tots.length)return '<div class="small muted">No comments located here.</div>';const max=Math.max(...tots.map(x=>x.tot));const order=[...tots].sort((a,b)=>b.tot-a.tot);const rowH=34;
  return `<div class="bars" style="height:${tots.length*rowH}px">${tots.map(x=>{const y=order.indexOf(x)*rowH;const w=x.tot/max*100;const seg=s=>`<i style="flex:0 0 ${x[s]/Math.max(1e-9,x.tot)*100}%;background:${COL[s]}" title="${stLabel[s]}"></i>`;return `<div class="barrow" style="top:${y}px"><div class="bl"><span style="color:var(--ink)">${x.n}</span><span>${x.count}</span></div><div class="sbar" style="width:${Math.max(3,w)}%;height:8px">${seg('support')}${seg('oppose')}${seg('neutral')}${seg('unclear')}</div></div>`}).join('')}</div>`}
 function regionBlock(reg,narrow){const tr=regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const cs=filtered().filter(c=>ids.has(c.tract));const pop=tr.reduce((s,t)=>s+t.pop,0);const A=ATTRS[S.attr];
 if(!tr.length)return `<div class="rhead"><input class="rname" value="${esc(reg.name)}"></div><div class="pad"><div class="toofew"><b>Draw over at least one neighborhood.</b></div></div>`;
 const f=fairness(tr,S.attr);const tiny=tr.length===1;const totExp=tr.reduce((s,t)=>s+t.exp,0);
 const fairH=true?'':`<div class="sec"><div class="sech"><h4>Fairness</h4><span class="small muted">${A.l}</span></div>${f.few?`<div class="small muted">Too few census tracts in each group to compare fairly (${f.nu} vs ${f.np}).</div>`:`<div class="stats" style="grid-template-columns:1fr 1fr">${stat((f.spd<0?'−':'')+Math.abs(f.spd).toFixed(2),'Parity difference')}${stat(fdi(f)+(f.di<0.8?' <span class="flag" style="vertical-align:3px"><i></i>Below 0.8</span>':''),'Disparate impact')}</div>`}</div>`;
 const seen=new Set();const quotes=[];for(const c of cs){if(quotes.length>=3)break;if(seen.has(c.text)||c.camp)continue;seen.add(c.text);quotes.push(c)}
 const photos=cs.filter(c=>c.photo).slice(0,4);
 const silent=tr.filter(t=>t.n===0||gapBin(t)>=3).sort((a,b)=>(b.exp-b.n)-(a.exp-a.n));const lim=narrow?4:5;
 const sw=t=>t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 2px,#8A74C4 2px 3px)`:GAPM[gapBin(t)];
 return `<div class="rhead"><input class="rname" value="${esc(reg.name)}" aria-label="Region name" style="${narrow?'font-size:16px':''}"><div class="stats">${stat(tr.length,'census tracts')}${stat(fmt(pop),'residents')}${stat(cs.length+'<small> / '+Math.round(totExp)+'</small>','comments / expected')}</div></div>
 ${fairH}
 <div class="sec"><div class="sech"><h4>What residents said</h4><div class="seg sm">${[['raw','Raw'],['rw','Reweighed'],['pop','Pop.']].map(([k,l])=>`<button class="${S.rmode===k?'on':''}" data-act="rmode" data-v="${k}">${l}</button>`).join('')}</div></div>${saidBars(cs,narrow)}</div>
 ${silent.length?`<div class="sec"><div class="sech"><h4>Who we’re not hearing from</h4><span class="small muted">${silent.length}</span></div><div class="silent"><div class="cap">No comments located here — unknown, not absent.</div>${silent.slice(0,lim).map(t=>`<div class="srow" data-act="seltract" data-t="${t.id}" style="cursor:pointer;grid-template-columns:10px 1fr auto;align-items:center"><div class="sw" style="margin:0;background:${sw(t)}"></div><div style="font-weight:500">${t.nbhd} <span class="tid">${t.id}</span></div><div class="nums"><b>${t.n}</b> of ${Math.round(t.exp)}</div></div>`).join('')}${silent.length>lim?`<div class="srow" style="display:block;color:#33205F;font-size:12px">+ ${silent.length-lim} more</div>`:''}</div></div>`:''}
 ${quotes.length?`<div class="sec"><div class="sech"><h4>Quotes</h4></div>${quotes.map(c=>`<div class="quote" data-hover="${c.id}"><q>${esc(c.evq||clip(c.text,240))}</q><div class="crow"><span class="st ${c.stance}">${stIco(stV(c),10)}</span><span>${c.t.nbhd}</span><span style="margin-left:auto">${H.cite(c)}</span></div></div>`).join('')}</div>`:''}
 ${photos.length&&!narrow?`<div class="sec"><div class="sech"><h4>Photos</h4></div><div class="thumbs">${photos.map(c=>H.thumb(CATN[c.cat].split(' ')[0].toLowerCase()+' · '+c.t.nbhd,c.id)).join('')}</div></div>`:''}
 ${narrow?'':`<details class="sec bx"><summary><h4>Outreach brief</h4><button class="btn" data-act="copy">Copy brief</button></summary><p style="margin:10px 0 0;line-height:1.6;text-wrap:pretty">${regionBrief(tr,cs,silent)}</p></details>`}`}
 function tractBlock(t){const cs=filtered().filter(c=>c.tract===t.id);const seen=new Set();const quotes=[];for(const c of cs){if(quotes.length>=3)break;if(seen.has(c.text))continue;seen.add(c.text);quotes.push(c)}
 return `<div class="rhead">${S.region?`<button class="link" data-act="untract" style="margin-bottom:8px">← ${esc(S.region.name)}</button>`:''}<div style="font-size:20px;font-weight:500">${t.nbhd}</div><div class="tid" style="margin-bottom:10px">Census tract ${t.id}</div>
 <div class="stats" style="grid-template-columns:repeat(4,1fr)">${stat(fmt(t.pop),'residents')}${stat(t.n,'comments')}${stat(Math.round(t.exp),'expected')}${stat('<span style="color:var(--g4)">'+sgn(t.gap)+'%</span>','gap')}</div>
 <div class="chips" style="margin-top:12px">${H.acs(t)}</div></div>
 <div class="sec"><div class="sech"><h4>What residents said</h4></div>${saidBars(cs)}</div>
 ${t.n===0?`<div class="sec"><div class="silent"><div class="cap" style="border:0">No comments located here — unknown, not absent.</div></div></div>`:''}
 ${quotes.length?`<div class="sec"><div class="sech"><h4>Quotes</h4></div>${quotes.map(c=>`<div class="quote" data-hover="${c.id}"><q>${esc(c.evq||clip(c.text,240))}</q><div class="crow"><span class="st ${c.stance}">${stIco(stV(c),10)}${stLabel[stV(c)]}</span><span style="margin-left:auto">${H.cite(c)}</span></div></div>`).join('')}</div>`:''}
 <details class="sec bx"><summary><h4>Outreach brief</h4><button class="btn" data-act="copy">Copy brief</button></summary><p style="margin:10px 0 0;line-height:1.6;text-wrap:pretty">${briefFor(t,D.comments)}</p></details>`}
 function regionBrief(tr,cs,silent){const pop=tr.reduce((s,t)=>s+t.pop,0);const ren=tr.reduce((s,t)=>s+t.renter*t.pop,0)/pop;const lep=tr.reduce((s,t)=>s+t.lep*t.pop,0)/pop;const tot=catTotals(cs,'raw').sort((a,b)=>b.tot-a.tot)[0];const ex=cs.find(c=>c.cat===tot.k);const sp=silent.reduce((s,t)=>s+t.pop,0);
 return `This area has ${H.src(fmt(pop)+' residents across '+tr.length+' census tracts','ACS 5-year B01003 · total population')}, ${H.src(pct(ren)+' in renter households','ACS 5-year B25003')} and ${H.src(pct(lep)+' in limited-English households','ACS 5-year C16002')}. ${H.src(silent.length+' census tracts with '+fmt(sp)+' residents','Pipeline · census tracts with 0 comments or gap below −55%')} sent few or no comments. Among comments that were received, the most frequent topic is ${H.src(tot.n.toLowerCase(),'Comment '+(ex?ex.id:'')+' and '+(tot.count-1)+' others')}. A translated mailer and a session at a school in the area would reach the census tracts listed above.`}
 /* ---------- shared area facts (pop card + analytics) ---------- */
 function areaFacts(tr){const CT=D.tracts;const wavg=(L,f,w)=>{let a=0,b=0;L.forEach(t=>{const v=f(t);if(v!=null&&!isNaN(v)){a+=v*w(t);b+=w(t)}});return b?a/b:null};
  const byPop=t=>t.pop,byHH=t=>t.households||0;const pop=tr.reduce((s,t)=>s+t.pop,0)||1;
  const inc=tr.length===1?tr[0].income:wavg(tr,t=>t.income,byPop);const incR=inc/D.medInc-1;
  const isEPC=t=>['High','Higher','Highest'].includes(t.epc);const epcT=tr.filter(isEPC);
  return {pop,hh:tr.reduce((s,t)=>s+(t.households||0),0),inc,incR,incWord:incR>=0.1?'High':incR<=-0.1?'Low':'Average',
   eng:wavg(tr,t=>t.lang&&t.lang.english_only,byHH),engC:wavg(CT,t=>t.lang&&t.lang.english_only,byHH),
   lep:wavg(tr,t=>t.lep,byHH),lepC:wavg(CT,t=>t.lep,byHH),ren:wavg(tr,t=>t.renter,byPop),renC:wavg(CT,t=>t.renter,byPop),
   nw:wavg(tr,t=>t.nonwhite,byPop),nwC:wavg(CT,t=>t.nonwhite,byPop),epcT,epcPop:epcT.reduce((s,t)=>s+t.pop,0),isEPC,
   dists:[...new Set(tr.map(t=>t.district).filter(Boolean))].sort((a,b)=>a-b),wavg,byHH}}
 const P0=(x,d=0)=>x==null?'—':(x*100).toFixed(d)+'%';
 const incLine=f=>`${Math.abs(f.incR*100).toFixed(0)}% ${f.incR>=0?'above':'below'} city median ($${fmt(Math.round(D.medInc))})`;
 /* ---------- pop card ---------- */
 function popBlock(){
  const isT=!!S.tractDetail;const reg=S.region;const t0=isT?D.byTract[S.tractDetail]:null;const city=!isT&&reg&&reg.poly==='city';
  const tr=isT?[t0]:regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const cs=D.comments.filter(c=>ids.has(c.tract));
  const f=areaFacts(tr);const exp=tr.reduce((s,t)=>s+t.exp,0);
  const row=(v,l,sm)=>`<div class="prow"><span class="pl">${l}</span><b>${v}</b>${sm?`<span class="ps">${sm}</span>`:''}</div>`;
  let rows='';
  rows+=row(fmt(f.pop),'Residents',city?`${fmt(f.hh)} households`:isT?`${fmt(f.hh)} households · ${(f.pop/D.totPop*100).toFixed(2)}% of the city`:`${(f.pop/D.totPop*100).toFixed(1)}% of the city`);
  rows+=row(P0(f.eng),'English-only households',city?'':`${P0(f.engC)} citywide`);
  rows+=row(P0(f.ren),'Renter households',city?'':`${P0(f.renC)} citywide`);
  rows+=row(f.incWord,'Median income',incLine(f));
  const cnt={};cs.forEach(c=>cnt[c.cat]=(cnt[c.cat]||0)+1);const top=Object.entries(cnt).sort((a,b)=>b[1]-a[1])[0];
  const cc={};D.comments.forEach(c=>cc[c.cat]=(cc[c.cat]||0)+1);
  const gap=exp?Math.round((cs.length-exp)/exp*100):0;
  let fr=row(fmt(cs.length),'Comments located here',city?'':`${exp<1?exp.toFixed(1):Math.round(exp)} expected from population${cs.length?` (${sgn(gap)}%)`:''}`);
  fr+=top?row(esc(CATN[top[0]]),'Top issue',`${P0(top[1]/cs.length)} of comments here${city?'':` vs ${P0((cc[top[0]]||0)/Math.max(1,D.comments.length))} citywide`}`):cs.length?'':'<div class="prow"><span class="ps" style="grid-column:1/-1;text-align:left">No comments located here: unknown, not absent.</span></div>';
  if(ITEM.n311)fr+=row(fmt(tr.reduce((s,t)=>s+t.p311,0)),'311 problem reports','');
  const foot=`<div class="prows pfoot">${fr}</div>`;
  const title=isT?t0.nbhd:reg.name;const sub=isT?`Census tract ${t0.id}`:`${tr.length} census tracts`;
  return `<div class="rmh"><div style="min-width:0">${isT&&reg?`<button class="link" data-act="untract" style="font-size:11.5px">← ${esc(reg.name)}</button>`:''}<div class="pt">${esc(title)}</div><div class="small muted">${sub}</div></div><button class="colbtn" data-act="closemodal" aria-label="Close">×</button></div><div class="prows">${rows}</div>${foot}<div class="rmf"><button class="btn pri" data-act="analytics" style="width:100%;justify-content:center;height:32px">Open analytics</button></div>`}
 /* ---------- analytics dashboard: KPI tiles, then charts, every mark has a hover tip ---------- */
 const SEC_PAL=['#2a78d6','#eb6834','#1baf7a','#eda100','#e87ba4','#008300','#6250d6','#e34948'];
 const secCol=k=>{const i=D.catDefs.findIndex(x=>x.key===k);return i<0?'#8A8A85':SEC_PAL[i%8]};
 const tipA=s=>`data-tip="${esc(s).replace(/"/g,'&quot;')}"`;
 function delta(here,city,{fmtv=v=>v,unit='',ref='city'}={}){if(here==null||city==null||!isFinite(here)||!isFinite(city))return '';const d=city?here/city-1:null;if(d==null)return '';const up=d>0.005,dn=d<-0.005;
  return `<span class="dchip">${up?'▲':dn?'▼':'■'} ${Math.abs(d*100)>=999?'>999':Math.abs(d*100).toFixed(0)}% vs ${ref} <em>(${fmtv(city)}${unit})</em></span>`}
 function spark(vals,col,w=120,h=34){if(vals.length<2)return '';const mx=Math.max(...vals,1e-9),mn=Math.min(...vals);const x=i=>i/(vals.length-1)*w,y=v=>h-3-(v-mn)/Math.max(1e-9,mx-mn)*(h-6);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${vals.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v).toFixed(1)).join('')}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round"/><circle cx="${x(vals.length-1)}" cy="${y(vals[vals.length-1])}" r="3" fill="${col}"/></svg>`}
 function donut(segs,center,sub,size=168){const tot=segs.reduce((s,x)=>s+x.v,0)||1;const r=size/2,ri=r*0.62;let a0=-Math.PI/2;const arc=d3.arc().innerRadius(ri).outerRadius(r).padAngle(0.012).cornerRadius(2);
  const paths=segs.filter(s=>s.v>0).map(s=>{const a1=a0+s.v/tot*Math.PI*2;const d=arc({startAngle:a0+Math.PI/2,endAngle:a1+Math.PI/2});a0=a1;return `<path d="${d}" fill="${s.col}" ${tipA(`${s.label}: ${s.v} (${P0(s.v/tot)})`)}/>`}).join('');
  return `<svg width="${size}" height="${size}" viewBox="${-r} ${-r} ${size} ${size}" class="donut">${paths}<text text-anchor="middle" y="-2" class="dc">${center}</text><text text-anchor="middle" y="16" class="ds">${sub}</text></svg>`}
 function pairBars(rows,{a='Here',b='Citywide',colA='#2a78d6',colB='#C9C4BA',fmtv=P0}={}){const mx=Math.max(1e-9,...rows.flatMap(r=>[r.a,r.b]));
  const multi=rows.some(r=>r.col);return `<div class="pbars"><div class="pblg"><span><i style="background:${multi?`linear-gradient(90deg,${SEC_PAL.slice(0,4).join(",")})`:colA}"></i>${multi?a+" (section color)":a}</span><span><i style="background:${colB}"></i>${b}</span></div>${rows.map(r=>`<div class="pbr"><span class="pbl">${esc(r.label)}</span><div class="pbt"><i style="width:${Math.max(.6,r.a/mx*100)}%;background:${r.col||colA}" ${tipA(`${r.label} · ${a}: ${fmtv(r.a)}`)}></i><i style="width:${Math.max(.6,r.b/mx*100)}%;background:${colB}" ${tipA(`${r.label} · ${b}: ${fmtv(r.b)}`)}></i></div><span class="pbv"><b>${fmtv(r.a)}</b><em>${fmtv(r.b)}</em></span></div>`).join('')}</div>`}
 function lineChart(months,series,{w=520,h=170,unit=''}={}){if(months.length<2)return '<div class="note">Not enough months to draw a trend.</div>';const L=46,R=10,T=10,B=24;const iw=w-L-R,ih=h-T-B;
  const mx=Math.max(1e-9,...series.flatMap(s=>s.vals));const x=i=>L+i/(months.length-1)*iw,y=v=>T+ih-v/mx*ih;const ticks=[0,mx/2,mx];
  const grid=ticks.map(t=>`<line x1="${L}" x2="${w-R}" y1="${y(t)}" y2="${y(t)}" class="gl"/><text x="${L-6}" y="${y(t)+4}" text-anchor="end" class="ax">${t>=10?Math.round(t):t.toFixed(1)}</text>`).join('');
  const xl=months.map((m,i)=>i%Math.ceil(months.length/8)===0||i===months.length-1?`<text x="${x(i)}" y="${h-6}" text-anchor="middle" class="ax">${m.slice(2)}</text>`:'').join('');
  const lines=series.map(s=>`<path d="${s.vals.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v).toFixed(1)).join('')}" fill="none" stroke="${s.col}" stroke-width="2" ${s.dash?'stroke-dasharray="4 3"':''} stroke-linejoin="round"/><text x="${x(months.length-1)+4}" y="${y(s.vals[s.vals.length-1])+4}" class="ax" style="fill:var(--ink)">${''}</text>`).join('');
  const hits=months.map((m,i)=>`<rect x="${x(i)-iw/(months.length-1)/2}" y="${T}" width="${iw/(months.length-1)}" height="${ih}" fill="transparent" ${tipA(`${m}${i===months.length-1?' (partial month)':''} · `+series.map(s=>`${s.name}: ${s.vals[i].toFixed(1)}${unit}`).join(' · '))}/>`).join('');
  return `<svg class="lc" width="100%" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">${grid}${lines}${xl}${hits}</svg><div class="pblg">${series.map(s=>`<span><i style="background:${s.col}"></i>${s.name}</span>`).join('')}</div>`}
 function analyticsView(){
  const C=D.cfg;const kind=S.tractDetail?'tract':(S.region&&S.region.poly==='city')?'city':'region';
  const reg=S.tractDetail?{name:D.byTract[S.tractDetail].nbhd,sub:'Census tract '+S.tractDetail,poly:{tract:S.tractDetail}}:S.region;
  const tr=regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const CT=D.tracts;const city=kind==='city';
  const scope=city?D.itemAll:D.itemAll.filter(c=>c.tract&&ids.has(c.tract));const loc=scope.filter(c=>c.t);const W=city?scope:loc;
  const f=areaFacts(tr);const pop=f.pop;const P=P0;
  const card=(q,lead,body,cls='')=>`<section class="card ${cls}"><h4><span class="dfl"${defA(q)}>${q}</span></h4>${lead?`<p class="lead">${lead}</p>`:''}${body}</section>`;
  const small=n=>n<C.small_n?`<span class="nodata" style="margin-left:6px"><i></i>small sample · ${n}</span>`:'';
  const cnt=(L,fn)=>{const o={};L.forEach(c=>{const k=fn(c);o[k]=(o[k]||0)+1});return o};const secLabel=k=>(ITEMS[k]||{}).title||k;
  /* monthly 311 per 1k: area vs city */
  const ms=D.p311months;const mser=T=>{const p=T.reduce((s,t)=>s+t.pop,0)||1;return ms.map(m=>T.reduce((s,t)=>s+((D.p311m[t.id]||{})[m]||0),0)/p*1000)};
  const areaM=mser(tr),cityM=city?areaM:mser(CT);
  const rate311=areaM.reduce((a,b)=>a+b,0)*12/ms.length,rate311C=cityM.reduce((a,b)=>a+b,0)*12/ms.length;
  const act=W.filter(c=>c.actionable!=null),actY=act.filter(c=>c.actionable).length,actR=act.length?actY/act.length:null;
  const actC=D.itemAll.filter(c=>c.actionable!=null),actRC=actC.length?actC.filter(c=>c.actionable).length/actC.length:null;
  const locAll=D.comments.length||1;const cShare=loc.length/locAll,pShare=pop/D.totPop,rr=pShare?cShare/pShare:null;
  /* ---- header facts strip ---- */
  const fact=(l,v,s)=>`<div class="hf"><span class="dfl"${defA(l)}>${l}</span><b>${v}</b>${s?`<em>${s}</em>`:''}</div>`;
  const head=`<section class="card span2 hfacts"><div class="hfs">${fact('Residents',fmt(pop),`${fmt(f.hh)} households`)}${fact('English-only households',P(f.eng),city?'':'city '+P(f.engC))}${fact('Limited-English',P(f.lep),city?'':'city '+P(f.lepC))}${fact('Renters',P(f.ren),city?'':'city '+P(f.renC))}${fact('Median income',f.incWord,incLine(f))}${fact('Equity Priority',kind==='tract'?(f.isEPC(tr[0])?tr[0].epc:'No'):`${f.epcT.length} of ${tr.length} census tracts`,'MTC 2024')}</div></section>`;
  /* ---- KPI tiles ---- */
  const tile=(label,big,sub,extra='',cls='')=>`<div class="kpi ${cls}"><div class="kl"><span class="dfl"${defA(label)}>${label}</span></div><div class="kb">${big}</div><div class="ks">${sub}</div>${extra}</div>`;
  const expN=tr.reduce((s,t)=>s+t.exp,0);
  const silent=(city?CT:tr).filter(t=>t.n===0);
  const kpis=`<section class="span2 kpis">
   ${tile(city?'Comments (no copies)':'Comments located here',fmt(city?scope.length:loc.length),city?`${fmt(D.rawRows)} incl. copies · ${P(loc.length/Math.max(1,scope.length))} on the map`:`${expN<1?expN.toFixed(1):Math.round(expN)} expected from population`,'', 'hero')}
   ${city?tile('Residents where we heard nothing',P(silent.reduce((s,t)=>s+t.pop,0)/D.totPop),`${fmt(silent.length)} of ${CT.length} census tracts sent no located comment`,'','hero'):tile('Representation ratio',rr==null?'—':rr.toFixed(2),rr==null?'':rr>=1?`sends ${rr.toFixed(1)}× its share of comments`:`gets ${P(rr)} of its fair share`,`<div class="bullet" ${tipA(`1.0 = comment share equals population share`)}><i style="width:${Math.min(100,(rr||0)/3*100)}%"></i><b style="left:${100/3}%"></b><span>0</span><span style="left:${100/3}%">1.0</span><span style="right:0">3+</span></div>`,'hero')}
   ${ITEM.n311?tile('311 problem reports / 1,000 / yr',rate311.toFixed(0),city?`${fmt(tr.reduce((s,t)=>s+((D.p311.all||{})[t.id]||0),0))} reports in ${ms.length} months`:delta(rate311,rate311C,{fmtv:v=>v.toFixed(0)}),spark(areaM,'#22877C')):tile('311 problem reports','—','no 311 data for this section')}
   ${tile('Ask for a specific fix',P(actR),city?`${fmt(actY)} of ${fmt(act.length)} report a problem or request an action, not just a vote`:delta(actR,actRC,{fmtv:v=>P(v)}))}
  </section>`;
  /* ---- trust ---- */
  const confs=W.map(c=>c.conf).filter(x=>x!=null);const mean=confs.length?confs.reduce((a,b)=>a+b,0)/confs.length:null;
  const meter=(l,v,s)=>`<div class="mt" ${tipA(`${l}: ${P(v)}`)}><div class="mtl"><span class="dfl"${defA(l)}>${l}</span><b>${P(v)}</b></div><div class="mtb"><i style="width:${(v||0)*100}%"></i></div>${s?`<em>${s}</em>`:''}</div>`;
  const trust=card('How much to trust these numbers','Read every number below with these in mind.',`<div class="mts">${meter('Placed on the map',scope.length?loc.length/scope.length:null,'the rest gave no usable location')}${meter('Real (not simulated)',W.length?1-W.filter(c=>c.mock).length/W.length:null,'simulated emails make numbers illustrative')}${meter('Average AI label confidence',mean,'every label cites an exact quote')}${meter('Labeled by IBM Bob',W.length?W.filter(c=>c.engine==='bob').length/W.length:null,'not yet checked against human review')}</div>`,'span2');
  let M=trust+head+kpis;
  /* ---- what people write about: donut + here vs city ---- */
  const here=cnt(W,c=>c.catKey),cityC=cnt(D.itemAll,c=>c.catKey);const totC=D.itemAll.length||1;
  const keys=D.catDefs.map(c=>c.key).filter(k=>(here[k]||0)>0||(!city&&(cityC[k]||0)>0));
  const segs=keys.map(k=>({k,label:secLabel(k),v:here[k]||0,col:secCol(k)})).filter(s=>s.v>0).sort((a,b)=>b.v-a.v);
  const top=segs[0];
  const legend=`<div class="dleg">${segs.map(s=>{const sub=cnt(W.filter(c=>c.catKey===s.k),c=>c.subKey);const cd=D.catDefs.find(x=>x.key===s.k);const ts=Object.entries(sub).sort((a,b)=>b[1]-a[1])[0];
   return `<div class="dl" ${tipA(`${s.label}: ${s.v}${ts?` · top subsection ${((cd&&cd.subcategories.find(x=>x.key===ts[0]))||{}).label||ts[0]} (${ts[1]})`:''}`)}><i style="background:${s.col}"></i><span><a class="link" data-act="pickitem" data-id="${s.k}">${esc(s.label)}</a><em>${ts?esc(((cd&&cd.subcategories.find(x=>x.key===ts[0]))||{}).label||''):''}</em></span><b>${s.v}</b><u>${P(s.v/Math.max(1,W.length))}</u></div>`}).join('')}</div>`;
  M+=card('What people write about',W.length?`<b>${esc(top.label)}</b> leads with ${P(top.v/W.length)} of comments${city?'':`, vs ${P((cityC[top.k]||0)/totC)} citywide`}.${small(W.length)}`:'No comments located here — unknown, not absent.',
   W.length?`<div class="dwrap">${donut(segs,fmt(W.length),'comments')}${legend}</div>`:'','span2');
  if(!city&&W.length)M+=card('Here vs citywide','Share of comments by section. Bars in a section’s color are this area; gray is the city.',pairBars(keys.map(k=>({label:secLabel(k),a:(here[k]||0)/W.length,b:(cityC[k]||0)/totC,col:secCol(k)})).sort((a,b)=>b.a-a.a||b.b-a.b)));
  /* ---- stance, policy sections: diverging ---- */
  const pol=C.policy_sections.filter(k=>W.some(c=>c.catKey===k));
  if(pol.length){const rows=pol.map(k=>{const L=W.filter(c=>c.catKey===k);const st=s=>L.filter(c=>c.stance===s).length;return {k,n:L.length,s:st('support'),o:st('oppose'),u:st('neutral')+st('unclear')}});const mx=Math.max(1,...rows.map(r=>Math.max(r.s,r.o)));
   M+=card('Support vs opposition',`Policy sections only. ${(()=>{const r=[...rows].sort((a,b)=>(b.o/b.n)-(a.o/a.n))[0];return r.o?`Most contested: <b>${esc(secLabel(r.k))}</b> (${P(r.o/r.n)} oppose).`:''})()}`,
    `<div class="div"><div class="dvh"><span>oppose</span><span>support</span></div>${rows.map(r=>{const net=r.s+r.o?Math.round((r.s-r.o)/(r.s+r.o)*100):0;return `<div class="dvr"><div class="dvl">${esc(secLabel(r.k))}<em>${r.n} comments · ${r.u} neutral/unclear</em></div><div class="dvb"><div class="dvo"><i style="width:${r.o/mx*100}%" ${tipA(`${secLabel(r.k)}: ${r.o} oppose`)}></i></div><div class="dvs"><i style="width:${r.s/mx*100}%" ${tipA(`${secLabel(r.k)}: ${r.s} support`)}></i></div></div><b class="dvn">${sgn(net)}</b></div>`}).join('')}<div class="note">Net = (support − oppose) ÷ (support + oppose). Service sections are about problems, so no stance is shown for them.</div></div>`)}
  /* ---- 311 ---- */
  if(ITEM.n311){const by={};Object.keys(D.p311).filter(k=>k!=='all').forEach(k=>{by[k]=tr.reduce((s,t)=>s+((D.p311[k]||{})[t.id]||0),0)});const tot=Object.values(by).reduce((a,b)=>a+b,0)||1;const tk=Object.entries(by).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]);
   const pwv=(city?CT:tr).filter(t=>t.pwv).length;
   M+=card('311 problem reports over time',`${city?'':`<b>${rate311.toFixed(0)}</b> per 1,000 residents a year vs <b>${rate311C.toFixed(0)}</b> citywide. `}Monthly reports per 1,000 residents.`,lineChart(ms,city?[{name:'San José',col:'#22877C',vals:areaM}]:[{name:esc(reg.name),col:'#22877C',vals:areaM},{name:'Citywide',col:'#8A8A85',vals:cityM,dash:1}],{unit:' per 1,000'})+'<div class="note">The last month is partial (data through Oct 22). 311 is counted separately and never added to comments.</div>');
   M+=card('What people report to 311',`Mostly <b>${esc((D.p311Labels[tk[0][0]]||tk[0][0]).toLowerCase())}</b>: ${P(tk[0][1]/tot)} of ${fmt(tot)} reports.${pwv?` ${pwv} census tract${pwv===1?'':'s'} here report many problems but send few comments.`:''}`,
    `<div class="mix">${tk.map(([k,n])=>`<div class="mxr" ${tipA(`${D.p311Labels[k]||k}: ${fmt(n)} reports (${P(n/tot)})`)}><span>${esc(D.p311Labels[k]||k)}</span><div><i style="width:${n/tk[0][1]*100}%;background:${secCol(k)}"></i></div><b>${fmt(n)}</b><em>${P(n/tot)}</em></div>`).join('')}</div>`)}
  /* ---- who is writing + languages ---- */
  const parts=new Set(W.map(c=>c.participant||c.id)).size;
  const L5=['english_only','spanish','asian_pacific','other_indo_european','other'];const LN={english_only:'English',spanish:'Spanish',asian_pacific:'Asian & Pac. Isl.',other_indo_european:'Other Indo-Eur.',other:'Other'};
  const cl={english_only:W.filter(c=>c.langCode==='en').length,spanish:W.filter(c=>c.langCode==='es').length,asian_pacific:W.filter(c=>c.langCode==='vi').length};
  const lrows=L5.map(k=>({label:LN[k],a:W.length&&cl[k]!=null?cl[k]/W.length:0,b:f.wavg(tr,t=>t.lang&&t.lang[k],f.byHH)||0,k}));
  const sp=lrows[1];
  M+=card('Languages',W.length?`${sp.b>0.08?`Spanish is <b>${P(sp.b)}</b> of households but <b>${P(sp.a)}</b> of comments.`:'Comment languages vs household languages.'}`:'No comments located here.',W.length?pairBars(lrows,{a:'Comments',b:'Households (ACS)',colA:'#B3412B'})+`<div class="note">Language comments were written in vs language spoken at home (ACS C16002). Vietnamese counts under Asian &amp; Pacific Island. Compares languages, not people.${small(W.length)}</div>`:'');
  const mini=(v,l,s)=>`<div class="mk"><b>${v}</b><span>${l}</span>${s?`<em>${s}</em>`:''}</div>`;
  M+=card('Who is writing',W.length?`<b>${fmt(parts)}</b> distinct writers sent ${fmt(W.length)} comments.`:'',W.length?`<div class="mks">${mini((W.length/Math.max(1,parts)).toFixed(2),'comments per writer','1.00 = everyone wrote once')}${mini(P(W.filter(c=>c.camp).length/W.length),'form-letter copies','organized campaigns')}${mini(fmt(W.filter(c=>c.commenter==='organization').length),'from organizations','')}${mini(P(W.filter(c=>c.mock).length/W.length),'simulated','demo emails')}</div>`:'');
  /* ---- city: timeline + locality ---- */
  if(city){const months={};scope.forEach(c=>{if(!c.when)return;const m=c.when.toISOString().slice(0,7);(months[m]=months[m]||{L:0,E:0})[c.src==='Letter'?'L':'E']++});const mk=Object.keys(months).sort();const mm=Math.max(1,...mk.map(m=>months[m].L+months[m].E));
   M+=card('When comments arrived','Real letters cover early 2025; simulated emails cover fall 2026. Gaps are months with no ingested data.',`<div class="tbars">${mk.map(m=>{const v=months[m];return `<div ${tipA(`${m}: ${v.L} letters, ${v.E} simulated emails`)}><i style="height:${v.E/mm*100}%;background:#E8957D"></i><i style="height:${v.L/mm*100}%;background:#8E2A1C"></i><span>${m.slice(2)}</span></div>`}).join('')}</div><div class="pblg"><span><i style="background:#8E2A1C"></i>letters (real)</span><span><i style="background:#E8957D"></i>emails (simulated)</span></div>`);
   const conc=D.catDefs.map(c=>c.key).map(k=>{const L=loc.filter(c=>c.catKey===k);if(L.length<5)return null;const o=cnt(L,c=>c.tract);const [tid,n]=Object.entries(o).sort((a,b)=>b[1]-a[1])[0];return {k,tid,n,N:L.length}}).filter(Boolean).sort((a,b)=>b.n/b.N-a.n/a.N);
   M+=card('Local or citywide?',conc.length?`<b>${esc(secLabel(conc[0].k))}</b> is the most local: ${P(conc[0].n/conc[0].N)} of its located comments come from one census tract.`:'Too few located comments.',`<div class="mix">${conc.map(r=>`<div class="mxr" ${tipA(`${secLabel(r.k)}: ${r.n} of ${r.N} located comments from ${D.byTract[r.tid].nbhd}`)}><span>${esc(secLabel(r.k))}</span><div><i style="width:${r.n/r.N*100}%;background:${secCol(r.k)}"></i></div><b><a class="link" data-act="seltract" data-t="${r.tid}">${esc(D.byTract[r.tid].nbhd)}</a></b><em>${P(r.n/r.N)}</em></div>`).join('')}</div><div class="note">Share of a section’s located comments from its busiest tract.</div>`)}
  /* ---- missing voices ---- */
  if(kind!=='tract'){const mode=t=>{const o={};D.comments.forEach(c=>{if(c.tract===t.id)o[c.cat]=(o[c.cat]||0)+1});const e=Object.entries(o).sort((a,b)=>b[1]-a[1])[0];return e?CATN[e[0]]:'—'};
   const UR=underRule();const under=tr.filter(UR.is);const quiet=tr.filter(UR.quiet);const sortK=S.mvSort||(ITEM.n311?'ratio':'pop');
   const vr=t=>t.pop?t.n/t.pop*1000:0;const cV=D.tracts.reduce((a,t)=>a+t.n,0)/Math.max(1,D.totPop)*1000;const c311r=D.tracts.reduce((a,t)=>a+(t.prate||0)*t.pop,0)/Math.max(1,D.totPop);
   const idx=t=>(t.prate>0&&cV>0)?(vr(t)/t.prate)/(cV/c311r):null;/* voice per problem report, relative to the city (1 = city level) */
   const keyF={pop:t=>t.pop,p311:t=>t.prate||0,lep:t=>t.lep,voice:t=>-vr(t),ratio:t=>-(idx(t)??9)*1e6+(t.prate||0)}[sortK]||(t=>t.pop);const list=[...under].sort((a,b)=>keyF(b)-keyF(a)).slice(0,10);
   const uPop=under.reduce((s,t)=>s+t.pop,0);const has311=!!ITEM.n311;
   const hh=D.tracts.reduce((s,t)=>s+(t.households||0),0);const cLep=hh?D.tracts.reduce((s,t)=>s+t.lep*(t.households||0),0)/hh:0;
   const heat=r=>r==null?'':r<0.1?'h0':r<0.35?'h1':r<0.6?'h2':r<0.9?'h3':'h4';
   const th=(k,l,sub,cls='')=>`<th class="srt${sortK===k?' on':''} ${cls}" data-act="mvsort" data-v="${k}" title="Sort by ${l}">${l}${sortK===k?' ▾':''}${sub?`<em>${sub}</em>`:''}</th>`;
      M+=card('Who we are not hearing from',`<b>${fmt(under.length)}</b> census tract${under.length===1?'':'s'} ${city?'citywide':'here'} send under ${C.underrepresented_ratio}× their population share of comments ${ITEM.n311?'while reporting many problems or having many limited-English households':'and have many limited-English households'} — home to <b>${fmt(uPop)}</b> residents${city?` (${P(uPop/D.totPop)} of the city)`:''}.${quiet.length?` <span class="muted">${quiet.length} more send few comments but also report few problems, so they are counted as quiet, not underheard.</span>`:''}`,
    under.length?`<div class="mvt"><div class="mvkey"><span>Voice for its problems:</span><span class="hk h0">almost none</span><span class="hk h1">low</span><span class="hk h2">below city</span><span class="hk h3">near city</span><span class="hk h4">city level+</span><span class="muted">· click a column to sort</span></div>
    <table class="mvtab"><thead><tr><th class="l">Census tract</th>${th('pop','Residents')}${th('voice','Voice',`per 1,000 residents · city ${cV.toFixed(2)}`)}${has311?th('p311','311 reports',`per 1,000 a year · city ${Math.round(c311r)}`):''}${has311?th('ratio','Voice for its problems','voice ÷ 311, vs city','rt'):''}${th('lep','Limited-English',`households · city ${P(cLep)}`)}</tr></thead><tbody>
    ${list.map(t=>{const r=idx(t);return `<tr data-act="seltract" data-t="${t.id}"><td class="l"><b>${esc(t.nbhd)}</b>${UR.prob(t)?'<span class="why wp">many problems</span>':''}${UR.lep(t)?'<span class="why wl">limited English</span>':''}${['High','Higher','Highest'].includes(t.epc)?'<span class="epc">Equity Priority</span>':''}</td>
     <td ${tipA(`${t.nbhd}: ${fmt(t.pop)} residents`)}>${fmt(t.pop)}</td>
     <td ${tipA(`${t.nbhd}: ${t.n} email${t.n===1?'':'s'} and messages located here (${vr(t).toFixed(2)} per 1,000 residents); about ${t.exp.toFixed(1)} expected from its share of residents`)}>${t.n?`<b>${vr(t).toFixed(2)}</b><span class="muted"> · ${t.n}</span>`:'<span class="muted">none</span>'}</td>
     ${has311?`<td ${tipA(`${t.nbhd}: ${Math.round(t.prate||0)} 311 problem reports per 1,000 residents a year; city ${Math.round(c311r)}`)}><b>${Math.round(t.prate||0)}</b></td>
     <td class="rt" ${tipA(`${t.nbhd}: ${r==null?'no 311 data':r.toFixed(2)+'× the city’s voice per 311 report. Below 1 means fewer messages for its problems than the city overall.'}`)}><span class="hc ${heat(r)}">${r==null?'—':r<0.01?'none':r.toFixed(2)+'×'}</span></td>`:''}
     <td ${tipA(`${t.nbhd}: ${P(t.lep)} of households are limited-English; city ${P(cLep)}`)}><span class="lp${t.lep>=cLep*1.5?' hi':''}">${P(t.lep)}</span></td></tr>`}).join('')}</tbody></table>
    <div class="note">Click a row to open that census tract on the map. Low comment counts can also mean writers did not say where they live (${P(ITEM.pct/100)} of comments could be located).</div></div>
    <details class="bx" style="margin-top:12px"><summary><h4>All census tracts in this area</h4></summary><table class="ht tt" style="margin-top:8px"><thead><tr><th>Census tract</th><th>Residents</th><th>Comments</th><th>Expected</th><th>Gap</th><th>Top issue</th></tr></thead><tbody>${[...tr].sort((a,b)=>a.gap-b.gap).map(t=>`<tr><td><a class="link" data-act="seltract" data-t="${t.id}" style="font-size:12px">${t.nbhd}</a> <span class="tid">${t.id}</span></td><td>${fmt(t.pop)}</td><td>${t.n}</td><td>${Math.round(t.exp)}</td><td style="color:var(--g4);font-weight:500">${sgn(t.gap)}%</td><td>${mode(t)}</td></tr>`).join('')}</tbody></table></details>`:'<div class="note">No census tract here is underheard: those sending few comments also report few problems and have few limited-English households.</div>','span2')}
  const side=`<aside class="anside"><div class="mini" data-act="back" title="Back to map"><div class="map" id="mini"></div><span>← Back to map</span></div><div><h1>${esc(reg.name)}</h1><div class="small muted">${kind==='tract'?reg.sub:city?`${fmt(CT.length)} census tracts`:`${tr.length} census tracts`}${f.dists.length?` · council district${f.dists.length>1?'s':''} ${f.dists.join(', ')}`:''}</div></div>${ITEM.id!=='all'?`<div class="small">Showing <b>${esc(ITEM.title)}</b> only · <button class="link" data-act="pickitem" data-id="all">show all sections</button></div>`:''}</aside>`;
  return `<div class="body"><div class="an">${side}<div class="anmain dash">${M}</div></div>${rightPanel()}</div>`}
 function placePop(){const el=document.querySelector('.rmodal.pop');const m=maps[0];if(!el||!m)return;/* always top-left, under the city label, so it never covers the selection */
  el.style.left='16px';el.style.top='64px';el.style.maxHeight=Math.max(200,m.h-80)+'px';el.style.overflowY='auto'}
 function regionTab(){
  if(S.regionState==='loading')return `<div class="progress"><i></i></div><div class="pad">${[60,30].map(w=>`<div class="skel" style="height:20px;width:${w}%;margin-bottom:8px"></div>`).join('')}<div class="tiles" style="margin:14px 0"><div class="skel" style="height:80px"></div><div class="skel" style="height:80px"></div></div>${[90,70,55,40,30].map(w=>`<div class="skel" style="height:10px;width:30%;margin:12px 0 5px"></div><div class="skel" style="height:16px;width:${w}%"></div>`).join('')}<div class="skel" style="height:70px;margin-top:18px"></div></div>`;
  if(S.tractDetail)return `<div class="scroll">${tractBlock(D.byTract[S.tractDetail])}</div>`;
  if(!S.region)return `<div class="pad"><div class="toofew"><b>No region drawn.</b><div class="small muted" style="margin:4px 0 10px">Use Draw region in the top bar, then click on the map to place points. Click the first point to close.</div><button class="btn" data-act="draw">${ICON.pen}Draw region</button></div></div>`;
  if(S.compare&&S.regions.length>1)return `<div style="display:grid;grid-template-columns:1fr 1fr;min-height:0;flex:1"><div class="scroll" style="border-right:1px solid var(--line)">${regionBlock(S.regions[0],true)}</div><div class="scroll">${regionBlock(S.regions[1],true)}</div></div>`;
  return `<div class="scroll">${regionBlock(S.region)}</div>`}

 /* ---------- chat: the in-app assistant (IBM Bob behind /api/assistant, search fallback in static builds) ---------- */
 function chatScope(){const drawn=!!S.region&&Array.isArray(S.region.poly);const useR=S.chatRegion&&(drawn||!!S.tractDetail);const cmp=S.compare&&S.regions.length>1&&!S.tractDetail;
  const tr=S.tractDetail?[D.byTract[S.tractDetail]]:cmp?[...new Map(S.regions.flatMap(r=>regionTracts(r.poly)).map(t=>[t.id,t])).values()]:drawn?regionTracts(S.region.poly):[];const ids=new Set(tr.map(t=>t.id));
  const cs=useR?D.itemAll.filter(c=>c.tract&&ids.has(c.tract)):D.itemAll;
  const label=S.tractDetail?`${D.byTract[S.tractDetail].nbhd} (census tract ${S.tractDetail})`:useR?(cmp?S.regions.map(r=>r.name).join(' + '):S.region.name):'All of San José';
  return {useR,tr,cs,label}}
 function chatNumbers(sc){const cs=sc.cs;const cnt=f=>{const o={};cs.forEach(c=>{const k=f(c);o[k]=(o[k]||0)+1});return o};
  const T=sc.useR?sc.tr:D.tracts;const pop=T.reduce((s,t)=>s+t.pop,0);const by={};Object.keys(D.p311).filter(k=>k!=='all').forEach(k=>{by[D.p311Labels[k]||k]=T.reduce((s,t)=>s+((D.p311[k]||{})[t.id]||0),0)});
  const tot=Object.values(by).reduce((a,b)=>a+b,0);
  return {scope:sc.label,section:ITEM.title,
   voice:{comments_no_copies:cs.length,located:cs.filter(c=>c.t).length,simulated:cs.filter(c=>c.mock).length,by_section:cnt(c=>(ITEMS[c.catKey]||{}).title||c.catKey),by_stance:cnt(c=>c.stance),by_channel:cnt(c=>c.src),actionable:cs.filter(c=>c.actionable).length},
   requests_311:{problem_reports:tot,residents:pop,per_1000_per_year:pop?+(tot/pop*1000*12/D.m311).toFixed(1):null,by_category:by,months:D.m311}}}
 function mdLite(txt){/* the assistant's markdown subset: **bold**, ### heading, - bullets, 1. numbered, paragraphs */
  const lines=esc(txt||'').replace(/\r/g,'').split('\n');let out='',list=null;const close=()=>{if(list){out+=`</${list}>`;list=null}};
  const inl=s=>s.replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/(^|\s)\*([^*\s][^*]*)\*(?=\s|[.,;:]|$)/g,'$1<i>$2</i>');
  lines.forEach(l=>{const t=l.trim();let m;
   if(!t){close();return}
   if((m=t.match(/^#{1,4}\s+(.*)$/))){close();out+=`<h5 class="mdh">${inl(m[1])}</h5>`;return}
   if((m=t.match(/^[-•*]\s+(.*)$/))){if(list!=='ul'){close();out+='<ul class="mdl">';list='ul'}out+=`<li>${inl(m[1])}</li>`;return}
   if((m=t.match(/^\d+[.)]\s+(.*)$/))){if(list!=='ol'){close();out+='<ol class="mdl">';list='ol'}out+=`<li>${inl(m[1])}</li>`;return}
   close();out+=`<p>${inl(t)}</p>`});close();return out}
 function chatText(txt){let h=mdLite(txt);
  return h.replace(/\[\[([^\]]+)\]\]/g,(m,id)=>{if(id.startsWith('metric:')){const k=id.slice(7);const mm=(D.metrics||{})[k];return `<button class="cite" data-act="srcview" data-ref="${esc(id)}" data-src="Metric ${esc(k)}${mm?' · '+esc(mm.name):''} · click to view"><code>${esc(k)}</code><span class="tn">${mm?esc(clip(mm.name,28)):'metric'}</span></button>`}
   if(id.startsWith('file:')){const f=id.slice(5);return `<button class="cite" data-act="srcview" data-ref="${esc(id)}" data-src="${esc(f)} · click to view"><span class="tn">source · ${esc(clip(f.replace(/^public\/data\//,'').replace(/^data\//,''),34))}</span></button>`}
   const c=D.voice.find(x=>x.id===id);return c?H.cite(c):''})}
 const ACT_LABEL={select_section:a=>'opened '+((ITEMS[a.id]||{}).title||a.id),set_scheme:a=>'switched the map to '+({voice:'Voice',prob:'Problems',gap:'Underheard'}[a.id]||a.id),zoom_tract:a=>'zoomed to '+((D.byTract[a.id]||{}).nbhd||a.id),open_analytics:a=>'opened '+a.scope+' analytics',open_comment:a=>'opened comment '+a.id,filter_stance:a=>'filtered stance to '+(a.ids||[]).join(', '),set_view:a=>a.id==='sbs'?'opened side-by-side maps':'went back to the single map',select_district:a=>`opened Council District ${a.id} (${a.tracts.length} census tracts)`,select_area:a=>`opened ${a.name} (${a.tracts.length} census tracts)`,select_tracts:a=>`opened ${a.name} (${a.ids.length} census tracts)`,compare_places:a=>`compared ${(a.places||[]).map(p=>p.name).join(' and ')}`};
 function runActions(acts){let zoom=null;(acts||[]).forEach(a=>{
  if(a.type==='select_section'&&ITEMS[a.id]){setItem(a.id);S.cats={}}
  else if(a.type==='set_scheme'){S.scheme=a.id;S.sbs=false;S.view='main'}
  else if(a.type==='zoom_tract'&&D.byTract[a.id]){S.view='main';S.selTract=a.id;S.tractDetail=a.id;S.modal=true;zoom=a.id}
  else if(a.type==='open_analytics'){if(a.section&&ITEMS[a.section]){setItem(a.section);S.cats={}}if(a.scope==='city'){S.tractDetail=null;S.region={name:'All of San José',poly:'city'};S.regions=[S.region]}S.view='analytics';S.modal=false}
  else if(a.type==='set_view'){S.view='main';S.sbs=a.id==='sbs';S.armed=false}
  else if(a.type==='compare_places'&&Array.isArray(a.places)){comparePlaces(a.places)}
  else if((a.type==='select_district'||a.type==='select_area'||a.type==='select_tracts')){const ids=(a.tracts||a.ids||[]).filter(i=>D.byTract[i]);if(ids.length){regionFromTracts(ids,a.type==='select_district'?`Council District ${a.id}`:a.name);S.view='main';S.sbs=false}}
  else if(a.type==='open_comment'){const c=D.voice.find(x=>x.id===a.id);if(c)S.inspector=c}
  else if(a.type==='filter_stance'&&Array.isArray(a.ids)){STANCES.forEach(s=>S.stance[s]=a.ids.includes(s)?1:0)}});return zoom}
 async function sendChat(q){q=(q||'').trim();if(!q||S.chatBusy)return;const sc=chatScope();const entry={q,pending:true,scope:sc.label};S.chat.push(entry);S.chatBusy=true;render();
  const comments=sc.cs.map(c=>({id:c.id,text:c.text,subject:c.subject,section:(ITEMS[c.catKey]||{}).title||c.catKey,subsection:CATN['sub:'+c.subKey]||(D.catDefs.find(x=>x.key===c.catKey)?.subcategories.find(s=>s.key===c.subKey)||{}).label||'',stance:c.stance,lang:c.lang,mock:c.mock,nbhd:c.t?c.t.nbhd:'',tract:c.tract,evq:c.evq}));
  const history=S.chat.filter(e=>!e.pending&&e.res).slice(-3).map(e=>({q:e.q,text:e.res.text}));
  let res;try{res=await askAssistant({question:q,scopeLabel:sc.label,sectionTitle:ITEM.title,sectionKey:ITEM.id,comments,numbers:chatNumbers(sc),history,regionTracts:sc.useR?sc.tr.map(t=>t.id):undefined})}catch(e){res={text:'',cited:[],engine:'search',note:'Something went wrong. Try again.'}}
  entry.pending=false;entry.res=res;S.chatBusy=false;const zoom=runActions(res.actions);entry.did=(res.actions||[]).map(a=>(ACT_LABEL[a.type]||(()=>a.type))(a));render();
  if(zoom)maps.forEach(m=>m.zoomTo(D.byTract[zoom]));const sc2=document.querySelector('.rpanel .scroll');if(sc2)sc2.scrollTop=sc2.scrollHeight}
 function chatTab(){const sc=chatScope();const ctx=S.tractDetail?D.byTract[S.tractDetail].nbhd:S.region?S.region.name:null;
  const sugg=sc.useR?['What are people here most concerned about?','Who are we not hearing from here?','How many 311 reports come from here, and what kind?','Open analytics for this area']:['What are the top concerns citywide?','Which neighborhoods report many problems but send few comments?','Show me the Underheard map','How is the fairness number computed?'];
  const msgs=S.chat.map(e=>`<div class="mu">${esc(e.q)}</div>${e.pending?`<div class="ma"><div class="who">Assistant</div><p class="muted"><span class="skel" style="display:inline-block;width:10px;height:10px;border-radius:50%;vertical-align:-1px"></span> Working on it… looking through comments and app data for ${esc(e.scope)}</p></div>`:
   (()=>{const r=e.res||{};const body=r.text?`<div class="md">${chatText(r.text)}</div>`:'';const note=r.note?`<p class="small muted" style="margin:0">${esc(r.note)}</p>`:'';const did=e.did&&e.did.length?`<div class="small" style="color:#33205F;margin-top:4px">Did: ${esc(e.did.join(' · '))}</div>`:'';
    return `<div class="ma${!r.text&&!did?' refuse':''}"><div class="who">Assistant${r.engine==='search'?' · search only':''}</div>${body||note?body+note:'<p class="muted" style="margin:0">No answer.</p>'}${did}</div>`})()}`).join('');
  const empty=`<div class="ma"><div class="who">Assistant</div><p style="margin:0 0 8px">Ask about comments, 311 reports, neighborhoods, metrics, or how a number is computed. I can also move around the app: open a section, switch the map, zoom to a census tract, open analytics.</p><div style="display:flex;flex-direction:column;gap:6px">${sugg.map(s=>`<button class="btn" style="justify-content:flex-start;height:auto;min-height:30px;padding:5px 10px;text-align:left;white-space:normal" data-act="suggest" data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div></div>`;
  return `${ctx?`<div class="ctxbar"><div style="min-width:0"><div class="small muted">${S.tractDetail?'Census tract':'Region'}</div><div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${esc(ctx)}">${esc(ctx)}</div></div>${S.view==='analytics'?'':'<button class="btn" data-act="analytics">View analytics</button>'}</div>`:''}<div class="scroll"><div class="msgs">${S.chat.length?msgs:empty}</div></div><div class="compose"><div class="notice"><i></i>Answers come only from the comments and data in this app, with sources. Not public-facing.</div><div class="cbox">${sc.useR?`<div>${(()=>{const nm=S.tractDetail?'Census tract: '+D.byTract[S.tractDetail].nbhd:'Region: '+S.region.name.replace(/^Drawn region — /,'');return `<span class="composer-chip" title="${esc(nm)}"><span class="cct">${esc(nm)}</span>${S.tractDetail?'':`<span class="ccn">· ${sc.tr.length} census tract${sc.tr.length===1?"":"s"}</span>`}`})()}<button data-act="rmchip" aria-label="Remove region">×</button></span></div>`:''}<textarea rows="2" placeholder="Ask anything about this app's data" ${S.chatBusy?'disabled':''}></textarea><div class="r"><span>${S.chat.length?'<button class="link" data-act="clearchat">Clear</button>':''}</span><button class="btn pri" style="height:30px" data-act="send" ${S.chatBusy?'disabled':''}>${S.chatBusy?'Working…':'Send'}</button></div></div></div>`}
 function rightPanel(){const tabs=[['chat','Chat',ICON.chat]];S.tab='chat';
 if(!S.right)return `<aside class="rpanel col"><div class="iconrail"><button data-act="right" aria-label="Expand panel">${ICON.chevL}</button>${tabs.map(t=>`<button class="${S.tab===t[0]?'on':''}" data-act="tab" data-v="${t[0]}" title="${t[1]}">${t[2]}</button>`).join('')}</div></aside>`;
 let body='';
 if(S.state==='loading')body=`<div class="pad">${[1,2,3,4,5].map(()=>`<div style="padding:10px 0;border-bottom:1px solid #EEEEEA"><div class="skel" style="height:12px;width:40%;margin-bottom:8px"></div><div class="skel" style="height:12px;width:95%;margin-bottom:5px"></div><div class="skel" style="height:12px;width:70%"></div></div>`).join('')}</div>`;
 else if(S.state==='noitem')body=`<div class="pad muted small">Comments, Missing Voices, and Chat appear once an agenda item is loaded.</div>`;

 else body=S.tab==='comments'?commentsTab():S.tab==='missing'?missingTab():S.tab==='region'?regionTab():chatTab();
 return `<aside class="rpanel"><div class="tabs">${tabs.map(t=>`<button class="${S.tab===t[0]?'on':''} ${t[0]==='region'&&!S.region&&!S.tractDetail?'dis':''}" data-act="tab" data-v="${t[0]}">${t[1]}</button>`).join('')}<span class="sp"></span><button class="colbtn" data-act="right" aria-label="Collapse">${ICON.chevR}</button></div><div style="flex:1;display:flex;flex-direction:column;min-height:0">${body}</div></aside>`}

 function footer(){const tiers=Object.fromEntries(ITEM.tiers||[]);const T=ITEM.total||1;const p=x=>Math.round(x/T*100)+'%';const row=(l,n)=>`<dt>${l}</dt><dd style="margin:0">${fmt(n)}</dd><dd style="margin:0">${p(n)}</dd>`;
 return `<footer class="foot"><div class="fi">Sources: <a href="https://sanjose.legistar.com" target="_blank" rel="noopener">Legistar letters from the public</a>, simulated emails, <a href="https://data.sanjoseca.gov/dataset/311-service-request-data" target="_blank" rel="noopener">San José 311</a>, <a href="https://www.census.gov/programs-surveys/acs" target="_blank" rel="noopener">ACS 5-year ${D.acsYears}</a>, <a href="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html" target="_blank" rel="noopener">Census TIGER 2024</a></div><div class="fi"><b>${D.tracts.length}</b> census tracts</div><div class="fi covwrap">Coverage <b>${ITEM.pct}%</b> located <span class="howi">?</span><div class="covtip" style="left:0"><div class="pbar" style="height:6px"><i style="flex:${tiers.address||0};background:#1B1B1B"></i><i style="flex:${tiers.neighborhood||0};background:#5C5C58"></i><i style="flex:${tiers.zip||0};background:#B6B0A5"></i><i style="flex:${(tiers.district||0)+(tiers.none||0)};background:#EFEFEB"></i></div><dl style="display:grid;grid-template-columns:1fr auto auto;gap:3px 10px;margin:6px 0 0" class="num">${row('Address',tiers.address||0)}${row('Neighborhood',tiers.neighborhood||0)}${row('ZIP only',tiers.zip||0)}${row('District only',tiers.district||0)}${row('Not located',tiers.none||0)}</dl></div></div><div class="fi">${ITEM.simulated?`<b>${fmt(ITEM.simulated)}</b>&nbsp;of ${fmt(ITEM.total)} simulated`:'All comments real'}</div><div class="fi">Labels: ${ITEM.fallback?`<b style="color:#6B4710">${ITEM.fallback} rule-based</b>`:'AI-labeled, every label cites its quote'}</div></footer>`}

 function mapArea(){
  if(S.sbs)return `<div class="mapwrap"><div class="maps"><div class="map" id="m0"><div class="mlabel">Voice <span>comments per 1k</span></div>${H.legend('voice')}</div><div class="divider"></div><div class="map" id="m1"><div class="mlabel">Underheard <span>${ITEM.n311?'problems without voice':'participation gap'}</span></div>${H.legend('gap')}</div></div></div>`;
  return `<div class="mapwrap"><div class="maps"><div class="map" id="m0"><div class="citylabel">San José<span>City limits · ${D.tracts.length} census tracts</span></div>${S.state==='noitem'?'':H.legend(S.scheme)}${S.modal&&(S.region||S.tractDetail)&&!S.regionState?`<div class="rmodal pop${S.compare&&S.regions.length>1&&!S.tractDetail?' cmpw':''}" role="dialog">${S.compare&&S.regions.length>1&&!S.tractDetail?popCompare():popBlock()}</div>`:''}${S.state==='noitem'?'':`<button class="tbtn mapdraw ${S.armed?'armed':''}" data-act="draw">${ICON.pen}${S.armed?'Drawing… Esc to cancel':'Draw region'}</button>`}<div class="zoomc"><button data-act="zin" aria-label="Zoom in">+</button><button data-act="zout" aria-label="Zoom out">−</button><button data-act="zreset" aria-label="Whole city">City</button></div>${(()=>{const rs=S.region&&Array.isArray(S.region.poly)&&!S.compare?ringsOf(S.region.poly):[];if(!rs.length||S.sbs)return '';if(S.region.area)return `<div class="drawlist"><div class="dlh"><span>Area</span></div><div class="dli"><i></i><span><b>${esc(S.region.name)}</b><em>${regionTracts(S.region.poly).length} census tracts</em></span><button data-act="closealldraw" aria-label="Close area" title="Close this area">×</button></div></div>`;return `<div class="drawlist"><div class="dlh"><span>Drawings · ${rs.length}</span><span>${S.saved.includes(S.region)?'<span class="muted" style="text-transform:none;letter-spacing:0">Saved</span>':'<button class="link" data-act="save">Save</button>'}${rs.length>1?' · <button class="link" data-act="closealldraw">Close all</button>':''}</span></div>${rs.map((g,i)=>{const tr=regionTracts(g);const nb=tr.length?D.byTract[tr[0].id].nbhd:'Empty area';return `<div class="dli"><i></i><span><b>${esc(nb)}</b><em>${tr.length} census tract${tr.length===1?'':'s'}</em></span><button data-act="closedraw" data-i="${i}" aria-label="Close drawing" title="Close this drawing">×</button></div>`}).join('')}</div>`})()}${S.menu==='city'?`<div class="menu" style="top:14px;right:52px;min-width:240px"><div class="mi" data-act="cityregion"><div><div style="font-weight:500">Select all of San José</div><div class="small muted">${D.tracts.length} census tracts · opens in Region</div></div></div></div>`:''}${S.state==='noitem'?`<div class="centerprompt"><h2>Choose an agenda item</h2><p>Every census tract in San José is shown. Pick an item to place its public comments.</p><p style="margin:0;font-size:12.5px">Use the item picker in the top bar.</p></div>`:''}</div></div></div>`}

 const tip=document.createElement('div');tip.className='ttip';tip.style.display='none';
 const srcTip=document.createElement('div');srcTip.className='srctip';srcTip.style.display='none';document.body.appendChild(srcTip);
 function onHover(t,p,mv){maps.forEach(m=>m.hover(t));if(!t){if(!S.pin)tip.style.display='none';return}showTip(t,p,mv)}
 function showTip(t,p,mv){mv.el.appendChild(tip);tip.innerHTML=H.tip(t);tip.style.display='block';let x=p[0]+16,y=p[1]+12;if(x+272>mv.w)x=p[0]-284;if(y+tip.offsetHeight>mv.h-8)y=mv.h-tip.offsetHeight-8;tip.style.left=x+'px';tip.style.top=y+'px'}
 function heatTh(){const fc=filtered();const sc=Math.max(.05,fc.length/Math.max(1,D.located));D.thSc=sc;const o={};D.tracts.forEach(t=>o[t.id]=0);fc.forEach(c=>o[c.tract]++);const nz=Object.values(o).filter(v=>v>0).sort((a,b)=>a-b);const q=p=>nz.length?nz[Math.floor(p*(nz.length-1))]:1;const a1=Math.max(2,q(.35)+1),a2=Math.max(a1+1,q(.65)+1),a3=Math.max(a2+1,q(.88)+1);D.th=[1,a1,a2,a3];
  const T=D.tracts;const sel=sel311();T.forEach(t=>{t.p311=sel?sel.reduce((a,k)=>a+((D.p311[k]||{})[t.id]||0),0):ITEM.n311?((D.p311[ITEM.id]||{})[t.id]||0):0});
  const vt=T.reduce((a,t)=>a+o[t.id],0)||1,pt=T.reduce((a,t)=>a+t.p311,0)||1;
  T.forEach(t=>{t.vrate=o[t.id]/t.pop*1000;t.prate=t.p311/t.pop*1000*12/D.m311});const vp=pctRanks(T.map(t=>t.vrate)),pp=pctRanks(T.map(t=>t.prate));T.forEach((t,i)=>{t.vpct=vp[i];t.ppct=pp[i];t.pgap=ITEM.n311?pp[i]-vp[i]:0;t.pwv=!!ITEM.n311&&pp[i]>=70&&vp[i]<=30});
  const qq=a=>{a=a.filter(x=>x>0).sort((x,y)=>x-y);return a.length?[.25,.5,.75].map(p=>a[Math.floor(a.length*p)]):[1,2,3]};
  D.qb={voice:qq(T.map(t=>t.vrate)),prob:qq(T.map(t=>t.prate)),gap:qq(T.map(t=>t.pgap))};return o}
 function styleMaps(){const fcnt=heatTh();const inR=S.region&&S.region.poly!=='city'?new Set(regionTracts(S.region.poly).map(t=>t.id)):null;const inAll=S.compare&&S.regions.length>1?new Set(S.regions.flatMap(r=>regionTracts(r.poly).map(t=>t.id))):inR;
  maps.forEach((m,i)=>{if(S.selTract===undefined&&S.mvOpen>=0)S.selTract=missingTop()[S.mvOpen].id;m.select(S.selTract?D.byTract[S.selTract]:null);m.style({cnt:fcnt,scheme:S.sbs?(i?'gap':'voice'):S.scheme,polys:(S.compare?S.regions:S.region?[S.region]:[]).flatMap(r=>ringsOf(r.poly)),dotFilter,empty:S.state==='noitem'||S.state==='loading'});m.regions(S.compare?S.regions:S.region?[S.region]:[])});placeHandle()}
 function placeHandle(){document.querySelectorAll('.rhandle').forEach(e=>e.remove());if(!maps[0]||S.sbs)return;const list=(S.compare?S.regions:S.region?[S.region]:[]).filter(r=>r.poly!=='city'&&(S.compare||!Array.isArray(r.poly)));list.forEach((r,i)=>{const m=maps[0];const pts=ptsOf(r.poly).map(p=>m.screen(p));const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const x=Math.max(...xs),y=Math.min(...ys);const h=document.createElement('div');h.className='rhandle';h.innerHTML=`<span class="nm"><i></i>${esc(r.name)}</span>${S.compare?'':'<span class="sep"></span><button data-act="rename">Rename</button>'+(S.saved.includes(r)?'<button disabled style="opacity:.6;cursor:default">Saved</button>':'<button data-act="save">Save</button>')+'<button data-act="del">Delete</button>'}`;m.el.appendChild(h);h.style.left=Math.max(8,Math.min(m.w-h.offsetWidth-56,x-h.offsetWidth/2))+'px';h.style.top=Math.max(8,y-40)+'px'})}

 function render(){
  if(S.view==='analytics'&&(S.region||S.tractDetail)){heatTh();const keepA=document.querySelector('.rpanel .scroll');const stA=keepA?keepA.scrollTop:0;stage.innerHTML=top()+analyticsView()+footer()+(S.inspector?inspector():'')+(S.srcView?srcModal():'')+(S.lightbox?lightbox():'');const nsA=document.querySelector('.rpanel .scroll');if(nsA&&keepA)nsA.scrollTop=stA;const el=stage.querySelector('#mini');const sel=S.tractDetail?[D.byTract[S.tractDetail]]:regionTracts(S.region.poly);const ids=new Set(sel.map(t=>t.id));const whole=sel.length===D.tracts.length;let focus=null;
   if(!whole){const b=[1e9,1e9,-1e9,-1e9];sel.forEach(t=>{const bb=bbox(t.geometry);b[0]=Math.min(b[0],bb[0]);b[1]=Math.min(b[1],bb[1]);b[2]=Math.max(b[2],bb[2]);b[3]=Math.max(b[3],bb[3])});const px=(b[2]-b[0])*0.35+0.004,py=(b[3]-b[1])*0.35+0.003;focus=[b[0]-px,b[1]-py,b[2]+px,b[3]+py]}
   const m=new MapView(el,{static:true,pad:12,focus});const drawnA=!S.tractDetail&&S.region&&Array.isArray(S.region.poly);const qb=(D.qb||{voice:[1,2,3]}).voice;const hq=t=>{const v=t.vrate||0;return v===0?'url(#hatchRaw)':RAW[v<qb[0]?1:v<qb[1]?2:v<qb[2]?3:4]};
   if(drawnA){const cid='mc'+Math.random().toString(36).slice(2,7);m.svg.select('defs').append('clipPath').attr('id',cid).append('path').attr('d',ringsOf(S.region.poly).map(g=>d3.line().curve(d3.curveLinearClosed)(g.map(p=>m.proj(p)))).join(''));m.gT.attr('clip-path',null);const bg=m.gT.node().cloneNode(true);m.gT.node().parentNode.insertBefore(bg,m.gT.node());d3.select(bg).selectAll('path').attr('fill','#ECEBE7').attr('stroke','#FFFFFF').attr('stroke-width',.6);m.gT.attr('clip-path',`url(#${cid})`);m.regions([S.region])}
   m.tp.attr('fill',t=>drawnA?hq(t):ids.has(t.id)?'#7357B4':'#ECEBE7').attr('stroke','#FFFFFF').attr('stroke-width',.6).attr('opacity',1);m.dp.attr('display','none');maps=[];return}
  heatTh();const keepM=document.querySelector('.rmodal .scroll');const stM=keepM?keepM.scrollTop:0;
  const keep=document.querySelector('.rpanel .scroll');const st=keep?keep.scrollTop:0;const keepL=document.querySelector('.rail .scroll');const stL=keepL?keepL.scrollTop:0;
  stage.innerHTML=top()+((S.state==='fallback'||ITEM.fallback>ITEM.total/2)?`<div class="banner"><span class="dia"></span><span>Running rule-based classification; AI labels unavailable.</span></div>`:'')+`<div class="body">${S.sbs?'':leftRail()}${mapArea()}${rightPanel()}${S.drawer&&!S.sbs?drawer():''}</div>`+footer()+(S.inspector?inspector():'')+(S.srcView?srcModal():'')+(S.lightbox?lightbox():'');
  const prevT=maps[0]?maps[0].k:null;
  maps=[...stage.querySelectorAll('.map')].map((el,i)=>new MapView(el,{padTop:S.sbs?56:52,onHover,regionOpen:r=>S.modal&&!S.tractDetail&&S.region===r&&!S.compare,onRegion:r=>{if(S.compare){const k=S.regions.indexOf(r);if(k>=0){S.region=r;S.regions=[r];S.compare=false}}S.selTract=null;S.tractDetail=null;S.modal=true;S.right=true;render()},onPick:(t,dbl)=>{const drawn=S.region&&Array.isArray(S.region.poly)&&!S.compare;if(drawn&&!dbl&&inPoly(t.c,S.region.poly)){S.selTract=null;S.tractDetail=null;S.modal=true;S.right=true;render();return}S.zoomTract=!!dbl;const off=!dbl&&S.selTract===t.id;S.selTract=off?null:t.id;S.tractDetail=off?null:t.id;if(!off){S.modal=true;S.right=true}render()},onZoom:(t,src)=>{maps.forEach(m=>{if(m!==src)m.setT(t)});tip.style.display='none';placeHandle()}}));
  if(prevT&&prevT.k!==1)maps.forEach(m=>m.setT(prevT));
  else if(S.initZoom&&!S._z){S._z=1;const m=maps[0];const [x,y]=m.proj(S.initZoom.c);const k=S.initZoom.k;const t=d3.zoomIdentity.translate(m.w/2-x*k,m.h/2-y*k).scale(k);maps.forEach(mm=>mm.setT(t))}
  maps.forEach(m=>m.onApply=()=>{placeHandle();placePop()});
  styleMaps();
  if(S.armed)armDraw();
  if(S.hint){const h=document.createElement('div');h.className='hint';h.textContent=S.hint;maps[0].el.appendChild(h)}
  if(S.pin&&!S.pinShown){const t=(S.pin.kind==='under'?D.tracts.filter(x=>x.n>=2&&x.gap<-55).sort((a,b)=>b.pop-a.pop)[0]:S.pin.kind==='zero'?D.tracts.filter(x=>x.n===0).sort((a,b)=>b.exp-a.exp)[0]:D.byTract[S.pin.id])||D.tracts[0];maps.forEach(m=>m.hover(t));const m=maps[S.pin.map||0];showTip(t,m.screen(t.c),m)}
  if(S.modal&&maps[0]&&!S.sbs){const tg=S.tractDetail?(!S.zoomTract?null:{pts:(b=>[[b[0],b[1]],[b[2],b[3]]])(D.byTract[S.tractDetail].cb)}):S.compare&&S.regions.length>1?{pts:S.regions.flatMap(r=>ptsOf(r.poly))}:S.region&&Array.isArray(S.region.poly)?{pts:ptsOf(S.region.poly)}:null;const key=S.tractDetail?S.tractDetail+(S.zoomTract?':z':''):S.compare?S.regions.map(r=>r.name).join('|'):(S.region&&S.region.name+(Array.isArray(S.region.poly)?S.region.poly.length:''));if(tg&&key!==S._fitKey&&!S.regionState){S._fitKey=key;const m=maps[0];const mw=(S.compare&&!S.tractDetail?640:380)+70;setTimeout(()=>m.fitTo(tg,[16+(S.compare&&!S.tractDetail?440:300)+40,60,m.w-60,m.h-30]),0)}}
  if(!S.modal)S._fitKey=null;placePop();
  if(S.toast&&maps[0]){const h=document.createElement('div');h.className='hint maptoast';h.textContent=S.toast;h.style.background='#1B1B1B';maps[0].el.appendChild(h)}
  if(S.preDraw)preDraw();
  if(S.pulseId){const c=D.comments.find(x=>x.id===S.pulseId);maps[0].pulse(c)}
  const ns=document.querySelector('.rpanel .scroll');if(ns&&keep)ns.scrollTop=st;const nl=document.querySelector('.rail .scroll');if(nl&&keepL)nl.scrollTop=stL;const nm=document.querySelector('.rmodal .scroll');if(nm&&keepM)nm.scrollTop=stM;
 }
 function preDraw(){const m=maps[0];const all=EAST_REGION.filter((p,i)=>i%4===0).slice(0,9).map(p=>m.screen(p));const g=m.gDraw.append('g');const cur=[all[all.length-1][0]-30,all[all.length-1][1]-42];
 g.append('path').attr('d','M'+[...all,cur].map(p=>p.join(',')).join('L')+'Z').attr('fill',GAP[4]).attr('fill-opacity',.08);
 g.append('path').attr('d','M'+all.map(p=>p.join(',')).join('L')).attr('fill','none').attr('stroke',GAP[4]).attr('stroke-width',2);
 g.append('path').attr('d',`M${all[all.length-1].join(',')}L${cur.join(',')}L${all[0].join(',')}`).attr('fill','none').attr('stroke',GAP[4]).attr('stroke-width',1.5).attr('stroke-dasharray','5 4');
 all.forEach((p,i)=>g.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',i?3.5:5).attr('fill',i?'#fff':GAP[4]).attr('stroke',GAP[4]).attr('stroke-width',i?1.5:2));
 g.append('path').attr('d',`M${cur[0]-7},${cur[1]}h14M${cur[0]},${cur[1]-7}v14`).attr('stroke','#1B1B1B').attr('stroke-width',1.2)}
 /* a named set of census tracts (district, neighborhood) becomes a region: adjacent census tracts are merged into outlines,
    and the exact census tract list is pinned so lookups never drift */
 function areaRegion(ids,name){let rs=[];ids.forEach(id=>{const g=D.byTract[id].geometry;(g.type==='Polygon'?[g.coordinates]:g.coordinates).forEach(pl=>{rs=mergeRings(rs,pl[0].slice(0,-1))})});
  const poly=rs.length===1?rs[0]:rs;_rtc.set(poly,{T:D.tracts,r:ids.map(i=>D.byTract[i])});return {name,poly,area:true}}
 function regionFromTracts(ids,name){S.tractDetail=null;S.selTract=null;S.region=areaRegion(ids,name);S.regions=[S.region];S.compare=false;S.modal=true;S.right=true}
 /* two named places at once: both outlined, compared side by side in the card */
 function comparePlaces(list){const rs=list.map(p=>areaRegion(p.tracts.filter(i=>D.byTract[i]),p.name)).filter(r=>regionTracts(r.poly).length);if(rs.length<2)return;
  S.tractDetail=null;S.selTract=null;S.regions=rs;S.region=rs[0];S.compare=true;S.modal=true;S.right=true;S.view='main'}
 function popCompare(){const city=D.tracts;const UR=underRule();const col=r=>{const tr=regionTracts(r.poly);const ids=new Set(tr.map(t=>t.id));const f=areaFacts(tr);const n=D.comments.filter(c=>ids.has(c.tract)).length;const p311=tr.reduce((a,t)=>a+t.p311,0)/f.pop*1000*12/D.m311;return {r,tr,f,n,v:n/f.pop*1000,p311,u:tr.filter(UR.is).length}};
  const A=col(S.regions[0]),B=col(S.regions[1]);const cv=D.comments.length/D.totPop*1000;
  const row=(l,a,b,c)=>`<div class="cmr"><span class="cml">${l}${c?`<em>city ${c}</em>`:''}</span><b>${a}</b><b>${b}</b></div>`;
  return `<div class="rmh"><div style="min-width:0"><div class="pt">Comparing two places</div><div class="small muted">${esc(ITEM.title)}</div></div><button class="colbtn" data-act="closemodal" aria-label="Close">×</button></div>
   <div class="cmp"><div class="cmr hd"><span></span><b><i class="cmk a"></i>${esc(A.r.name)}</b><b><i class="cmk b"></i>${esc(B.r.name)}</b></div>
   ${row('Census tracts',A.tr.length,B.tr.length)}${row('Residents',fmt(A.f.pop),fmt(B.f.pop))}
   ${row('Comments per 1,000',A.v.toFixed(2),B.v.toFixed(2),cv.toFixed(2))}
   ${ITEM.n311?row('311 reports per 1,000 a year',Math.round(A.p311),Math.round(B.p311),Math.round(city.reduce((a,t)=>a+t.p311,0)/D.totPop*1000*12/D.m311)):''}
   ${row('Underheard census tracts',A.u,B.u)}${row('Renter households',P0(A.f.ren),P0(B.f.ren),P0(A.f.renC))}
   ${row('Limited-English households',P0(A.f.lep),P0(B.f.lep),P0(A.f.lepC))}${row('Median income',A.f.incWord,B.f.incWord)}</div>`}
 function regionFromRings(rs){if(!rs.length)return {name:'All of San José',poly:'city'};const nb=rs.map(g=>{const t=regionTracts(g)[0];return t?D.byTract[t.id].nbhd:'empty area'});
  return {name:rs.length===1?`Drawn region — ${nb[0]}`:nb.slice(0,3).join(' + ')+(nb.length>3?` + ${nb.length-3} more`:''),poly:rs.length===1?rs[0]:rs,drawn:true}}
 function setDrawn(rs){S.tractDetail=null;S.selTract=null;S.region=regionFromRings(rs);S.regions=[S.region];S.compare=false;S.modal=rs.length>0;S.right=true}
 function flash(msg){S.toast=msg;setTimeout(()=>{S.toast=null;const e=document.querySelector('.maptoast');if(e)e.remove()},4500)}
 function armDraw(){maps[0].armDraw(true,ll=>{S.armed=false;S.hint=null;window.__drawEnd=Date.now();
  const cur=S.region&&Array.isArray(S.region.poly)?ringsOf(S.region.poly):[];
  if(cur.some(r=>ll.every(p=>inRing(p,r)))){flash('That shape is inside an open drawing. Close the drawing around it first.');S.modal=cur.length>0;render();return}
  const rs=mergeRings(cur,ll);setDrawn(rs);flash(rs.length<cur.length+1?'Overlapping drawings merged into one':rs.length>1?`${rs.length} drawings combined in one analysis`:'Region selected · double-click inside to pick a single census tract');
  S.regionState='loading';render();setTimeout(()=>{S.regionState=null;render()},380)},h=>{const e=maps[0].el.querySelector('.hint');if(e)e.textContent=h})}
 /* ---------- source viewer: what a chat citation points at ---------- */
 const SRC={};
 function loadSrc(path){if(SRC[path])return SRC[path].v;SRC[path]={v:null};const url=`${import.meta.env.BASE_URL}${path.replace(/^public\//,'')}`;
  fetch(url).then(r=>path.endsWith('.csv')?r.text():r.json()).then(v=>{if(path.endsWith('.csv')){const [h,...L]=v.trim().split('\n');const c=h.split(',');v=L.map(l=>{const x=l.split(',');return Object.fromEntries(c.map((k,i)=>[k,x[i]]))})}SRC[path].v=v;if(S.srcView)render()}).catch(()=>{SRC[path].v={error:true};if(S.srcView)render()});return null}
 function srcModal(){const ref=S.srcView;const [kind,rest]=[ref.slice(0,ref.indexOf(':')),ref.slice(ref.indexOf(':')+1)];const [path,key]=rest.split('#');let title='',sub='',body='';
  const tbl=(cols,rows)=>`<table class="ht srct"><thead><tr>${cols.map(c=>`<th>${c}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(x=>`<td>${x}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  const wait='<p class="muted">Loading…</p>';const pct=x=>x==null||x===''?'—':Math.round(+x*100)+'%';
  if(kind==='metric'){const m=(D.metrics||{})[rest]||{};title=`${rest} · ${m.name||'Metric'}`;sub='public/data/metrics.json';body=`<dl class="srcdl"><dt>Value</dt><dd>${esc(typeof m.value==='object'?JSON.stringify(m.value):String(m.value??'—'))}</dd><dt>Formula</dt><dd>${esc(m.formula||'—')}</dd><dt>Data</dt><dd>${esc(m.label||'—')}</dd></dl>`}
  else if(path==='docs/CONTEXT_SAN_JOSE.md'){title='Background notes';sub='docs/CONTEXT_SAN_JOSE.md · context, not computed from app data';const secs=CONTEXT_MD.split('\n## ').slice(1).map(x=>{const i=x.indexOf('\n');return {k:x.slice(0,i).trim(),t:x.slice(i+1).replace(/\n/g,' ').trim()}});
   body=secs.filter(x=>!key||x.k===key).map(x=>`<h5 class="mdh">${esc(x.k.replace(/-/g,' '))}</h5><p>${esc(x.t)}</p>`).join('')||secs.map(x=>`<h5 class="mdh">${esc(x.k)}</h5><p>${esc(x.t)}</p>`).join('')}
  else if(path==='public/data/associations.json'){const a=loadSrc(path);title='How census tract traits go with what was measured';sub=path+' · Spearman correlation across census tracts; places, not people; not cause';
   body=!a?wait:a.error?'<p>Could not load.</p>':`<p class="small muted">${esc(a.read_as||'')}</p>`+tbl(['Census tract trait','Measured','rho','Strength'],a.results.map(r=>[esc(r.attribute_label),esc(r.outcome_label.replace(/_/g,' ')),(+r.rho).toFixed(2),r.strength]))}
  else if(path==='public/data/tract_profiles.csv'){const T=loadSrc(path);title='Census tract profiles';sub=path;
   if(!T)body=wait;else if(T.error)body='<p>Could not load.</p>';else{const regs=S.compare&&S.regions.length>1?S.regions:S.region&&Array.isArray(S.region.poly)?[S.region]:[];
    const sum=rows=>{const pop=rows.reduce((a,r)=>a+(+r.pop||0),0)||1;const w=k=>rows.reduce((a,r)=>a+(+r[k]||0)*(+r.pop||0),0)/pop;const c=rows.reduce((a,r)=>a+(+r.comments||0),0);return [rows.length,fmt(pop),c,(c/pop*1000).toFixed(2),Math.round(w('p311_per_1k_yr')),pct(w('renter')),pct(w('lep')),rows.filter(r=>r.underheard==='True').length]};
    if(regs.length){const by=new Map(T.map(r=>[r.tract_id,r]));body=regs.map(g=>{const rows=regionTracts(g.poly).map(t=>by.get(t.id)).filter(Boolean);return `<h5 class="mdh">${esc(g.name)}</h5>`+tbl(['Neighborhood','Residents','Comments','Per 1,000','311 per 1,000/yr','Renters','Limited English','Underheard'],rows.sort((a,b)=>(+a.voice_per_1k)-(+b.voice_per_1k)).map(r=>[esc(r.nbhd),fmt(+r.pop),r.comments,(+r.voice_per_1k).toFixed(2),Math.round(+r.p311_per_1k_yr),pct(r.renter),pct(r.lep),r.underheard==='True'?'yes':'']))}).join('')}
    else{const ds=[...new Set(T.map(r=>r.district).filter(Boolean))].sort((a,b)=>a-b);body='<p class="small muted">All sections, by council district. Open a district or region to see its census tracts.</p>'+tbl(['District','Census tracts','Residents','Comments','Per 1,000','311 per 1,000/yr','Renters','Limited English','Underheard'],ds.map(d=>['D'+parseInt(d,10),...sum(T.filter(r=>r.district===d))]))+tbl(['City','Census tracts','Residents','Comments','Per 1,000','311 per 1,000/yr','Renters','Limited English','Underheard'],[['All',...sum(T)]])}}}
  else{title='Source file';sub=rest;const j=path.startsWith('public/data/')&&path.endsWith('.json')?loadSrc(path):null;const v=j&&!j.error&&key?j[key.split(/[.[/]/)[0]]:null;
   body=path.startsWith('public/data/')?(j?`<pre class="srcpre">${esc(JSON.stringify(v??Object.keys(j),null,1).slice(0,4000))}</pre>`:wait):`<p>This file is part of the project repository (<code>${esc(path)}</code>) and is not served with the app.</p>`}
  return `<div class="scrim" data-act="closesrc"><div class="modal srcm" data-stop="1" role="dialog" aria-label="Source"><div class="mhd"><h3>${esc(title)}</h3><button class="colbtn" data-act="closesrc" aria-label="Close">×</button></div><div class="small muted" style="padding:0 20px 8px">${esc(sub)}</div><div class="scroll srcb md">${body}</div></div></div>`}
 function inspector(){const c=S.inspector;const letter=c.src==='Letter';
 const hl=(txt)=>{let h=esc(txt);const mark=(q,cls)=>{const e=esc(q);if(e&&h.includes(e))h=h.replace(e,`<mark${cls?` class="${cls}"`:''}>${e}</mark>`)};mark(c.evq,'');if(c.sev&&c.sev!==c.evq&&!c.evq.includes(c.sev))mark(c.sev,'sev');return h.replace(/\[(name|email|phone) removed\]/g,'<span class="rmv">[$1 removed at ingest]</span>')};
 const loc=c.tier==='none'?'Not located':`${c.tier[0].toUpperCase()+c.tier.slice(1)}${c.locSrc==='street_anchor'?' (street, approximate)':c.locSrc?' ('+c.locSrc+')':''}`;
 const basis={residence:'where the writer is',issue:'the place the comment is about',both:'the writer’s own area'}[c.basis]||'';
 const photos=c.attach.filter(a=>a.kind==='image');
 return `<div class="scrim" data-act="closeinsp"><div class="modal" data-stop="1" role="dialog" aria-label="Comment inspector"><div class="mhd"><h3><code style="font-family:var(--mono);font-size:14px">${c.id}</code><span class="st ${c.stance}">${stIco(stV(c),11)}${stLabel[stV(c)]}</span>${c.mock?'<span class="flag"><i></i>Simulated</span>':''}</h3><div class="btnrow">${c.tract?`<button class="btn" data-act="zoomto" data-t="${c.tract}">Show on map</button>`:''}<button class="colbtn" data-act="closeinsp" aria-label="Close" style="width:30px;height:30px">×</button></div></div><div class="mbody"><div class="raw"><div class="small muted" style="margin-bottom:8px;font-weight:500;text-transform:uppercase;letter-spacing:.06em">As received · ${letter?'Letter from the public (Legistar)':c.via==='ecomments_portal'?'eComment portal (simulated)':'Email (simulated)'}</div>
 <div class="ehdr">${letter?`<div>From: <span class="rmv">removed at ingest</span></div><div>Matter: <b>${esc(c.agenda)} · ${esc(clip(c.agendaTitle,80))}</b></div><div>Meeting: <b>${esc(c.meeting||'—')}</b></div><div>PDF pages: <b>${c.pages||'—'}${c.exhibit?` (${c.exhibit} exhibit)`:''}</b>${c.ocr?' · read by OCR':''}</div>${c.srcUrl?`<div>Record: <a href="${esc(c.srcUrl)}" target="_blank" rel="noopener">Legistar</a></div>`:''}`:`<div>From: <span class="rmv">removed at ingest</span></div><div>To: <b>${esc(c.office||'City Council')}</b></div><div>Item: <b>${esc(clip(c.agendaTitle,80))}</b></div>`}<div>Subject: <b>${esc(c.subject||'(none)')}</b></div><div>Date: <b>${c.when?c.when.toLocaleString('en-US'):'unknown'}</b></div></div>
 <div class="ebody">${hl(c.text)}</div>
 ${c.attach.length?`<div style="margin-top:18px"><div class="small muted" style="margin-bottom:6px">Attachments (${c.attach.length})</div>${photos.length?`<div class="thumbs">${photos.map(a=>H.thumb(esc(a.file),c.id)).join('')}</div>`:''}${c.attach.filter(a=>a.kind!=='image').map(a=>`<div class="small" style="margin-top:4px">📎 ${esc(a.file)}${a.description?' — '+esc(a.description):''}</div>`).join('')}</div>`:''}</div>
 <div class="rec"><div class="small muted" style="margin-bottom:10px;font-weight:500;text-transform:uppercase;letter-spacing:.06em">Structured record</div><dl>
 <dt>Source</dt><dd>${letter?'Letter · real':c.src+' · simulated'}</dd><dt>Received</dt><dd class="num">${fdate(c)}</dd><dt>Language</dt><dd>${esc(c.lang)}${c.langCode&&c.langCode!=='en'?' · labeled in the original language':''}</dd>
 <dt>Stance</dt><dd><span class="st ${c.stance}">${stIco(stV(c),10)}${stLabel[stV(c)]}</span><span class="prov">${c.engine==='bob'?'AI-labeled (IBM Bob)':c.engine==='build-agent'?'AI-labeled (build agent)':'rule-based'}</span>${c.sev?`<div class="small muted" style="margin-top:3px">Evidence: “${esc(c.sev)}”</div>`:''}</dd>
 <dt>Section</dt><dd class="chips"><span class="cat">${esc((ITEMS[c.catKey]||{}).title||c.catKey)}</span>${c.subKey?`<span class="cat">${esc(D.catDefs.find(x=>x.key===c.catKey)?.subcategories.find(x=>x.key===c.subKey)?.label||c.subKey)}</span>`:''}${c.conf!=null?`<span class="small muted">${Math.round(c.conf*100)}% confidence</span>`:''}</dd>
 <dt>Evidence</dt><dd>${c.evq?`“${esc(c.evq)}” <span class="small muted">· highlighted at left</span>`:'<span class="muted">none</span>'}</dd>
 <dt>Census tract</dt><dd>${c.t?`${esc(c.t.nbhd)} · <code style="font-family:var(--mono);font-size:12px">${c.tract}</code>`:'<span class="muted">not located</span>'}</dd>
 <dt>Location</dt><dd><b style="font-weight:600">${esc(loc)}</b>${basis?`<div class="small muted" style="margin-top:3px">Located by ${basis}. Street addresses are used only to find the census tract and are not stored; the map shows census tracts, never points.</div>`:''}</dd>
 <dt>Sender</dt><dd>${esc(c.commenter||'resident').replace(/_/g,' ')}</dd>
 <dt>Campaign</dt><dd>${c.camp?`<div class="dup">Form-letter campaign ${esc(c.camp)} · ${c.campSize} copies. Counted as separate comments; tagged so a campaign is not read as broad independent input.</div>`:'<span class="muted">None detected</span>'}</dd>
 ${c.inherited?`<dt>Label</dt><dd class="small">Copied from ${esc(c.inherited)} (same campaign text); quote re-checked in this copy</dd>`:''}
 <dt>Name</dt><dd class="rmv">removed at ingest</dd><dt>Email / phone</dt><dd class="rmv">removed at ingest</dd><dt>Street address</dt><dd class="rmv">removed at ingest · census tract kept</dd>
 <dt>Attachments</dt><dd>${c.attach.length?`${c.attach.length} listed · photos withheld until faces and plates are redacted`:'<span class="muted">none</span>'}</dd></dl></div></div></div></div>`}
 function lightbox(){const l=S.lightbox;return `<div class="lightbox" data-act="closelb"><div class="lbox" data-stop="1"><div class="lbimg"><span class="bz" style="position:absolute;left:12px;top:12px;font-size:12px;font-weight:600;background:rgba(27,27,27,.8);color:#fff;border-radius:2px;padding:2px 7px">withheld</span>${esc(l.lab)} · not displayed until redacted</div><div class="lbcap"><span>${l.id?`Attached to <code style="font-family:var(--mono)">${l.id}</code> · `:''}Faces and license plates must be blurred before any photo is shown</span><span class="btnrow"><button class="btn" data-act="closelb">Close</button></span></div></div></div>`}

 stage.addEventListener('click',e=>{
  const a=e.target.closest('[data-act]');if(!a){if(S.menu){S.menu=null;render()}return}
  if(a.dataset.act==='closeinsp'||a.dataset.act==='closelb'){if(e.target.closest('[data-stop]')&&!e.target.closest('.colbtn,.btn'))return}
  const v=a.dataset.v,act=a.dataset.act;
  switch(act){
  case 'scheme':S.scheme=v;S.sbs=false;break;
  case 'sbs':S.sbs=!S.sbs;S.drawer=false;break;
  case 'menu':S.menu=S.menu===a.dataset.m?null:a.dataset.m;break;
  case 'pickitem':S.menu=null;S.state=null;setItem(a.dataset.id);if(S.view==='analytics'){S.view='main';S.modal=false}S.selTract=null;S.tractDetail=null;S.cats={};S.mvOpen=-1;S.chatExtra=[];S.openCite=null;break;
  case 'loadregion':S.menu=null;S.tractDetail=null;S.selTract=null;{const r=S.saved[+a.dataset.i];S.region=r;S.regions=[r];S.compare=false;S.modal=true;S.right=true}break;
  case 'compare':S.menu=null;S.regions=S.saved.slice(0,2);S.region=S.regions[0];S.compare=true;S.modal=true;S.sbs=false;break;
  case 'draw':S.armed=!S.armed;S.sbs=false;S.modal=S.armed?false:!!(S.region&&Array.isArray(S.region.poly));S.hint=S.armed?'Click to place the first point':null;S.preDraw=false;break;
  case 'left':S.left=!S.left;break;case 'right':S.right=!S.right;break;
  case 'tab':if(v==='region'&&!S.region&&S.tab!=='region'){S.modal=true}else S.tab=v;S.right=true;break;
  case 'stance':S.stance[v]=S.stance[v]?0:1;break;
  case 'catexp':S.catExp=S.catExp||{};S.catExp[v]=!S.catExp[v];break;
  case 'cat':if(S.cats[v])delete S.cats[v];else S.cats[v]=1;break;
  case 'togglefilters':S.filtersOpen=!S.filtersOpen;break;
  case 'fairopen':S.fairOpen=!S.fairOpen;break;
  case 'attr':S.attr=v;break;
  case 'drawer':S.drawer=!S.drawer;break;
  case 'mv':{const t=missingTop()[+a.dataset.i];S.selTract=t.id;S.tractDetail=t.id;S.modal=true;S.right=true;S.mvOpen=-1}render();if(S.selTract)maps.forEach(m=>m.zoomTo(D.byTract[S.selTract]));return;
  case 'seltract':S.view='main';S.selTract=a.dataset.t;S.tractDetail=a.dataset.t;S.modal=true;render();if(S.selTract)maps.forEach(m=>m.zoomTo(D.byTract[S.selTract]));return;
    case 'zoomto':{S.inspector=null;S.selTract=a.dataset.t;render();const t=D.byTract[a.dataset.t];maps.forEach(m=>m.zoomTo(t));return}
  case 'zin':maps.forEach(m=>m.zoomBy(1.6));return;case 'zout':maps.forEach(m=>m.zoomBy(1/1.6));return;case 'zreset':S.menu=S.menu==='city'?null:'city';render();maps.forEach(m=>m.reset());return;
  case 'cityregion':S.menu=null;S.tractDetail=null;S.region={name:'All of San José',poly:'city'};S.regions=[S.region];S.compare=false;S.modal=true;S.right=true;S.selTract=null;break;
  case 'rmode':S.rmode=v;{const sc=document.querySelector('.rpanel .scroll');const y=sc?sc.scrollTop:0;const html=regionTab();/* animate bars by updating in place */const tmp=document.createElement('div');tmp.innerHTML=html;const nb=tmp.querySelector('.bars');const ob=document.querySelector('.rmodal .bars');if(ob&&nb){[...ob.children].forEach((row,i)=>{const n=nb.children[i];row.style.top=n.style.top;row.querySelector('.bl').innerHTML=n.querySelector('.bl').innerHTML;const os=row.querySelector('.sbar'),ns=n.querySelector('.sbar');os.style.width=ns.style.width;[...os.children].forEach((s,j)=>{s.style.flexBasis=ns.children[j].style.flexBasis;s.innerHTML=ns.children[j].innerHTML})});document.querySelectorAll('.rmodal .seg button[data-act=rmode]').forEach(b=>b.classList.toggle('on',b.dataset.v===v));return}}break;
  case 'inspect':S.inspector=D.comments.find(c=>c.id===a.dataset.id);break;
  case 'closeinsp':S.inspector=null;break;
  case 'srcview':S.srcView=a.dataset.ref;break;
  case 'closesrc':S.srcView=null;break;
  case 'cite':S.openCite=S.openCite===a.dataset.id?null:a.dataset.id;if(S.tab!=='chat'){S.inspector=D.comments.find(c=>c.id===a.dataset.id)}break;
  case 'lightbox':S.lightbox={lab:a.dataset.lab,id:a.dataset.id};break;
  case 'closelb':S.lightbox=null;break;
  case 'ask':S.tab='chat';S.chatRegion=true;break;
  case 'rmchip':S.chatRegion=false;break;
  case 'copy':{e.preventDefault();const p=a.closest('.brief,.sec').querySelector('p');if(p&&navigator.clipboard)navigator.clipboard.writeText(p.innerText).catch(()=>{});a.textContent='Copied';setTimeout(()=>{a.textContent='Copy brief'},1500)}return;
  case 'save':if(S.region&&!S.saved.includes(S.region))S.saved.push(S.region);break;
  case 'rename':{const i=document.querySelector('.rname');if(i){i.focus();i.select()}return}
  case 'closedraw':{const rs=ringsOf(S.region&&S.region.poly).filter((_,i)=>i!==+a.dataset.i);setDrawn(rs);if(!rs.length){S.modal=false}}break;
  case 'closealldraw':setDrawn([]);S.modal=false;break;
  case 'del':S.modal=false;S.tractDetail=null;S.region={name:'All of San José',poly:'city'};S.regions=[S.region];S.compare=false;S.tab='missing';break;
  case 'docksend':{const q=(document.querySelector('.dockin')||{}).value||'';S.tab='chat';sendChat(q)}return;
  case 'untract':S.tractDetail=null;S.selTract=null;S.modal=!!S.region;break;
  case 'anmode':S.anMode=v;break;
  case 'mvsort':S.mvSort=v;break;
  case 'closemodal':S.modal=false;break;
  case 'analytics':S.view='analytics';S.modal=false;break;
  case 'cityan':S.tractDetail=null;S.selTract=null;S.region={name:'All of San José',poly:'city'};S.regions=[S.region];S.compare=false;S.view='analytics';S.modal=false;S.menu=null;break;
  case 'back':S.view='main';S.modal=true;break;
  case 'send':{const ta=document.querySelector('.cbox textarea');const q=ta?ta.value:'';sendChat(q)}return;
  case 'suggest':sendChat(a.dataset.q);return;
  case 'clearchat':S.chat=[];break;
  }
  render();
 });
 stage.addEventListener('keydown',e=>{if(e.target.matches&&e.target.matches('.cbox textarea')&&e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChat(e.target.value)}});
 stage.addEventListener('toggle',e=>{if(e.target.classList&&e.target.classList.contains('mapkey'))S_KEY.open=e.target.open},true);
 stage.addEventListener('change',e=>{const a=e.target.dataset.actChange;if(a==='attr'){S.attr=e.target.value;render()}});
 stage.addEventListener('input',e=>{if(e.target.classList.contains('rname')&&S.region){S.region.name=e.target.value;const n=document.querySelector('.rhandle .nm');if(n)n.lastChild.textContent=e.target.value}});
 stage.addEventListener('mouseover',e=>{const tp=e.target.closest&&e.target.closest('[data-tip]');if(tp){srcTip.innerHTML=tp.getAttribute('data-tip');srcTip.style.display='block';delete srcTip.dataset.fixed;return}});
 stage.addEventListener('mouseout',e=>{const tp=e.target.closest&&e.target.closest('[data-tip]');if(tp&&!tp.contains(e.relatedTarget))srcTip.style.display='none'});
 stage.addEventListener('mouseover',e=>{const df=e.target.closest('[data-def]');if(df){const r=df.getBoundingClientRect();srcTip.innerHTML=esc(df.dataset.def);srcTip.style.display='block';srcTip.style.left=r.left+'px';srcTip.style.top=(r.bottom+8)+'px';srcTip.dataset.fixed='1';return}const q=e.target.closest('[data-hover]');if(q&&maps[0]){maps[0].pulse(D.comments.find(c=>c.id===q.dataset.hover))}const s=e.target.closest('[data-src]');if(s){srcTip.innerHTML='Source: <code>'+esc(s.dataset.src)+'</code>';srcTip.style.display='block'}});
 stage.addEventListener('mousemove',e=>{if(srcTip.style.display==='block'&&!srcTip.dataset.fixed){srcTip.style.left=Math.min(innerWidth-290,e.clientX+12)+'px';srcTip.style.top=(e.clientY+16)+'px'}});
 stage.addEventListener('mouseout',e=>{const df=e.target.closest('[data-def]');if(df&&!df.contains(e.relatedTarget)){srcTip.style.display='none';delete srcTip.dataset.fixed;return}const q=e.target.closest('[data-hover]');if(q&&!q.contains(e.relatedTarget)&&maps[0]&&!S.pulseId)maps[0].pulse(null);const s=e.target.closest('[data-src]');if(s&&!s.contains(e.relatedTarget))srcTip.style.display='none'});
 addEventListener('keydown',e=>{if(e.key==='Escape'){if(S.armed)S.modal=!!(S.region&&Array.isArray(S.region.poly));S.armed=false;S.hint=null;S.inspector=null;S.srcView=null;S.lightbox=null;S.menu=null;render()}});
 render();
 if(S.srcDemo){const el=document.querySelector(S.srcDemo);if(el){const r=el.getBoundingClientRect();srcTip.innerHTML='Source: <code>'+esc(el.dataset.src)+'</code>';srcTip.style.display='block';srcTip.style.left=r.left+'px';srcTip.style.top=(r.bottom+6)+'px'}}
 return {S,render,maps:()=>maps};
}


export {mount,load};
