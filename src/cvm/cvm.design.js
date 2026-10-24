(function(){
const COL={support:'#1F7A6E',oppose:'#B3412B',neutral:'#6B7280',amber:'#B7791F'};
const GAP=['#EDE9F7','#C9BEE8','#9F8AD3','#7357B4','#4A2C8C'];
const GAPM=['#D9D6CE','#CDC2EC','#9F8AD3','#7357B4','#4A2C8C'];
const RAW=['#E4E0D8','#F6CFC2','#E8957D','#C8553D','#8E2A1C'];
const PROB=['#E3F1EF','#A9D8D1','#5FB3A8','#22877C','#0B5249'];
const RAWZ=`repeating-linear-gradient(45deg,#E4E0D8 0 3px,#C9C4BA 3px 4.5px)`;
const CATS=[];const CATN={};const ITEM={};
const ATTRS={renter:{l:'Renter-majority',s:'Renter-majority',f:t=>t.renter>0.5,acs:'ACS B25003'},income:{l:'Below-median income',s:'Below-median-income',f:null,acs:'ACS B19013'},nonwhite:{l:'Majority non-white',s:'Majority non-white',f:t=>t.nonwhite>0.5,acs:'ACS B03002'},lep:{l:'High limited-English',s:'High limited-English',f:t=>t.lep>0.2,acs:'ACS C16002'}};
const sub=(k,n,count,tpl)=>({k,n,count,tpl});
const ITEMS={
'gov':{id:'gov',title:'Governance & Civic Rights',n311:null,src:{Letter:246},seed:11,
 focus:t=>0.3+t.e*2+t.lep*2+t.a*.6,
 subs:[sub('imm','Immigrant Protection & Sanctuary Policy',182,[{s:'support',t:'Keep San José a sanctuary city. My neighbors should not be afraid to call the police.'},{s:'oppose',t:'The city should cooperate with federal immigration requests.'},{s:'support',t:'Por favor protejan a nuestras familias inmigrantes.',tr:'Please protect our immigrant families.',lang:'Spanish'}]),
  sub('appt','Council Appointments & Special Elections',51,[{s:'neutral',t:'Hold a special election for the open seat instead of appointing someone.'},{s:'oppose',t:'An appointment takes the choice away from voters.'}]),
  sub('prop','Voter Threshold & Prop 13',10,[{s:'neutral',t:'Explain how a lower voter threshold interacts with Prop 13 before it goes on the ballot.'}]),
  sub('boards','Boards, Commissions & Appointments Fairness',3,[{s:'support',t:'Commission seats should reflect every district, not just downtown.'}])]},
'streets':{id:'streets',title:'Streets & Infrastructure',n311:65815,src:{Email:61,Letter:1},seed:12,
 focus:t=>0.5+t.a*1.2+(1-t.renter),
 subs:[sub('light','Streetlight Outages & Reliability',38,[{s:'support',t:'Half the streetlights on our block near the McKee bus stop have been out since spring.'},{s:'support',t:'Đèn đường gần trạm xe buýt bị hư nhiều tháng rồi.',tr:'The streetlights near the bus stop have been broken for months.',lang:'Vietnamese'}]),
  sub('pot','Pothole & Pavement Repair',21,[{s:'support',t:'Repave Hicks Rd. I have replaced two tires this year.'}]),
  sub('drain','Storm Drain & Flooding',2,[{s:'support',t:'The storm drain on Lucretia backs up every time it rains.'}]),
  sub('equity','Infrastructure Equity & Accountability',1,[{s:'neutral',t:'Publish repair response times by district so we can see who waits longest.'}])]},
'housing':{id:'housing',title:'Housing & Affordability Policy',n311:null,src:{Email:51,Letter:2},seed:13,
 focus:t=>0.2+t.renter*2.5,
 subs:[sub('rent','Rent Stabilization & Caps',37,[{s:'support',t:'Cap rent increases. Ours went up 9% this year.'},{s:'oppose',t:'Rent caps will stop small landlords from maintaining their units.'}]),
  sub('zoning','Zoning & Density Reform',10,[{s:'support',t:'Allow fourplexes near transit.'},{s:'oppose',t:'Density changes should not happen without parking.'}]),
  sub('tenant','Tenant Protections & Eviction',3,[{s:'support',t:'Enforce just-cause eviction protections.'}]),
  sub('afford','Affordable Housing Financing',2,[{s:'neutral',t:'How will the affordable housing bond be repaid?'}]),
  sub('supply','Housing Supply & Infrastructure Readiness',1,[{s:'neutral',t:'New housing needs sewer and school capacity first.'}])]},
'code':{id:'code',title:'Code Enforcement & Permitting',n311:541,src:{Email:19,Letter:2},seed:14,
 focus:t=>0.1+t.renter*1.5+t.e,
 subs:[sub('hab','Habitability Failures',11,[{s:'support',t:'Our apartment has had mold and no heat since November. The landlord ignores us.'}]),
  sub('backlog','Permit Backlog & Delays',5,[{s:'oppose',t:'My ADU permit has been waiting eight months.'}]),
  sub('fees','Permit Fees & Staffing',3,[{s:'oppose',t:'Permit fees keep rising while the wait gets longer.'}]),
  sub('derelict','Derelict Buildings & Blight',2,[{s:'support',t:'The burned house on our street has been boarded up for three years.'}])]},
'other':{id:'other',title:'Other / General',n311:13870,src:{Letter:15,Email:4},seed:15,
 focus:t=>0.6,
 subs:[sub('cover','Cover Note / Forwarded Attachment',15,[{s:'neutral',t:'Please see the attached letter for the record.'}]),
  sub('hardship','Personal Financial Hardship',2,[{s:'neutral',t:'I am two months behind on rent and utilities.'}]),
  sub('col','General Cost-of-Living Frustration',1,[{s:'neutral',t:'Everything costs more and nothing seems to change.'}]),
  sub('senior','Senior Services (General)',1,[{s:'support',t:'Keep the senior center open on weekends.'}])]},
'env':{id:'env',title:'Environment & Development Review',n311:null,src:{Email:13},seed:16,
 focus:t=>(t.c[1]<37.28?2.5:0.2)*(t.fringe?1.6:1),
 subs:[sub('eir','EIR & Environmental Review',5,[{s:'oppose',t:'The EIR does not study traffic on Monterey Rd.'}]),
  sub('flood','Flood & Water Risk',4,[{s:'support',t:'Fisher Creek flooded our street in 2023. Leave the land that absorbs the water.'}]),
  sub('cond','Conditional Approval & Community Benefits',3,[{s:'support',t:'Approve it only with a park and local hiring commitments.'}]),
  sub('char','Traffic & Neighborhood Character',1,[{s:'oppose',t:'This project will change the character of our street.'}])]},
'safety':{id:'safety',title:'Public Safety & Emergency Response',n311:11032,src:{Email:7,Letter:5},seed:17,
 focus:t=>0.2+3*Math.exp(-Math.hypot((t.c[0]+121.889)*0.79,t.c[1]-37.333)/0.03)+t.e,
 subs:[sub('alt','Alternative & Co-Response Programs',6,[{s:'support',t:'Send mental health responders, not only police, to crisis calls.'}]),
  sub('patrol','Patrol & Sworn Officer Staffing',4,[{s:'support',t:'We need more officers on patrol in our neighborhood.'}]),
  sub('cams','Cameras, Surveillance & Privacy',1,[{s:'oppose',t:'License plate cameras collect too much data on residents.'}]),
  sub('youth','Crime Prevention & Youth Programs',1,[{s:'support',t:'Fund after-school programs to keep kids safe.'}])]},
'sanit':{id:'sanit',title:'Sanitation & Environmental Quality',n311:126157,src:{Email:9},seed:18,
 focus:t=>0.2+t.e*1.5,
 subs:[sub('dump','Illegal Dumping & Creek Pollution',6,[{s:'support',t:'People dump mattresses along Coyote Creek every week.'}]),
  sub('free','Dumping Prevention & Free Disposal Access',2,[{s:'support',t:'Bring back free bulky item pickup so people stop dumping.'}]),
  sub('air','Freeway Air Quality & Noise',1,[{s:'support',t:'The noise and exhaust from 101 reach our kids’ school.'}])]}};
Object.values(ITEMS).forEach(d=>{d.total=d.subs.reduce((s,x)=>s+x.count,0);d.cats=d.subs.map(x=>({k:d.id+'_'+x.k,n:x.n}))});
const EAST_REGION=(()=>{const pts=[];const cx=-121.832,cy=37.334;for(let i=0;i<44;i++){const a=i/44*Math.PI*2;const r=1+0.07*Math.sin(a*3+1)+0.04*Math.sin(a*7)+0.03*Math.cos(a*11);pts.push([+(cx+Math.cos(a)*0.034*r).toFixed(4),+(cy+Math.sin(a)*0.021*r*(a>Math.PI?1.08:0.95)).toFixed(4)])}return pts})();
const WG_REGION=(()=>{const pts=[];const cx=-121.902,cy=37.298;for(let i=0;i<36;i++){const a=i/36*Math.PI*2;const r=1+0.06*Math.sin(a*4)+0.04*Math.cos(a*9);pts.push([+(cx+Math.cos(a)*0.028*r).toFixed(4),+(cy+Math.sin(a)*0.019*r).toFixed(4)])}return pts})();
function rng(s){return function(){s|=0;s=s+0x6D2B79F5|0;let t=Math.imul(s^s>>>15,1|s);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function inRing(p,r){let x=p[0],y=p[1],ins=false;for(let i=0,j=r.length-1;i<r.length;j=i++){const xi=r[i][0],yi=r[i][1],xj=r[j][0],yj=r[j][1];if(((yi>y)!=(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi))ins=!ins}return ins}
function inGeom(p,g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;return P.some(pl=>inRing(p,pl[0])&&!pl.slice(1).some(h=>inRing(p,h)))}
function bbox(g){const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;let a=[1e9,1e9,-1e9,-1e9];P.forEach(pl=>pl[0].forEach(c=>{a[0]=Math.min(a[0],c[0]);a[1]=Math.min(a[1],c[1]);a[2]=Math.max(a[2],c[0]);a[3]=Math.max(a[3],c[1])}));return a}
const fmt=n=>n.toLocaleString('en-US');
const pct=x=>Math.round(x*100)+'%';
const sgn=n=>(n>0?'+':n<0?'−':'')+Math.abs(n);
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');
const ICON={
 support:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><circle cx="5" cy="5" r="4.2" fill="${COL.support}"/></svg>`,
 oppose:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><polygon points="5,0.8 9.6,9.2 0.4,9.2" fill="${COL.oppose}"/></svg>`,
 neutral:(s=10)=>`<svg width="${s}" height="${s}" viewBox="0 0 10 10" aria-hidden="true"><rect x="1.2" y="1.2" width="7.6" height="7.6" fill="${COL.neutral}"/></svg>`,
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
const stLabel={support:'Support',oppose:'Oppose',neutral:'Neutral'};
const stIco=(s,z)=>ICON[s](z);

/* ---------- data ---------- */
const D={};
async function load(){
 if(D.ready)return D;
 const j=await fetch('data/sj.json').then(r=>r.json());
 D.city={type:'Feature',geometry:j.city,properties:{}};
 D.tracts=j.tracts;
 const T=D.tracts;
 const rew=g=>{const P=g.type==='Polygon'?[g.coordinates]:g.coordinates;P.forEach(pl=>pl.forEach((r,i)=>{if(d3.geoArea({type:'Polygon',coordinates:[r]})>2*Math.PI)r.reverse()}))};
 rew(D.city.geometry);T.forEach(t=>rew(t.geometry));
 const medInc=[...T].map(t=>t.income).sort((a,b)=>a-b)[Math.floor(T.length/2)];
 ATTRS.income.f=t=>t.income<medInc;D.medInc=medInc;
 D.totPop=T.reduce((s,t)=>s+t.pop,0);
 T.forEach(t=>{const P=t.geometry.type==='Polygon'?[t.geometry.coordinates]:t.geometry.coordinates;let a=[1e9,1e9,-1e9,-1e9],n=0;P.forEach(pl=>pl[0].forEach(v=>{if(inGeom(v,D.city.geometry)){n++;a[0]=Math.min(a[0],v[0]);a[1]=Math.min(a[1],v[1]);a[2]=Math.max(a[2],v[0]);a[3]=Math.max(a[3],v[1])}}));if(n<3){const d=0.004;a=[t.c[0]-d,t.c[1]-d,t.c[0]+d,t.c[1]+d]}t.cb=a});
 T.forEach(t=>t.n0=t.n);D.byTract=Object.fromEntries(T.map(t=>[t.id,t]));
 D.ready=true;setItem('gov');return D;
}
function itemTotal(id){return ITEMS[id].total}
function srcLine(d){const e=Object.entries(d.src);return e.length===1?`all ${e[0][0].toLowerCase()}s`:e.map(([k,v])=>`${v} ${k.toLowerCase()}${v===1?'':'s'}`).join(', ')}
function n311(d){return d.n311?fmt(d.n311)+' reported problems':'No reported-problem data'}
function buildItem(def){const R=rng(def.seed*97);const T=D.tracts;const w=T.map(t=>(0.35+Math.max(0,def.focus(t)))*(0.3+R())*(t.pop/5000));const sm=w.reduce((a,b)=>a+b,0);const cum=[];let acc=0;w.forEach(x=>{acc+=x/sm;cum.push(acc)});
 const pick=()=>{const r=R();let i=cum.findIndex(c=>c>=r);return T[i<0?T.length-1:i]};
 const pool=[];Object.entries(def.src).forEach(([k,v])=>{for(let i=0;i<v;i++)pool.push(k)});for(let i=pool.length-1;i>0;i--){const j=Math.floor(R()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]]}
 const C=[];let si=0;
 const ord=T.map((t,i)=>({t,k:Math.pow(R(),1/Math.max(1e-6,w[i]))})).sort((a,b)=>b.k-a.k).map(x=>x.t);let oi=0;const pick2=()=>{const r=R();return r<0.75?ord[(oi++)%ord.length]:pick()};
 def.subs.forEach(sb=>{for(let i=0;i<sb.count;i++){const t=pick2();const tp=sb.tpl[Math.floor(R()*sb.tpl.length)];const bb=bbox(t.geometry);let p,k=0;do{p=[bb[0]+R()*(bb[2]-bb[0]),bb[1]+R()*(bb[3]-bb[1])];k++}while(!(inGeom(p,t.geometry)&&inGeom(p,D.city.geometry))&&k<400);
  const r=R();C.push({id:'ec_'+Math.floor(R()*0xffffffff).toString(16).padStart(8,'0'),item:def.id,tract:t.id,t,cat:def.id+'_'+sb.k,stance:tp.s,text:tp.t,tr:tp.tr,lang:tp.lang||'English',ll:p,tier:r<0.3?'address':r<0.83?'neighborhood':'zip',src:pool[si++]||'Email',when:new Date(2026,9,1+Math.floor(R()*21),7+Math.floor(R()*14),Math.floor(R()*60)),photo:['streets','sanit','code'].includes(def.id)&&R()<0.15})}});
 return C}
function setItem(id){const T=D.tracts;const def=ITEMS[id];
 CATS.length=0;Object.keys(CATN).forEach(k=>delete CATN[k]);def.cats.forEach(c=>{CATS.push(c);CATN[c.k]=c.n});
 const C=buildItem(def);const cnt={};T.forEach(t=>cnt[t.id]=0);C.forEach(c=>cnt[c.tract]++);
 T.forEach(t=>t.n=cnt[t.id]);const located=C.length;
 T.forEach(t=>{t.exp=+(t.pop/D.totPop*located).toFixed(1);t.gap=Math.round((t.n-t.exp)/Math.max(.01,t.exp)*100);const ad=Math.round(t.n*0.3),zp=Math.round(t.n*0.17);t.prec=[ad,t.n-ad-zp,zp]});
 const rates=T.map(t=>t.n/t.pop).sort((a,b)=>a-b);D.hvTh=Math.max(1e-6,rates[Math.floor(rates.length*0.4)]);
 {const R=rng(def.seed*131);const pw=T.map(t=>(0.4+t.e*1.6+t.renter*0.8)*(0.5+R())*t.pop);const ps=pw.reduce((a,b)=>a+b,0);T.forEach((t,i)=>{t.p311=def.n311?Math.round(pw[i]/ps*def.n311):0})}
 C.sort((a,b)=>b.when-a.when);D.comments=C;D.located=C.length;for(const k in ITEM)delete ITEM[k];Object.assign(ITEM,def);ITEM.total=def.total;ITEM.pct=100}
function fairness(tracts,ak){const f=ATTRS[ak].f;const u=tracts.filter(f),p=tracts.filter(t=>!f(t));const hv=t=>t.n>0&&t.n/t.pop>=D.hvTh;const hu=u.filter(hv).length,hp=p.filter(hv).length;
 const r={nu:u.length,np:p.length,hu,hp,pu:u.length?hu/u.length:0,pp:p.length?hp/p.length:0};r.few=u.length<3||p.length<3;r.spd=r.pu-r.pp;r.di=r.pp?r.pu/r.pp:0;return r}
function weights(comments,mode,ak){
 if(mode==='raw')return comments.map(()=>1);
 if(mode==='pop')return comments.map(c=>c.t.pop/Math.max(1,c.t.n)/400);
 const f=ATTRS[ak||'renter'].f;const T=D.tracts;const popU=T.filter(f).reduce((s,t)=>s+t.pop,0)/D.totPop;const cu=D.comments.filter(c=>f(c.t)).length/D.comments.length;
 const wu=popU/Math.max(.01,cu),wp=(1-popU)/Math.max(.01,1-cu);return comments.map(c=>f(c.t)?wu:wp)}
function catTotals(comments,mode,ak){const w=weights(comments,mode,ak);const o={};CATS.forEach(c=>o[c.k]={k:c.k,n:c.n,tot:0,support:0,oppose:0,neutral:0,count:0});comments.forEach((c,i)=>{const x=o[c.cat];x.tot+=w[i];x[c.stance]+=w[i];x.count++});return Object.values(o)}
function ranks(comments,ak){const m={};['raw','rw','pop'].forEach(mode=>{const t=catTotals(comments,mode,ak).sort((a,b)=>b.tot-a.tot);t.forEach((x,i)=>{(m[x.k]=m[x.k]||{k:x.k,n:x.n})[mode]=i+1})});return Object.values(m).sort((a,b)=>a.raw-b.raw)}
function gapBin(t){const g=t.gap;return g>=0?0:g>-30?1:g>-55?2:g>-80?3:4}
function rawBin(t){const n=t.n;return n===0?0:n<5?1:n<10?2:n<18?3:4}
function popBin(t){const r=t.n/t.pop*1000;return r===0?0:r<0.6?1:r<1.2?2:r<2.2?3:4}
const _rtc=new WeakMap();
function regionTracts(poly){if(poly==='city')return D.tracts;if(poly&&poly.tract)return [D.byTract[poly.tract]];if(_rtc.has(poly)&&_rtc.get(poly).T===D.tracts)return _rtc.get(poly).r;
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
 const sym={support:'M0,-2.1a2.1,2.1 0 1,0 0.01,0z',oppose:'M0,-2.6L2.4,1.8L-2.4,1.8z',neutral:'M-1.8,-1.8h3.6v3.6h-3.6z'};
 this.dp=this.gD.selectAll('path').data([]).join('path').attr('d',c=>sym[c.stance]).attr('fill',c=>COL[c.stance]).attr('pointer-events','none');
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
 let lb=this.el.querySelector('.sellabel');if(!t){if(lb)lb.remove();return}if(!lb){lb=document.createElement('div');lb.className='sellabel';this.el.appendChild(lb)}lb.innerHTML=`<b>${t.nbhd}</b><span>Tract ${t.id}</span>`;this.placeSel()};
MapView.prototype.placeSel=function(){const lb=this.el.querySelector('.sellabel');if(!lb||!this.selT)return;const cb=this.selT.cb||[this.selT.c[0],this.selT.c[1],this.selT.c[0],this.selT.c[1]];const p=this.k.apply(this.proj([(cb[0]+cb[2])/2,cb[3]]));lb.style.left=p[0]+'px';lb.style.top=(p[1]-8)+'px'};
MapView.prototype.regions=function(list){list=list.filter(r=>r.poly!=='city');const self=this;this.gR.raise();const at=ev=>{const ll=self.toLL(d3.pointer(ev,self.svg.node()));return D.tracts.find(t=>inGeom(ll,t.geometry))};
 const line=d3.line().curve(d3.curveLinearClosed);
 this.gR.selectAll('path').data(list).join('path').attr('d',r=>line(r.poly.map(p=>this.proj(p)))).attr('fill',GAP[4]).attr('fill-opacity',.1).attr('stroke',GAP[4]).attr('stroke-width',2).attr('vector-effect','non-scaling-stroke').attr('pointer-events','none');
 this.gR.selectAll('path').attr('pointer-events',this.o.static?'none':'all').style('cursor','pointer')
  .on('mousemove',function(ev,r){if(self.armed||self.drawing)return;const open=self.o.regionOpen&&self.o.regionOpen(r);d3.select(this).attr('fill-opacity',open?.1:.2);if(!open){if(self.o.onHover)self.o.onHover(null,null,self);return}const t=at(ev);if(self.o.onHover)self.o.onHover(t||null,t?d3.pointer(ev,self.svg.node()):null,self)})
  .on('mouseleave',function(){d3.select(this).attr('fill-opacity',.1);if(self.o.onHover)self.o.onHover(null,null,self)})
  .on('click',(ev,r)=>{if(self.armed||self.drawing||!self.o.onRegion||Date.now()-(window.__drawEnd||0)<600)return;clearTimeout(self._ct);self._ct=setTimeout(()=>self.o.onRegion(r),230)})
  .on('dblclick',(ev,r)=>{ev.stopPropagation();if(self.armed||self.drawing||!self.o.onPick||Date.now()-(window.__drawEnd||0)<600)return;if(!(self.o.regionOpen&&self.o.regionOpen(r))){clearTimeout(self._ct);self.o.onRegion(r);return}clearTimeout(self._ct);const t=at(ev);if(t)self.o.onPick(t,true)});
};
MapView.prototype.pulse=function(c){this.gP.selectAll('*').remove();if(!c)return;const i=D.comments.indexOf(c);const p=this.k.apply(this.base[i]);
 this.gP.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',7).attr('fill','none').attr('stroke',COL[c.stance]).attr('stroke-width',2).attr('class','pulse');
 this.gP.append('circle').attr('cx',p[0]).attr('cy',p[1]).attr('r',3.6).attr('fill',COL[c.stance]).attr('stroke','#fff').attr('stroke-width',1.2)};
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
 const L=(t,sub,r,l)=>`<div class="legend"><div class="lt">${t}</div><div class="small muted" style="margin:-4px 0 6px">${sub}</div>${r}<div class="rampl">${l.map(x=>`<span>${x}</span>`).join('')}</div></div>`;
 if(sch==='prob'){if(!ITEM.n311)return '';return L('Problems','Reported problems per 1,000 residents',ramp(PROB,PROB[0]),lab(qb.prob))}
 if(sch==='gap'){if(!ITEM.n311)return L('Underheard · participation gap','Comments vs. population share',ramp(GAPM,GAPM[0]),['0%','−30%','−55%','−80%','−100%']);
  return L('Underheard · problems without voice','Share of reported problems − share of comments',ramp(GAPM,GAPM[0]),['≤0',`<${qb.gap[0].toFixed(2)}`,`${qb.gap[0].toFixed(2)}+`,`${qb.gap[1].toFixed(2)}+`,`${qb.gap[2].toFixed(2)}+`])}
 return L('Voice','Comments per 1,000 residents',ramp(RAW,RAWZ),lab(qb.voice))};
H.tip=(t)=>{const ex=t.exp.toFixed(1);if(t.n===0)return `<div class="h">${t.nbhd}</div><div class="s">Tract ${t.id}</div><div class="zero">No comments located here</div><dl><dt>Expected from population share</dt><dd>${ex}</dd><dt>Population</dt><dd>${fmt(t.pop)}</dd><dt>Comments per 1k</dt><dd>${(t.vrate||0).toFixed(2)}</dd>${ITEM.n311?`<dt>Reported problems per 1k</dt><dd>${(t.prate||0).toFixed(1)}</dd><dt>Problems without voice</dt><dd class="gp">${(t.pgap>0?'+':'')+(t.pgap||0).toFixed(2)} pts</dd>`:''}<dt>Renter households</dt><dd>${pct(t.renter)}</dd><dt>Limited-English households</dt><dd>${pct(t.lep)}</dd></dl>`;
 const tot=t.prec[0]+t.prec[1]+t.prec[2];
 return `<div class="h">${t.nbhd}</div><div class="s">Tract ${t.id}</div><dl><dt>Population</dt><dd>${fmt(t.pop)}</dd><dt>Comments per 1k</dt><dd>${(t.vrate||0).toFixed(2)}</dd>${ITEM.n311?`<dt>Reported problems per 1k</dt><dd>${(t.prate||0).toFixed(1)}</dd><dt>Problems without voice</dt><dd class="gp">${(t.pgap>0?'+':'')+(t.pgap||0).toFixed(2)} pts</dd>`:''}<dt>Comments located</dt><dd>${t.n}</dd><dt>Expected from population share</dt><dd>${ex}</dd><dt>Participation gap</dt><dd class="gp">${sgn(t.gap)}%</dd><dt>Renter households</dt><dd>${pct(t.renter)}</dd><dt>Limited-English households</dt><dd>${pct(t.lep)}</dd></dl><div class="pstrip"><div class="pbar"><i style="flex:${t.prec[1]};background:#5C5C58"></i><i style="flex:${t.prec[0]};background:#1B1B1B"></i><i style="flex:${t.prec[2]};background:#B6B0A5"></i></div><div class="small muted">located by: ${t.prec[1]} neighborhood · ${t.prec[0]} address · ${t.prec[2]} zip</div></div>`};
H.cite=(c,extra='')=>`<button class="cite" data-act="cite" data-id="${c.id}" data-src="Comment ${c.id} · ${c.src} · ${c.when.toLocaleDateString('en-US',{month:'short',day:'numeric'})}">${stIco(c.stance,9)}<code>${c.id.slice(0,7)}…</code><span class="tn">${c.t.nbhd}</span>${extra}</button>`;
H.src=(txt,src)=>`<span class="src" data-src="${esc(src)}">${txt}</span>`;
const incLabel=t=>{const r=t.income/D.medInc;return r<0.9?'Below San José median income':r>1.1?'Above San José median income':'Average San José median income'};
H.acs=(t)=>`<span class="acs">${pct(t.renter)} renters</span><span class="acs">${pct(t.lep)} limited-English</span><span class="acs">${incLabel(t)}</span>`;
H.howi=(src)=>`<span class="howi src" style="text-decoration:none" data-src="${esc(src)}">?</span>`;
H.thumb=(lab,id)=>`<div class="thumb" data-act="lightbox" data-lab="${esc(lab)}" data-id="${id||''}"><span class="bz">blurred</span><span class="lb">${lab}</span></div>`;
H.gauge=(di)=>{const sc=v=>Math.min(100,v/1.2*100);return `<div class="gauge"><div class="tr"></div><div class="fl" style="width:${sc(di)}%"></div><div class="th" style="left:${sc(.8)}%"></div><div class="tl" style="left:${sc(.8)}%;transform:translateX(calc(-100% - 5px))">0.8 threshold</div></div>`};
function briefFor(t,cs){const tc=cs.filter(c=>c.tract===t.id);const cats={};tc.forEach(c=>cats[c.cat]=(cats[c.cat]||0)+1);const top=Object.entries(cats).sort((a,b)=>b[1]-a[1])[0];
 let s=`${H.src(`${pct(t.renter)} of households in ${t.nbhd} (tract ${t.id}) rent`,'ACS 5-year B25003 · tenure')} and ${H.src(`${pct(t.lep)} are limited-English households`,'ACS 5-year C16002 · household language')}. ${H.src(`${t.n} comment${t.n===1?' was':'s were'} located here against ${t.exp.toFixed(0)} expected`,'Pipeline · tract count vs. population share (ACS B01003)')}${t.n===0?'; no comments were located, so this brief makes no statement about residents’ views.':'.'} `;
 if(top&&tc.length){const c=tc.find(x=>x.cat===top[0]);s+=`The comments that were received most often concern ${H.src(CATN[top[0]].toLowerCase(),'Comment '+c.id+' and '+(top[1]-1)+' others')}. `}
 s+=`${H.src(t.lep>0.25?'Spanish and Vietnamese are the most common household languages other than English':'Spanish is the most common household language other than English','ACS 5-year C16001 · language spoken at home')}; a translated notice and an in-person session would reach the households counted here.`;return s}

/* ---------- app ---------- */
async function mount(root,init){
 await load();
 const S=Object.assign({scheme:'raw',tab:'comments',sbs:false,left:true,right:true,fairOpen:false,filtersOpen:true,attr:'renter',drawer:false,region:null,regions:[],compare:false,rmode:'raw',stance:{support:1,oppose:1,neutral:1},cats:{},mvOpen:-1,affected:new Set(),state:null,chatRegion:true,inspector:null,lightbox:null,menu:null,armed:false,hint:null,pin:null,chatExtra:[],regionState:null},init||{});
 const circ=(c,r)=>Array.from({length:28},(_,i)=>{const a=i/28*Math.PI*2;return [c[0]+Math.cos(a)*r*1.25,c[1]+Math.sin(a)*r]});
 const EAST={name:'East Side — Story Rd corridor',poly:EAST_REGION},WG={name:'Willow Glen — Lincoln Ave',poly:WG_REGION};
 if(S.region==='east')S.region=EAST;
 if(S.region==='tiny'){const t=D.tracts.filter(x=>x.e>0.5&&x.n>=6).sort((a,b)=>b.n-a.n)[0];S.region={name:t.nbhd+' — single tract',poly:circ(t.c,0.0025)}}
 if(S.region==='empty')S.region={name:'Untitled region',poly:circ([-121.715,37.318],0.006)};
 if(S.compareInit){S.regions=[EAST,WG];S.region=EAST;S.compare=true}
 if(S.inspectKind){S.inspector=D.comments.find(c=>c.src==='Email'&&c.cat==='xwalk'&&c.t.e>0.4&&!c.tr)||D.comments.find(c=>c.src==='Email')}
 if(S.region&&!S.regions.length)S.regions=[S.region];
 S.saved=[EAST,WG];if(S.tab==='region'){S.modal=true;S.tab='chat'}if(!S.region&&!S.tractDetail&&S.state!=='noitem'){S.region={name:'All of San José',poly:'city'};S.regions=[S.region]}if(S.tab==='comments')S.tab='chat';
 const stage=document.createElement('div');stage.id='stage';stage.style.width=(init.W||1440)+'px';stage.style.height=(init.H||900)+'px';root.appendChild(stage);
 const fit=()=>{const s=Math.min(innerWidth/(init.W||1440),innerHeight/(init.H||900));stage.style.transform=`translate(${Math.max(0,(innerWidth-(init.W||1440)*s)/2)}px,${Math.max(0,(innerHeight-(init.H||900)*s)/2)}px) scale(${s})`;stage._s=s};fit();addEventListener('resize',fit);
 let maps=[];
 const dotFilter=c=>S.stance[c.stance]&&(!Object.keys(S.cats).length||S.cats[c.cat]);
 const filtered=()=>D.comments.filter(dotFilter);
 const city=fairness(D.tracts,S.attr);
 const R=()=>S.region?regionTracts(S.region.poly):null;

 function top(){if(S.scheme==='raw'||S.scheme==='pop'||(S.scheme==='prob'&&!ITEM.n311))S.scheme='voice';const sch=S.scheme;return `<div class="top"><div class="brand"><b>CityLens</b><span>San José · Council staff</span></div><div class="vsep"></div>
 ${S.state==='noitem'?`<button class="picker" data-act="menu" data-m="item"><div><div class="t">Select a category</div><div class="m">No category loaded</div></div><span class="caret"></span></button>`:`<button class="picker" data-act="menu" data-m="item"><div style="min-width:0"><div class="t">${ITEM.title}</div><div class="m">${fmt(ITEM.total)} comments · ${srcLine(ITEM)}</div></div>${ITEM.n311?`<span class="badge">${n311(ITEM)}</span>`:''}<span class="caret"></span></button>`}
 ${S.view==='analytics'?`<div class="seg" aria-label="Data">${[['raw','Raw data'],['adj','Bias-adjusted']].map(([k,l])=>`<button class="${(S.anMode||'raw')===k?'on':''}" data-act="anmode" data-v="${k}">${l}</button>`).join('')}</div>`:`<div class="seg" role="tablist" aria-label="Map scheme">${[['voice','Voice'],...(ITEM.n311?[['prob','Problems']]:[]),['gap','Underheard']].map(([k,l])=>`<button data-def="${{voice:'Voice: public comments per 1,000 residents. Where people are writing in to Council.',prob:'Problems: reported problems (311 service requests) per 1,000 residents. Where people report issues.',gap:ITEM.n311?'Underheard: share of reported problems minus share of comments. High where problems are reported but no one writes in.':'Underheard: how far each tract falls below its population share of comments.'}[k]}" class="${!S.sbs&&sch===k?'on':''}" data-act="scheme" data-v="${k}">${l}</button>`).join('')}</div>
 <button class="tbtn ${S.sbs?'on':''}" data-act="sbs">${ICON.split}Side-by-side</button>${ITEM.n311?'':'<span class="nodata" style="height:28px"><i></i>No reported-problem data</span>'}`}
 <div class="spacer"></div>
  <button class="tbtn" data-act="menu" data-m="saved">Saved regions <span class="cnt">${S.saved.length}</span>${ICON.chevD}</button>
 ${S.menu==='item'?`<div class="menu" style="left:186px;width:440px"><div class="mh">Category</div>${Object.values(ITEMS).map(d=>`<div class="mi" data-act="pickitem" data-id="${d.id}"><div><div style="font-weight:500">${d.title}</div><div class="small muted">${fmt(d.total)} comments · ${srcLine(d)} ${d.n311?' · '+n311(d):''}</div></div>${ITEM.id===d.id?'<span style="margin-left:auto;font-size:12px;color:var(--ink2);padding-top:2px">Current</span>':''}</div>`).join('')}</div>`:''}
 ${S.menu==='saved'?`<div class="menu" style="right:16px;width:300px">${S.saved.map((r,i)=>`<div class="mi" data-act="loadregion" data-i="${i}"><span style="width:10px;height:10px;border:1.5px dashed ${GAP[4]};border-radius:50%;margin-top:4px;flex:none"></span><div style="flex:1"><div style="font-weight:500">${esc(r.name)}</div><div class="small muted">${regionTracts(r.poly).length} tracts</div></div></div>`).join('')}${S.saved.length>1?'<div style="border-top:1px solid var(--line);margin:6px -6px 0;padding:8px 10px 2px"><button class="btn" data-act="compare">Compare first two</button></div>':''}</div>`:''}
 </div>`}

 function filters(){const fc=filtered();const cc={};D.comments.forEach(c=>cc[c.cat]=(cc[c.cat]||0)+1);const sc={};D.comments.forEach(c=>sc[c.stance]=(sc[c.stance]||0)+1);
 return `<div class="sec"><div class="sech"><h4>Filters</h4><button class="link" data-act="togglefilters">${S.filtersOpen?'Hide':'Show'}</button></div>${S.filtersOpen?`
 <div class="lbl" style="margin-top:0">Subcategory</div><div class="sublist">${(()=>{const mx=Math.max(1,CATS.reduce((t,c)=>t+(cc[c.k]||0),0));const any=Object.keys(S.cats).length;return CATS.map(c=>{const on=!!S.cats[c.k];const n=cc[c.k]||0;return `<button class="subrow ${on?'on':''} ${any&&!on?'dim':''}" data-act="cat" data-v="${c.k}" aria-pressed="${on}"><span class="sbx">${on?'✓':''}</span><span class="snm">${c.n}</span><span class="sct num">${n}</span><span class="sbar"><i style="width:${n/mx*100}%"></i></span></button>`}).join('')})()}</div>
 <div class="lbl">Stance</div><div class="chips">${['support','oppose','neutral'].map(s=>`<button class="fchip ${S.stance[s]?'on':''}" data-act="stance" data-v="${s}" aria-pressed="${!!S.stance[s]}">${stIco(s,9)}${stLabel[s]}<span class="ct num">${sc[s]||0}</span></button>`).join('')}</div>
 <div class="small muted" style="margin-top:10px"><b class="num" style="color:var(--ink)">${fmt(fc.length)}</b> of ${fmt(D.located)} shown</div>`:`<div class="small muted">${fmt(fc.length)} of ${fmt(D.located)} shown</div>`}</div>`}

 function fairCard(){const f=fairness(D.tracts,S.attr);const A=ATTRS[S.attr];const rk=ranks(D.comments,S.attr);
 const spdC=`${A.l} tracts are ${Math.abs(Math.round(f.spd*100))} points ${f.spd<0?'less':'more'} likely to be high-volume.`;
 const diC='';
 const tiles=`<div class="tiles"><div class="tile full"><div class="k">Statistical parity difference ${H.howi('P(high-volume | '+A.l+') − P(high-volume | other) = '+f.pu.toFixed(2)+' − '+f.pp.toFixed(2))}</div><div class="v">${f.spd<0?'−':''}${Math.abs(f.spd).toFixed(2)}</div><div class="c">${spdC}</div></div><div class="tile full"><div class="k" style="justify-content:space-between"><span style="display:flex;gap:4px;align-items:center">Disparate impact ${H.howi('P(high-volume | '+A.l+') ÷ P(high-volume | other) = '+f.pu.toFixed(2)+' ÷ '+f.pp.toFixed(2))}</span>${f.di<0.8?'<span class="flag"><i></i>Below 0.8</span>':''}</div><div class="v">${f.di.toFixed(2)}</div>${H.gauge(f.di)}</div></div>`;
 if(!S.fairOpen)return `<div class="fcard"><div class="sech"><h4>Fairness</h4><button class="link" data-act="fairopen">Expand</button></div><div class="small muted" style="margin-bottom:8px">Protected attribute: <b style="color:var(--ink);font-weight:500">${A.l}</b></div><div class="tiles"><div class="tile sm"><div class="k">SPD</div><div class="v">${f.spd<0?'−':''}${Math.abs(f.spd).toFixed(2)}</div></div><div class="tile sm"><div class="k">DI</div><div class="v">${f.di.toFixed(2)}</div>${f.di<0.8?'<div style="margin-top:4px"><span class="flag"><i></i>Below 0.8</span></div>':''}</div></div></div>`;
 return `<div class="fcard"><div class="sech"><h4>Fairness</h4><button class="link" data-act="fairopen">Collapse</button></div>
 <label class="small muted" style="display:flex;align-items:center;gap:8px">Compared by<select data-act-change="attr" style="flex:1;min-width:0;font:inherit;font-size:12.5px;color:var(--ink);height:28px;border:1px solid var(--line);border-radius:4px;background:var(--panel);padding:0 6px">${Object.entries(ATTRS).map(([k,a])=>`<option value="${k}" ${S.attr===k?'selected':''}>${a.l}</option>`).join('')}</select></label>
 <div style="height:10px"></div>${tiles}
 <div style="margin:10px 0 14px"><button class="link" data-act="drawer">How is this computed?</button></div>
 <div style="border-top:1px solid #EEEEEA;padding-top:10px;display:grid;grid-template-columns:auto 1fr;gap:3px 10px;font-size:12px"><span class="muted">Top issue, raw</span><span>${(rk.find(r=>r.raw===1)||{}).n}</span><span class="muted">Top issue, pop.-weighted</span><span style="font-weight:600">${(rk.find(r=>r.pop===1)||{}).n}</span></div>
 </div>`}

 function drawer(){const A=ATTRS[S.attr];const f=fairness(D.tracts,S.attr);return `<div class="drawer"><div class="ph"><h3>How the fairness numbers are computed</h3><button class="colbtn" data-act="drawer" aria-label="Close">×</button></div><div class="scroll" style="padding:4px 20px 20px">
 <h5>High-volume tract</h5><p>A tract is high-volume when its comments per resident are at or above the 40th percentile of all ${D.tracts.length} tracts for this item (${(D.hvTh*1000).toFixed(2)} per 1,000 residents).</p>
 <h5>Statistical parity difference</h5><div class="formula">SPD = P(high | ${A.s}) − P(high | other)<br>= ${f.pu.toFixed(3)} − ${f.pp.toFixed(3)} = ${f.spd.toFixed(3)}</div><p class="muted">0 means both groups are equally likely to be high-volume. Negative means the protected group is less likely.</p>
 <h5>Disparate impact</h5><div class="formula">DI = P(high | ${A.s}) ÷ P(high | other)<br>= ${f.pu.toFixed(3)} ÷ ${f.pp.toFixed(3)} = ${f.di.toFixed(3)}</div><p class="muted">Below 0.8 fails the four-fifths rule used in U.S. employment guidance; it is used here as a reference line, not a legal finding.</p>
 <h5>Group counts</h5><table class="gc"><thead><tr><th>Group</th><th>Tracts</th><th>High-volume</th><th>Rate</th></tr></thead><tbody><tr><td>${A.l}</td><td>${f.nu}</td><td>${f.hu}</td><td>${f.pu.toFixed(2)}</td></tr><tr><td>Other tracts</td><td>${f.np}</td><td>${f.hp}</td><td>${f.pp.toFixed(2)}</td></tr><tr><td class="muted">All tracts</td><td>${f.nu+f.np}</td><td>${f.hu+f.hp}</td><td>${((f.hu+f.hp)/(f.nu+f.np)).toFixed(2)}</td></tr></tbody></table>
 <h5>Group definition</h5><p>${A.l}: ${S.attr==='renter'?'more than 50% of occupied housing units are renter-occupied':S.attr==='income'?'median household income below the San José tract median ($'+Math.round(D.medInc/1000)+'k)':S.attr==='nonwhite'?'more than 50% of residents are not non-Hispanic white':'more than 20% of households are limited-English'} (${A.acs}, ACS 5-year 2019–2023).</p>
 <h5>Theme ranking weights</h5><p><b style="font-weight:500">Raw</b>: each comment counts once. <b style="font-weight:500">Reweighed</b>: comments from each group are weighted so the group’s share of comments matches its share of population (Reweighing, Kamiran &amp; Calders 2012). <b style="font-weight:500">Population-weighted</b>: each tract’s comments are scaled to its population, so a tract with 3 comments and 6,000 residents counts as much as one with 30 comments and 6,000 residents. Tracts with no comments contribute nothing to any ranking.</p></div></div>`}

 function leftRail(){if(!S.left)return `<aside class="rail col"><div class="iconrail"><button data-act="left" aria-label="Expand filters">${ICON.chevR}</button><button class="on" data-act="left" title="Filters">${ICON.filter}</button><button data-act="left" title="Fairness">${ICON.gauge}</button></div></aside>`;
 if(S.state==='loading')return `<aside class="rail"><div class="ph"><h3>Filters</h3></div><div class="pad">${[80,180,140,200,120].map(w=>`<div class="skel" style="height:12px;width:${w/2}%;margin:10px 0"></div><div class="skel" style="height:26px;width:${w*0.45}%;margin-bottom:14px"></div>`).join('')}<div class="skel" style="height:150px;margin-top:20px"></div></div></aside>`;
 if(S.state==='noitem')return `<aside class="rail"><div class="ph"><h3>Filters</h3><button class="colbtn" data-act="left">${ICON.chevL}</button></div><div class="pad muted small">Filters and fairness metrics appear once an agenda item is loaded.</div></aside>`;
 return `<aside class="rail"><div class="ph"><h3>Filters</h3><button class="colbtn" data-act="left" aria-label="Collapse">${ICON.chevL}</button></div><div class="scroll">${filters()}</div></aside>`}

 function commentsTab(){const fc=(S.region?filtered().filter(c=>R().some(t=>t.id===c.tract)):filtered());return `<div class="ph" style="border-bottom:1px solid var(--line)"><div><h3>${fmt(fc.length)} comments</h3><div class="small muted">${S.region?'In '+S.region.name:'Located comments, current filters'} · newest first</div></div></div><div class="scroll">${fc.slice(0,40).map(c=>`<div class="ccard" data-act="inspect" data-id="${c.id}"><div class="crow"><span class="st ${c.stance}">${stIco(c.stance,10)}${stLabel[c.stance]}</span><span class="cat">${CATN[c.cat]}</span>${c.camp?'<span class="cat" style="background:var(--bg)">Campaign</span>':''}<span style="margin-left:auto">${c.when.toLocaleDateString('en-US',{month:'short',day:'numeric'})}</span></div><div class="ctext">${esc(c.text)}${c.tr?`<span class="tr">Translated from ${c.lang}: ${esc(c.tr)}</span>`:''}</div><div class="crow"><span>${c.t.nbhd}</span>${c.photo?'<span>· 1 photo</span>':''}</div></div>`).join('')}</div>`}

 function missingTop(){return [...D.tracts].sort((a,b)=>(b.exp-b.n)-(a.exp-a.n)).slice(0,5)}
 function missingTab(){const list=missingTop();return `<div class="ph"><h3>Most underheard tracts</h3></div><div class="scroll">${list.map((t,i)=>{const open=S.mvOpen===i;const b=gapBin(t);return `<div class="mvrow"><div class="mvhead" data-act="mv" data-i="${i}" style="${open?'background:#FFF8D6;box-shadow:inset 3px 0 0 #1B1B1B':''}"><div class="rankn">${i+1}</div><div><div class="mvname"><div><b>${t.nbhd}</b><div class="tid">Tract ${t.id}</div></div><span style="color:var(--ink2)">${ICON.chevR}</span></div>
 <div class="gbar" style="margin:8px 0"><span class="num" style="width:44px;font-weight:600;color:#33205F">${sgn(t.gap)}%</span><div class="b"><i style="width:${Math.min(100,Math.abs(t.gap))}%;background:${t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 3px,#7B62B8 3px 4.5px)`:GAPM[b]}"></i></div></div>
 <div class="small muted num">${t.n} of ${Math.round(t.exp)} expected comments</div></div></div>
 ${open?`<div class="brief"><div class="bh">Outreach brief</div><p>${briefFor(t,D.comments)}</p><div class="btnrow"><button class="btn" data-act="zoomto" data-t="${t.id}">Zoom to tract</button><button class="btn" data-act="copy">Copy brief</button></div></div>`:''}</div>`}).join('')}</div>`}

 const stat=(v,l)=>`<div class="stat"><b>${v}</b><span>${l}</span></div>`;
 function saidBars(cs,narrow){const tots=catTotals(cs,S.rmode,S.attr).filter(x=>x.count>0).sort((a,b)=>b.count-a.count).slice(0,5);if(!tots.length)return '<div class="small muted">No comments located here.</div>';const max=Math.max(...tots.map(x=>x.tot));const order=[...tots].sort((a,b)=>b.tot-a.tot);const rowH=34;
  return `<div class="bars" style="height:${tots.length*rowH}px">${tots.map(x=>{const y=order.indexOf(x)*rowH;const w=x.tot/max*100;const seg=s=>`<i style="flex:0 0 ${x[s]/Math.max(1e-9,x.tot)*100}%;background:${COL[s]}" title="${stLabel[s]}"></i>`;return `<div class="barrow" style="top:${y}px"><div class="bl"><span style="color:var(--ink)">${x.n}</span><span>${x.count}</span></div><div class="sbar" style="width:${Math.max(3,w)}%;height:8px">${seg('support')}${seg('oppose')}${seg('neutral')}</div></div>`}).join('')}</div>`}
 function regionBlock(reg,narrow){const tr=regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const cs=filtered().filter(c=>ids.has(c.tract));const pop=tr.reduce((s,t)=>s+t.pop,0);const A=ATTRS[S.attr];
 if(!tr.length)return `<div class="rhead"><input class="rname" value="${esc(reg.name)}"></div><div class="pad"><div class="toofew"><b>Draw over at least one neighborhood.</b></div></div>`;
 const f=fairness(tr,S.attr);const tiny=tr.length===1;const totExp=tr.reduce((s,t)=>s+t.exp,0);
 const fairH=true?'':`<div class="sec"><div class="sech"><h4>Fairness</h4><span class="small muted">${A.l}</span></div>${f.few?`<div class="small muted">Too few tracts in each group to compare fairly (${f.nu} vs ${f.np}).</div>`:`<div class="stats" style="grid-template-columns:1fr 1fr">${stat((f.spd<0?'−':'')+Math.abs(f.spd).toFixed(2),'Parity difference')}${stat(f.di.toFixed(2)+(f.di<0.8?' <span class="flag" style="vertical-align:3px"><i></i>Below 0.8</span>':''),'Disparate impact')}</div>`}</div>`;
 const seen=new Set();const quotes=[];for(const c of cs){if(quotes.length>=3)break;if(seen.has(c.text)||c.camp)continue;seen.add(c.text);quotes.push(c)}
 const photos=cs.filter(c=>c.photo).slice(0,4);
 const silent=tr.filter(t=>t.n===0||gapBin(t)>=3).sort((a,b)=>(b.exp-b.n)-(a.exp-a.n));const lim=narrow?4:5;
 const sw=t=>t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 2px,#8A74C4 2px 3px)`:GAPM[gapBin(t)];
 return `<div class="rhead"><input class="rname" value="${esc(reg.name)}" aria-label="Region name" style="${narrow?'font-size:16px':''}"><div class="stats">${stat(tr.length,'tracts')}${stat(fmt(pop),'residents')}${stat(cs.length+'<small> / '+Math.round(totExp)+'</small>','comments / expected')}</div></div>
 ${fairH}
 <div class="sec"><div class="sech"><h4>What residents said</h4><div class="seg sm">${[['raw','Raw'],['rw','Reweighed'],['pop','Pop.']].map(([k,l])=>`<button class="${S.rmode===k?'on':''}" data-act="rmode" data-v="${k}">${l}</button>`).join('')}</div></div>${saidBars(cs,narrow)}</div>
 ${silent.length?`<div class="sec"><div class="sech"><h4>Who we’re not hearing from</h4><span class="small muted">${silent.length}</span></div><div class="silent"><div class="cap">No comments located here — unknown, not absent.</div>${silent.slice(0,lim).map(t=>`<div class="srow" data-act="seltract" data-t="${t.id}" style="cursor:pointer;grid-template-columns:10px 1fr auto;align-items:center"><div class="sw" style="margin:0;background:${sw(t)}"></div><div style="font-weight:500">${t.nbhd} <span class="tid">${t.id}</span></div><div class="nums"><b>${t.n}</b> of ${Math.round(t.exp)}</div></div>`).join('')}${silent.length>lim?`<div class="srow" style="display:block;color:#33205F;font-size:12px">+ ${silent.length-lim} more</div>`:''}</div></div>`:''}
 ${quotes.length?`<div class="sec"><div class="sech"><h4>Quotes</h4></div>${quotes.map(c=>`<div class="quote" data-hover="${c.id}"><q>${esc(c.tr||c.text)}</q><div class="crow"><span class="st ${c.stance}">${stIco(c.stance,10)}</span><span>${c.t.nbhd}</span><span style="margin-left:auto">${H.cite(c)}</span></div></div>`).join('')}</div>`:''}
 ${photos.length&&!narrow?`<div class="sec"><div class="sech"><h4>Photos</h4></div><div class="thumbs">${photos.map(c=>H.thumb(CATN[c.cat].split(' ')[0].toLowerCase()+' · '+c.t.nbhd,c.id)).join('')}</div></div>`:''}
 ${narrow?'':`<details class="sec bx"><summary><h4>Outreach brief</h4><button class="btn" data-act="copy">Copy brief</button></summary><p style="margin:10px 0 0;line-height:1.6;text-wrap:pretty">${regionBrief(tr,cs,silent)}</p></details>`}`}
 function tractBlock(t){const cs=filtered().filter(c=>c.tract===t.id);const seen=new Set();const quotes=[];for(const c of cs){if(quotes.length>=3)break;if(seen.has(c.text))continue;seen.add(c.text);quotes.push(c)}
 return `<div class="rhead">${S.region?`<button class="link" data-act="untract" style="margin-bottom:8px">← ${esc(S.region.name)}</button>`:''}<div style="font-size:20px;font-weight:500">${t.nbhd}</div><div class="tid" style="margin-bottom:10px">Tract ${t.id}</div>
 <div class="stats" style="grid-template-columns:repeat(4,1fr)">${stat(fmt(t.pop),'residents')}${stat(t.n,'comments')}${stat(Math.round(t.exp),'expected')}${stat('<span style="color:var(--g4)">'+sgn(t.gap)+'%</span>','gap')}</div>
 <div class="chips" style="margin-top:12px">${H.acs(t)}</div></div>
 <div class="sec"><div class="sech"><h4>What residents said</h4></div>${saidBars(cs)}</div>
 ${t.n===0?`<div class="sec"><div class="silent"><div class="cap" style="border:0">No comments located here — unknown, not absent.</div></div></div>`:''}
 ${quotes.length?`<div class="sec"><div class="sech"><h4>Quotes</h4></div>${quotes.map(c=>`<div class="quote" data-hover="${c.id}"><q>${esc(c.tr||c.text)}</q><div class="crow"><span class="st ${c.stance}">${stIco(c.stance,10)}${stLabel[c.stance]}</span><span style="margin-left:auto">${H.cite(c)}</span></div></div>`).join('')}</div>`:''}
 <details class="sec bx"><summary><h4>Outreach brief</h4><button class="btn" data-act="copy">Copy brief</button></summary><p style="margin:10px 0 0;line-height:1.6;text-wrap:pretty">${briefFor(t,D.comments)}</p></details>`}
 function regionBrief(tr,cs,silent){const pop=tr.reduce((s,t)=>s+t.pop,0);const ren=tr.reduce((s,t)=>s+t.renter*t.pop,0)/pop;const lep=tr.reduce((s,t)=>s+t.lep*t.pop,0)/pop;const tot=catTotals(cs,'raw').sort((a,b)=>b.tot-a.tot)[0];const ex=cs.find(c=>c.cat===tot.k);const sp=silent.reduce((s,t)=>s+t.pop,0);
 return `This area has ${H.src(fmt(pop)+' residents across '+tr.length+' tracts','ACS 5-year B01003 · total population')}, ${H.src(pct(ren)+' in renter households','ACS 5-year B25003')} and ${H.src(pct(lep)+' in limited-English households','ACS 5-year C16002')}. ${H.src(silent.length+' tracts with '+fmt(sp)+' residents','Pipeline · tracts with 0 comments or gap below −55%')} sent few or no comments. Among comments that were received, the most frequent topic is ${H.src(tot.n.toLowerCase(),'Comment '+(ex?ex.id:'')+' and '+(tot.count-1)+' others')}. A translated mailer and a session at a school in the area would reach the tracts listed above.`}
 function analyticsView(){
  const reg=S.tractDetail?{name:D.byTract[S.tractDetail].nbhd,sub:'Tract '+S.tractDetail,poly:{tract:S.tractDetail}}:S.region;
  const tr=regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const cs=D.comments.filter(c=>ids.has(c.tract));
  const pop=tr.reduce((s,t)=>s+t.pop,0),exp=tr.reduce((s,t)=>s+t.exp,0);const gap=exp?Math.round((cs.length-exp)/exp*100):0;const silent=tr.filter(t=>t.n===0).length;
  const adj=S.anMode==='adj';const share=list=>{const o={};CATS.forEach(c=>o[c.k]=0);const w=adj?weights(list,'pop'):list.map(()=>1);let n=0;list.forEach((c,i)=>{o[c.cat]+=w[i];n+=w[i]});CATS.forEach(c=>o[c.k]/=(n||1));return o};const keepRM=S.rmode;S.rmode=adj?'pop':'raw';
  const rs=share(cs),city=share(D.comments);
  const rows=CATS.map(c=>({k:c.k,n:c.n,r:rs[c.k],c:city[c.k],x:city[c.k]?rs[c.k]/city[c.k]:0,count:cs.filter(x=>x.cat===c.k).length})).sort((a,b)=>b.x-a.x);
  const top=rows[0];const maxS=Math.max(...rows.map(r=>Math.max(r.r,r.c)),0.01);
  const heat=v=>d3.interpolateRgb('#FBE9E4','#8E2A1C')(Math.min(1,v/0.4));
  const areaList=[...S.saved.filter(r=>r!==S.region&&Array.isArray(r.poly)).map(r=>{const s2=new Set(regionTracts(r.poly).map(t=>t.id));return {name:r.name,cs:D.comments.filter(c=>s2.has(c.tract))}}),{name:reg.name,cs,me:1},{name:'All of San José',cs:D.comments}];
  const colCats=CATS.slice(0,6);
  const mode=t=>{const o={};D.comments.forEach(c=>{if(c.tract===t.id)o[c.cat]=(o[c.cat]||0)+1});const e=Object.entries(o).sort((a,b)=>b[1]-a[1])[0];return e?CATN[e[0]]:'—'};
  const pctS=v=>Math.round(v*100)+'%';
  return `<div class="body"><div class="an"><aside class="anside"><div class="mini" data-act="back" title="Back to map"><div class="map" id="mini"></div><span>← Back to map</span></div><div><h1>${esc(reg.name)}</h1><div class="small muted">${reg.sub?reg.sub+' · ':''}${ITEM.title}</div></div>
  <div class="kv">${stat(fmt(pop),'residents')}${stat(tr.length,'tracts')}${stat(cs.length+'<small> / '+Math.round(exp)+'</small>','comments / expected')}${stat('<span style="color:var(--g4)">'+sgn(gap)+'%</span>','participation gap')}${stat(silent,'tracts with no comments')}</div></aside>
  <div class="anmain">
  <section class="card span2"><h4>Issues that stand out here</h4>${cs.length?`${reg.poly==='city'?(()=>{const b=[...rows].sort((p,q)=>q.r-p.r)[0];return `<p class="lead"><b style="font-weight:600">${b.n}</b> is the most common issue citywide: <b style="font-weight:600">${Math.round(b.r*100)}%</b> of ${adj?'bias-adjusted':'raw'} comments.</p>`})():`<p class="lead"><b style="font-weight:600">${top.n}</b> comes up <b style="font-weight:600">${top.x.toFixed(1)}×</b> as often here as citywide.</p>`}
   <div class="xrow xh"><span></span><span><i class="sw" style="background:#B3412B"></i>This area <i class="sw" style="background:#B6B0A5;margin-left:10px"></i>Citywide</span><span>Share</span><span>vs city</span></div>
   ${rows.map(r=>`<div class="xrow"><span>${r.n}</span><div class="xbars"><i style="width:${r.r/maxS*100}%;background:#B3412B"></i><i style="width:${r.c/maxS*100}%;background:#B6B0A5"></i></div><span class="num">${pctS(r.r)} vs ${pctS(r.c)}</span><span class="num" style="font-weight:${r.x>=1.3?600:400};color:${r.x>=1.3?'#8E2A1C':'var(--ink2)'}">${r.x.toFixed(1)}×</span></div>`).join('')}`:'<div class="small muted">No comments located in this area.</div>'}</section>
  <section class="card"><h4>Issue share by area</h4><table class="ht"><thead><tr><th></th>${colCats.map(c=>`<th>${c.n.split(' ')[0].replace(/[&,]/g,'')}</th>`).join('')}</tr></thead><tbody>${areaList.map(a=>{const sh=share(a.cs);return `<tr style="${a.me?'font-weight:600':''}"><td>${esc(a.name)}</td>${colCats.map(c=>`<td style="background:${heat(sh[c.k])};color:${sh[c.k]>.24?'#fff':'var(--ink)'}">${pctS(sh[c.k])}</td>`).join('')}</tr>`}).join('')}</tbody></table><div class="small muted" style="margin-top:8px">Share of each area’s comments. Deeper red = larger share.</div></section>
  <section class="card"><h4>Stance by issue</h4>${saidBars(cs)}<div class="stkey" style="border:0;padding-top:4px"><span>${stIco('support',9)}Support</span><span>${stIco('oppose',9)}Oppose</span><span>${stIco('neutral',9)}Neutral</span></div></section>
  <section class="card span2"><h4>Missing voices</h4><div class="small muted" style="margin:-6px 0 10px">Tracts sending the fewest comments relative to population. No comments located — unknown, not absent.</div>${[...tr].sort((a,b)=>(b.exp-b.n)-(a.exp-a.n)).slice(0,5).map((t,i)=>`<div class="mvl" data-act="seltract" data-t="${t.id}"><span class="rankn">${i+1}</span><div><b style="font-weight:600">${t.nbhd}</b> <span class="tid">${t.id}</span></div><div class="gbar"><div class="b"><i style="width:${Math.min(100,Math.abs(Math.min(0,t.gap)))}%;background:${t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 3px,#7B62B8 3px 4.5px)`:GAPM[gapBin(t)]}"></i></div></div><span class="num small">${t.n} of ${t.exp<1?t.exp.toFixed(1):Math.round(t.exp)}</span><div class="chips">${H.acs(t)}</div></div>`).join('')}</section>
  <section class="card span2"><h4>Tracts in this area</h4><table class="ht tt"><thead><tr><th>Tract</th><th>Residents</th><th>Comments</th><th>Expected</th><th>Gap</th><th>Top issue</th></tr></thead><tbody>${[...tr].sort((a,b)=>a.gap-b.gap).slice(0,14).map(t=>`<tr><td><b style="font-weight:500">${t.nbhd}</b> <span class="tid">${t.id}</span></td><td>${fmt(t.pop)}</td><td>${t.n}</td><td>${Math.round(t.exp)}</td><td style="color:var(--g4);font-weight:500">${sgn(t.gap)}%</td><td>${mode(t)}</td></tr>`).join('')}</tbody></table>${tr.length>14?`<div class="small muted" style="margin-top:6px">+ ${tr.length-14} more tracts</div>`:''}</section>
  </div></div></div>`+(S.rmode=keepRM,'')}
 function popBlock(){
  const isT=!!S.tractDetail;const reg=S.region;const t0=isT?D.byTract[S.tractDetail]:null;const city=!isT&&reg&&reg.poly==='city';
  const tr=isT?[t0]:regionTracts(reg.poly);const ids=new Set(tr.map(t=>t.id));const cs=D.comments.filter(c=>ids.has(c.tract));
  const pop=tr.reduce((s,t)=>s+t.pop,0)||1,exp=tr.reduce((s,t)=>s+t.exp,0);const gap=exp?Math.round((cs.length-exp)/exp*100):0;
  const wavg=(L,k)=>L.reduce((s,t)=>s+t[k]*t.pop,0)/Math.max(1,L.reduce((s,t)=>s+t.pop,0));
  const cR=wavg(D.tracts,'renter'),cL=wavg(D.tracts,'lep'),rR=wavg(tr,'renter'),rL=wavg(tr,'lep');
  const cnt=L=>{const o={};L.forEach(c=>o[c.cat]=(o[c.cat]||0)+1);return o};const rc=cnt(cs),cc=cnt(D.comments);
  const topK=Object.entries(rc).sort((a,b)=>b[1]-a[1])[0];const silent=tr.filter(t=>t.n===0);const sPop=silent.reduce((s,t)=>s+t.pop,0);
  const row=(v,l,sm)=>`<div class="prow"><b>${v}</b><div><div class="pl">${l}</div>${sm?`<div class="ps">${sm}</div>`:''}</div></div>`;
  const vs=(a,b)=>`${pct(a)} citywide${a>0&&b/a>=1.25?` · ${(b/a).toFixed(1)}× higher here`:''}`;
  let rows='';
  if(city){const rk=ranks(D.comments,S.attr);rows+=row(fmt(D.located),'comments on the map',`${ITEM.pct}% of ${fmt(ITEM.total)} received could be located`);
   rows+=row(CATN[topK[0]],'top issue, raw count',`Population-weighted, the top issue is ${(rk.find(r=>r.pop===1)||{}).n}`);
   rows+=row(`${silent.length}`,'tracts with no comments',`${fmt(sPop)} residents · unknown, not absent`);}
  else{
   rows+=row(`${cs.length}<small> / ${Math.round(exp)}</small>`,'comments / expected',cs.length===0?'No comments located — unknown, not absent':gap<0?`${Math.abs(gap)}% fewer than population share predicts`:`${gap}% more than population share predicts`);
   if(topK)rows+=row(CATN[topK[0]],'top issue',`${pct(topK[1]/cs.length)} of comments here vs ${pct((cc[topK[0]]||0)/D.comments.length)} citywide`);
   if(!isT)rows+=row(`${silent.length}<small> / ${tr.length}</small>`,'tracts with no comments',`${fmt(sPop)} residents`);
   rows+=row(pct(rR),'renter households',vs(cR,rR));
   rows+=row(pct(rL),'limited-English households',vs(cL,rL));
   if(isT)rows+=row('',incLabel(t0),'');}
  const title=isT?t0.nbhd:reg.name;const sub=isT?`Tract ${t0.id} · ${fmt(t0.pop)} residents`:`${tr.length} tracts · ${fmt(pop)} residents`;
  return `<div class="rmh"><div style="min-width:0">${isT&&reg?`<button class="link" data-act="untract" style="font-size:11.5px">← ${esc(reg.name)}</button>`:''}<div class="pt">${esc(title)}</div><div class="small muted">${sub}</div></div><button class="colbtn" data-act="closemodal" aria-label="Close">×</button></div><div class="prows">${rows}</div><div class="rmf"><button class="btn pri" data-act="analytics" style="width:100%;justify-content:center;height:32px">Open analytics</button></div>`}
 function placePop(){const el=document.querySelector('.rmodal');const m=maps[0];if(!el||!m)return;let b;
  if(S.tractDetail){const cb=D.byTract[S.tractDetail].cb;const p0=m.screen([cb[0],cb[3]]),p1=m.screen([cb[2],cb[1]]);b=[p0[0],p0[1],p1[0],p1[1]]}
  else if(S.region&&Array.isArray(S.region.poly)){const P=S.region.poly.map(p=>m.screen(p));b=[Math.min(...P.map(p=>p[0])),Math.min(...P.map(p=>p[1])),Math.max(...P.map(p=>p[0])),Math.max(...P.map(p=>p[1]))]}
  else{el.style.left=(m.w-el.offsetWidth-60)+'px';el.style.top='70px';return}
  const w=el.offsetWidth,h=el.offsetHeight;let y=b[3]+12;if(y+h>m.h-10){const up=b[1]-12-h;y=up>=10?up:Math.max(10,m.h-h-10)}
  const x=Math.max(10,Math.min(m.w-w-56,(b[0]+b[2])/2-w/2));el.style.left=x+'px';el.style.top=y+'px'}
 function regionTab(){
  if(S.regionState==='loading')return `<div class="progress"><i></i></div><div class="pad">${[60,30].map(w=>`<div class="skel" style="height:20px;width:${w}%;margin-bottom:8px"></div>`).join('')}<div class="tiles" style="margin:14px 0"><div class="skel" style="height:80px"></div><div class="skel" style="height:80px"></div></div>${[90,70,55,40,30].map(w=>`<div class="skel" style="height:10px;width:30%;margin:12px 0 5px"></div><div class="skel" style="height:16px;width:${w}%"></div>`).join('')}<div class="skel" style="height:70px;margin-top:18px"></div></div>`;
  if(S.tractDetail)return `<div class="scroll">${tractBlock(D.byTract[S.tractDetail])}</div>`;
  if(!S.region)return `<div class="pad"><div class="toofew"><b>No region drawn.</b><div class="small muted" style="margin:4px 0 10px">Use Draw region in the top bar, then click on the map to place points. Click the first point to close.</div><button class="btn" data-act="draw">${ICON.pen}Draw region</button></div></div>`;
  if(S.compare&&S.regions.length>1)return `<div style="display:grid;grid-template-columns:1fr 1fr;min-height:0;flex:1"><div class="scroll" style="border-right:1px solid var(--line)">${regionBlock(S.regions[0],true)}</div><div class="scroll">${regionBlock(S.regions[1],true)}</div></div>`;
  return `<div class="scroll">${regionBlock(S.region)}</div>`}

 function chatTab(compact){const drawn=!!S.region&&Array.isArray(S.region.poly);const useR=S.chatRegion&&(drawn||!!S.tractDetail);const tr=S.tractDetail?[D.byTract[S.tractDetail]]:drawn?regionTracts(S.region.poly):[];const ids=new Set(tr.map(t=>t.id));const cs=useR?D.comments.filter(c=>ids.has(c.tract)):D.comments;const by=k=>cs.filter(c=>c.cat===k);const tops=catTotals(cs,'raw').sort((a,b)=>b.count-a.count);const t1=tops[0],t2=tops[1];const pick=(a,n)=>{const s=new Set(),o=[];for(const c of a){if(o.length>=n)break;if(!s.has(c.text)){s.add(c.text);o.push(c)}}return o};const ph=cs.filter(c=>c.photo).slice(0,4);
 const inArea=!useR?'':S.tractDetail?`<div class="inarea">In ${esc(D.byTract[S.tractDetail].nbhd)}</div>`:'<div class="inarea">In the area you drew</div>';
 const open=S.openCite;const card=id=>{if(open!==id)return '';const c=D.comments.find(x=>x.id===id);return `<div class="inl"><div class="crow" style="margin-bottom:4px"><span class="st ${c.stance}">${stIco(c.stance,10)}${stLabel[c.stance]}</span><span class="cat">${CATN[c.cat]}</span><span>${c.t.nbhd} · ${c.tract}</span></div>“${esc(c.text)}”${c.tr?`<div class="small muted">Translated: ${esc(c.tr)}</div>`:''}<div style="margin-top:6px"><button class="link" data-act="inspect" data-id="${c.id}">Open full comment</button></div></div>`};
 const cites=a=>`<div class="cites">${a.map(c=>H.cite(c)).join('')}</div>${a.map(c=>card(c.id)).join('')}`;
 const xa=pick(by(t1.k),3),la=pick(by(t2.k),2);
 const msgs=[`<div class="mu">What are the top concerns here?</div>`,
 `<div class="ma${t1.count?'':' refuse'}">${t1.count?'<div class="who">Assistant</div>':'<div class="rt">No supporting comments</div>'}${inArea}${t1.count?`<p>The most frequent topic is ${t1.n.toLowerCase()}, with ${t1.count} comment${t1.count===1?'':'s'}.</p>${cites(xa)}${t2&&t2.count?`<p style="margin-top:10px">${t2.n} comes second, with ${t2.count}.</p>${cites(la)}`:''}`:`<p style="margin:0">No comments on this item${useR?' were located '+(S.tractDetail?'in this tract':'in the area you drew'):''}, so there is nothing to summarize.</p>`}</div>`,
 ...(compact?[]:[`<div class="mu">Show me photos residents attached.</div>`,
 `<div class="ma"><div class="who">Assistant</div>${inArea}<p>${ph.length?ph.length+" comments include photos.":"No photos are attached to these comments."} Faces and license plates were blurred at ingest; originals are not stored.</p><div class="thumbs" style="margin-bottom:6px">${ph.map(c=>H.thumb(CATN[c.cat].split(' ')[0].toLowerCase()+' · '+c.t.nbhd,c.id)).join('')}</div>${cites(ph.slice(0,2))}</div>`,
 `<div class="mu">What do residents here think about library hours?</div>`,
 `<div class="ma refuse"><div class="rt">No supporting comments</div><p style="margin:0">None of the ingested comments on this item ${useR?(S.tractDetail?'located in '+esc(D.byTract[S.tractDetail].nbhd)+' ':'located in the area you drew '):''}mention library hours, so I can’t answer this.</p></div>`]),...S.chatExtra];
 const ctx=S.tractDetail?D.byTract[S.tractDetail].nbhd:S.region?S.region.name:null;
 return `${ctx?`<div class="ctxbar"><div style="min-width:0"><div class="small muted">${S.tractDetail?'Tract':'Region'}</div><div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(ctx)}</div></div><button class="btn" data-act="analytics">View analytics</button></div>`:''}<div class="scroll"><div class="msgs">${msgs.join('')}</div></div><div class="compose"><div class="notice"><i></i>Answers only from ingested comments on this item. Not public-facing.</div><div class="cbox">${useR?`<div><span class="composer-chip">${S.tractDetail?'Tract: '+esc(D.byTract[S.tractDetail].nbhd):'Region: '+esc(S.region.name.split(' — ')[0])+' — '+tr.length+' tracts'}<button data-act="rmchip" aria-label="Remove region">×</button></span></div>`:''}<textarea rows="2" placeholder="Ask about this item or the area you drew"></textarea><div class="r"><span></span><button class="btn pri" style="height:30px" data-act="send">Send</button></div></div></div>`}

 function rightPanel(){const tabs=[['chat','Chat',ICON.chat]];S.tab='chat';
 if(!S.right)return `<aside class="rpanel col"><div class="iconrail"><button data-act="right" aria-label="Expand panel">${ICON.chevL}</button>${tabs.map(t=>`<button class="${S.tab===t[0]?'on':''}" data-act="tab" data-v="${t[0]}" title="${t[1]}">${t[2]}</button>`).join('')}</div></aside>`;
 let body='';
 if(S.state==='loading')body=`<div class="pad">${[1,2,3,4,5].map(()=>`<div style="padding:10px 0;border-bottom:1px solid #EEEEEA"><div class="skel" style="height:12px;width:40%;margin-bottom:8px"></div><div class="skel" style="height:12px;width:95%;margin-bottom:5px"></div><div class="skel" style="height:12px;width:70%"></div></div>`).join('')}</div>`;
 else if(S.state==='noitem')body=`<div class="pad muted small">Comments, Missing Voices, and Chat appear once an agenda item is loaded.</div>`;

 else body=S.tab==='comments'?commentsTab():S.tab==='missing'?missingTab():S.tab==='region'?regionTab():chatTab();
 return `<aside class="rpanel"><div class="tabs">${tabs.map(t=>`<button class="${S.tab===t[0]?'on':''} ${t[0]==='region'&&!S.region&&!S.tractDetail?'dis':''}" data-act="tab" data-v="${t[0]}">${t[1]}</button>`).join('')}<span class="sp"></span><button class="colbtn" data-act="right" aria-label="Collapse">${ICON.chevR}</button></div><div style="flex:1;display:flex;flex-direction:column;min-height:0">${body}</div></aside>`}

 function footer(){return `<footer class="foot"><div class="fi">Sources: <a href="https://sanjose.legistar.com" target="_blank" rel="noopener">San José eComments</a>, <a href="https://www.sanjoseca.gov" target="_blank" rel="noopener">San José 311</a>, <a href="https://www.census.gov/programs-surveys/acs" target="_blank" rel="noopener">ACS 5-year</a>, <a href="https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html" target="_blank" rel="noopener">Census TIGER</a></div><div class="fi"><b>${D.tracts.length}</b> tracts drawn</div><div class="fi covwrap">Coverage <b>${ITEM.pct}%</b> located <span class="howi">?</span><div class="covtip" style="left:0">${(()=>{const a=D.tracts.reduce((s,t)=>s+t.prec[0],0),z=D.tracts.reduce((s,t)=>s+t.prec[2],0),nb=D.located-a-z,no=ITEM.total-D.located,T=ITEM.total,p=x=>Math.round(x/T*100)+"%";return `<div class="pbar" style="height:6px"><i style="flex:${a};background:#1B1B1B"></i><i style="flex:${nb};background:#5C5C58"></i><i style="flex:${z};background:#B6B0A5"></i><i style="flex:${no};background:#EFEFEB"></i></div><dl style="display:grid;grid-template-columns:1fr auto auto;gap:3px 10px;margin:6px 0 0" class="num"><dt>Address</dt><dd style="margin:0">${fmt(a)}</dd><dd style="margin:0">${p(a)}</dd><dt>Neighborhood</dt><dd style="margin:0">${fmt(nb)}</dd><dd style="margin:0">${p(nb)}</dd><dt>ZIP only</dt><dd style="margin:0">${fmt(z)}</dd><dd style="margin:0">${p(z)}</dd><dt>Not located</dt><dd style="margin:0">${fmt(no)}</dd><dd style="margin:0">${p(no)}</dd></dl>`})()}</div></div><div class="fi" style="display:none">Pipeline: ${S.state==='fallback'?'<b style="color:#6B4710">rule-based classification</b>':'local classifier + rules'} v0.9</div></footer>`}

 function mapArea(){
  if(S.sbs)return `<div class="mapwrap"><div class="maps"><div class="map" id="m0"><div class="citylabel sm">San José</div><div class="mlabel">Voice <span>comments per 1k</span></div></div><div class="divider"></div><div class="map" id="m1"><div class="mlabel">Underheard <span>participation gap</span></div></div></div><div class="sharedlegend"><div><span class="lt">Comments per tract</span><div><div class="ramp">${RAW.map((c,i)=>`<div style="background:${i?c:RAWZ};box-shadow:inset 0 0 0 1px rgba(0,0,0,.05)"></div>`).join('')}</div><div class="rampl"><span>0</span><span>1–4</span><span>5–9</span><span>10–17</span><span>18+</span></div></div></div><div class="sep"></div><div><span class="lt">Participation gap</span><div><div class="ramp">${GAPM.map((c,i)=>`<div style="background:${i===4?`repeating-linear-gradient(45deg,${c} 0 3px,#7B62B8 3px 4.5px)`:c}"></div>`).join('')}</div><div class="rampl"><span>at/above share</span><span>−30%</span><span>−55%</span><span>−80%</span><span>silent</span></div></div></div></div></div>`;
  return `<div class="mapwrap"><div class="maps"><div class="map" id="m0"><div class="citylabel">San José<span>City limits · ${D.tracts.length} census tracts</span></div>${S.state==='noitem'?'':H.legend(S.scheme)}${S.modal&&(S.region||S.tractDetail)&&!S.regionState?`<div class="rmodal pop" role="dialog">${popBlock()}</div>`:''}${S.state==='noitem'?'':`<button class="tbtn mapdraw ${S.armed?'armed':''}" data-act="draw">${ICON.pen}${S.armed?'Drawing… Esc to cancel':'Draw region'}</button>`}<div class="zoomc"><button data-act="zin" aria-label="Zoom in">+</button><button data-act="zout" aria-label="Zoom out">−</button><button data-act="zreset" aria-label="Whole city">City</button></div>${S.menu==='city'?`<div class="menu" style="top:14px;right:52px;min-width:240px"><div class="mi" data-act="cityregion"><div><div style="font-weight:500">Select all of San José</div><div class="small muted">${D.tracts.length} tracts · opens in Region</div></div></div></div>`:''}${S.state==='noitem'?`<div class="centerprompt"><h2>Choose an agenda item</h2><p>Every census tract in San José is shown. Pick an item to place its public comments.</p><p style="margin:0;font-size:12.5px">Use the item picker in the top bar.</p></div>`:''}</div></div></div>`}

 const tip=document.createElement('div');tip.className='ttip';tip.style.display='none';
 const srcTip=document.createElement('div');srcTip.className='srctip';srcTip.style.display='none';document.body.appendChild(srcTip);
 function onHover(t,p,mv){maps.forEach(m=>m.hover(t));if(!t){if(!S.pin)tip.style.display='none';return}showTip(t,p,mv)}
 function showTip(t,p,mv){mv.el.appendChild(tip);tip.innerHTML=H.tip(t);tip.style.display='block';let x=p[0]+16,y=p[1]+12;if(x+272>mv.w)x=p[0]-284;if(y+tip.offsetHeight>mv.h-8)y=mv.h-tip.offsetHeight-8;tip.style.left=x+'px';tip.style.top=y+'px'}
 function heatTh(){const fc=filtered();const sc=Math.max(.05,fc.length/Math.max(1,D.located));D.thSc=sc;const o={};D.tracts.forEach(t=>o[t.id]=0);fc.forEach(c=>o[c.tract]++);const nz=Object.values(o).filter(v=>v>0).sort((a,b)=>a-b);const q=p=>nz.length?nz[Math.floor(p*(nz.length-1))]:1;const a1=Math.max(2,q(.35)+1),a2=Math.max(a1+1,q(.65)+1),a3=Math.max(a2+1,q(.88)+1);D.th=[1,a1,a2,a3];
  const T=D.tracts,vt=T.reduce((a,t)=>a+o[t.id],0)||1,pt=T.reduce((a,t)=>a+t.p311,0)||1;
  T.forEach(t=>{t.vrate=o[t.id]/t.pop*1000;t.prate=t.p311/t.pop*1000;t.pgap=(t.p311/pt-o[t.id]/vt)*100});
  const qq=a=>{a=a.filter(x=>x>0).sort((x,y)=>x-y);return a.length?[.25,.5,.75].map(p=>a[Math.floor(a.length*p)]):[1,2,3]};
  D.qb={voice:qq(T.map(t=>t.vrate)),prob:qq(T.map(t=>t.prate)),gap:qq(T.map(t=>t.pgap))};return o}
 function styleMaps(){const fcnt=heatTh();const inR=S.region&&S.region.poly!=='city'?new Set(regionTracts(S.region.poly).map(t=>t.id)):null;const inAll=S.compare&&S.regions.length>1?new Set(S.regions.flatMap(r=>regionTracts(r.poly).map(t=>t.id))):inR;
  maps.forEach((m,i)=>{if(S.selTract===undefined&&S.mvOpen>=0)S.selTract=missingTop()[S.mvOpen].id;m.select(S.selTract?D.byTract[S.selTract]:null);m.style({cnt:fcnt,scheme:S.sbs?(i?'gap':'voice'):S.scheme,polys:(S.compare?S.regions:S.region?[S.region]:[]).map(r=>r.poly).filter(p=>Array.isArray(p)),dotFilter,empty:S.state==='noitem'||S.state==='loading'});m.regions(S.compare?S.regions:S.region?[S.region]:[])});placeHandle()}
 function placeHandle(){document.querySelectorAll('.rhandle').forEach(e=>e.remove());if(!maps[0]||S.sbs)return;const list=(S.compare?S.regions:S.region?[S.region]:[]).filter(r=>r.poly!=='city');list.forEach((r,i)=>{const m=maps[0];const pts=r.poly.map(p=>m.screen(p));const xs=pts.map(p=>p[0]),ys=pts.map(p=>p[1]);const x=Math.max(...xs),y=Math.min(...ys);const h=document.createElement('div');h.className='rhandle';h.innerHTML=`<span class="nm"><i></i>${esc(r.name)}</span>${S.compare?'':'<span class="sep"></span><button data-act="rename">Rename</button>'+(S.saved.includes(r)?'<button disabled style="opacity:.6;cursor:default">Saved</button>':'<button data-act="save">Save</button>')+'<button data-act="del">Delete</button>'}`;m.el.appendChild(h);h.style.left=Math.max(8,Math.min(m.w-h.offsetWidth-56,x-h.offsetWidth/2))+'px';h.style.top=Math.max(8,y-40)+'px'})}

 function render(){
  if(S.view==='analytics'&&(S.region||S.tractDetail)){heatTh();stage.innerHTML=top()+analyticsView()+footer();const el=stage.querySelector('#mini');const sel=S.tractDetail?[D.byTract[S.tractDetail]]:regionTracts(S.region.poly);const ids=new Set(sel.map(t=>t.id));const whole=sel.length===D.tracts.length;let focus=null;
   if(!whole){const b=[1e9,1e9,-1e9,-1e9];sel.forEach(t=>{const bb=bbox(t.geometry);b[0]=Math.min(b[0],bb[0]);b[1]=Math.min(b[1],bb[1]);b[2]=Math.max(b[2],bb[2]);b[3]=Math.max(b[3],bb[3])});const px=(b[2]-b[0])*0.35+0.004,py=(b[3]-b[1])*0.35+0.003;focus=[b[0]-px,b[1]-py,b[2]+px,b[3]+py]}
   const m=new MapView(el,{static:true,pad:12,focus});const drawnA=!S.tractDetail&&S.region&&Array.isArray(S.region.poly);const qb=(D.qb||{voice:[1,2,3]}).voice;const hq=t=>{const v=t.vrate||0;return v===0?'url(#hatchRaw)':RAW[v<qb[0]?1:v<qb[1]?2:v<qb[2]?3:4]};
   if(drawnA){const cid='mc'+Math.random().toString(36).slice(2,7);m.svg.select('defs').append('clipPath').attr('id',cid).append('path').attr('d',d3.line().curve(d3.curveLinearClosed)(S.region.poly.map(p=>m.proj(p))));m.gT.attr('clip-path',null);const bg=m.gT.node().cloneNode(true);m.gT.node().parentNode.insertBefore(bg,m.gT.node());d3.select(bg).selectAll('path').attr('fill','#ECEBE7').attr('stroke','#FFFFFF').attr('stroke-width',.6);m.gT.attr('clip-path',`url(#${cid})`);m.regions([S.region])}
   m.tp.attr('fill',t=>drawnA?hq(t):ids.has(t.id)?'#7357B4':'#ECEBE7').attr('stroke','#FFFFFF').attr('stroke-width',.6).attr('opacity',1);m.dp.attr('display','none');maps=[];return}
  heatTh();const keepM=document.querySelector('.rmodal .scroll');const stM=keepM?keepM.scrollTop:0;
  const keep=document.querySelector('.rpanel .scroll');const st=keep?keep.scrollTop:0;const keepL=document.querySelector('.rail .scroll');const stL=keepL?keepL.scrollTop:0;
  stage.innerHTML=top()+(S.state==='fallback'?`<div class="banner"><span class="dia"></span><span>Running rule-based classification; AI labels unavailable.</span></div>`:'')+`<div class="body">${S.sbs?'':leftRail()}${mapArea()}${rightPanel()}${S.drawer&&!S.sbs?drawer():''}</div>`+footer()+(S.inspector?inspector():'')+(S.lightbox?lightbox():'');
  const prevT=maps[0]?maps[0].k:null;
  maps=[...stage.querySelectorAll('.map')].map((el,i)=>new MapView(el,{onHover,regionOpen:r=>S.modal&&!S.tractDetail&&S.region===r&&!S.compare,onRegion:r=>{if(S.compare){const k=S.regions.indexOf(r);if(k>=0){S.region=r;S.regions=[r];S.compare=false}}S.selTract=null;S.tractDetail=null;S.modal=true;S.right=true;render()},onPick:(t,dbl)=>{const drawn=S.region&&Array.isArray(S.region.poly)&&!S.compare;if(drawn&&!dbl&&inRing(t.c,S.region.poly)){S.selTract=null;S.tractDetail=null;S.modal=true;S.right=true;render();return}const off=S.selTract===t.id;S.selTract=off?null:t.id;S.tractDetail=off?null:t.id;if(!off){S.modal=true;S.right=true}render()},onZoom:(t,src)=>{maps.forEach(m=>{if(m!==src)m.setT(t)});tip.style.display='none';placeHandle()}}));
  if(prevT&&prevT.k!==1)maps.forEach(m=>m.setT(prevT));
  else if(S.initZoom&&!S._z){S._z=1;const m=maps[0];const [x,y]=m.proj(S.initZoom.c);const k=S.initZoom.k;const t=d3.zoomIdentity.translate(m.w/2-x*k,m.h/2-y*k).scale(k);maps.forEach(mm=>mm.setT(t))}
  maps.forEach(m=>m.onApply=()=>{placeHandle();placePop()});
  styleMaps();
  if(S.armed)armDraw();
  if(S.hint){const h=document.createElement('div');h.className='hint';h.textContent=S.hint;maps[0].el.appendChild(h)}
  if(S.pin&&!S.pinShown){const t=S.pin.kind==='under'?D.tracts.filter(x=>x.n>=2&&x.gap<-55).sort((a,b)=>b.pop-a.pop)[0]:S.pin.kind==='zero'?D.tracts.filter(x=>x.n===0).sort((a,b)=>b.exp-a.exp)[0]:D.byTract[S.pin.id];maps.forEach(m=>m.hover(t));const m=maps[S.pin.map||0];showTip(t,m.screen(t.c),m)}
  if(S.modal&&maps[0]&&!S.sbs){const tg=S.tractDetail?{pts:(b=>[[b[0],b[1]],[b[2],b[3]]])(D.byTract[S.tractDetail].cb)}:S.region&&Array.isArray(S.region.poly)?{pts:S.region.poly}:null;const key=S.tractDetail||(S.region&&S.region.name+(Array.isArray(S.region.poly)?S.region.poly.length:''));if(tg&&key!==S._fitKey&&!S.regionState){S._fitKey=key;const m=maps[0];const mw=(S.compare&&!S.tractDetail?640:380)+70;setTimeout(()=>m.fitTo(tg,[40,40,m.w-60,m.h*0.48]),0)}}
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
 function armDraw(){maps[0].armDraw(true,ll=>{S.armed=false;S.hint=null;const reg={name:'Untitled region',poly:ll};const n=regionTracts(ll).length;reg.name=n?`Drawn region — ${D.byTract[regionTracts(ll)[0].id].nbhd}`:'Untitled region';S.tractDetail=null;S.selTract=null;window.__drawEnd=Date.now();S.selTract=null;S.tractDetail=null;S.region=reg;S.toast='Region selected · double-click inside to pick a single tract';setTimeout(()=>{S.toast=null;const e=document.querySelector('.maptoast');if(e)e.remove()},4500);S.regions=[reg,...S.regions.filter(r=>r!==S.region)].slice(0,2);S.compare=false;S.modal=true;S.right=true;S.regionState='loading';render();setTimeout(()=>{S.regionState=null;render()},380)},h=>{const e=maps[0].el.querySelector('.hint');if(e)e.textContent=h})}
 function inspector(){const c=S.inspector;const email=c.src==='Email';const hlw=c.text.split(' ').slice(0,Math.min(9,c.text.split(' ').length)).join(' ');const body=esc(c.text).replace(esc(hlw),`<mark>${esc(hlw)}</mark>`);
 return `<div class="scrim" data-act="closeinsp"><div class="modal" data-stop="1" role="dialog" aria-label="Comment inspector"><div class="mhd"><h3><code style="font-family:var(--mono);font-size:14px">${c.id}</code><span class="st ${c.stance}">${stIco(c.stance,11)}${stLabel[c.stance]}</span></h3><div class="btnrow"><button class="btn" data-act="zoomto" data-t="${c.tract}">Show on map</button><button class="colbtn" data-act="closeinsp" aria-label="Close" style="width:30px;height:30px">×</button></div></div><div class="mbody"><div class="raw"><div class="small muted" style="margin-bottom:8px;font-weight:500;text-transform:uppercase;letter-spacing:.06em">As received · ${c.src}</div>
 <div class="ehdr">${email?`<div>From: <span class="rmv">removed at ingest</span></div><div>To: <b>city.clerk@sanjoseca.gov</b></div><div>Subject: <b>Public comment — ${ITEMS[c.item].title}</b></div><div>Date: <b>${c.when.toLocaleDateString('en-US',{weekday:'short',day:'numeric',month:'short',year:'numeric'})} ${c.when.toTimeString().slice(0,8)} -0700</b></div><div>X-Mailer: <b>iPhone Mail (21G93)</b></div>`:`<div>Form: <b>eComment</b></div><div>Name: <span class="rmv">removed at ingest</span></div><div>Address: <span class="rmv">removed at ingest</span> → ZIP 95122 retained</div><div>Submitted: <b>${c.when.toLocaleString('en-US')}</b></div>`}</div>
 <div class="ebody">Hello,

${body} ${c.cat==='xwalk'?'<mark>The crossing guard can only do so much.</mark> ':''}I have lived on Lucretia for 11 years.

${c.tr?'('+esc(c.tr)+')\n\n':''}Please consider this before the vote.

Thank you,
<span class="rmv">[name removed at ingest]</span>

Sent from my iPhone</div>
 ${c.photo||true?`<div style="margin-top:18px"><div class="small muted" style="margin-bottom:6px">Attachments (2)</div><div class="thumbs">${H.thumb('IMG_4471.jpg · crossing',c.id)}${H.thumb('IMG_4472.jpg · street',c.id)}</div></div>`:''}</div>
 <div class="rec"><div class="small muted" style="margin-bottom:10px;font-weight:500;text-transform:uppercase;letter-spacing:.06em">Structured record</div><dl>
 <dt>Source</dt><dd>${c.src}</dd><dt>Received</dt><dd class="num">${c.when.toLocaleString('en-US',{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit'})}</dd><dt>Language</dt><dd>${c.lang}${c.tr?' · translated for staff':''}</dd>
 <dt>Stance</dt><dd><span class="st ${c.stance}">${stIco(c.stance,10)}${stLabel[c.stance]}</span><span class="prov">${S.state==='fallback'?'rule-based':'AI-labeled'}</span><div class="small muted" style="margin-top:3px">Evidence highlighted at left. Resident did not state a position explicitly.</div></dd>
 <dt>Categories</dt><dd class="chips"><span class="cat">${CATN[c.cat]}</span>${c.cat==='xwalk'?'<span class="cat">Speeding &amp; traffic calming</span>':''}</dd>
 <dt>Tract</dt><dd>${c.t.nbhd} · <code style="font-family:var(--mono);font-size:12px">${c.tract}</code></dd>
 <dt>Location precision</dt><dd><b style="font-weight:600">${c.tier[0].toUpperCase()+c.tier.slice(1)}</b> <span class="muted">(address / neighborhood / zip / none)</span><div class="small muted" style="margin-top:3px">${c.tier==='address'?'Street address geocoded to a tract, then discarded. The dot is placed at random inside the tract.':c.tier==='neighborhood'?'Resident named a street or neighborhood (“Lucretia”); matched to the tract containing it.':'Only a ZIP code was given; assigned to the ZIP’s most populous tract.'}</div></dd>
 <dt>Campaign</dt><dd>${c.camp?esc(c.camp):'<span class="muted">None detected</span>'}</dd>
 <dt>Duplicate</dt><dd>${c.camp?'<div class="dup">Matches 142 other comments (form letter). Counted individually in Raw; collapsed in Reweighed.</div>':'<span class="muted">No duplicates</span>'}</dd>
 <dt>Name</dt><dd class="rmv">removed at ingest</dd><dt>Email / phone</dt><dd class="rmv">removed at ingest</dd><dt>Street address</dt><dd class="rmv">removed at ingest · tract kept</dd>
 <dt>Attachments</dt><dd>2 photos · faces and plates blurred · originals not stored</dd></dl></div></div></div></div>`}
 function lightbox(){const l=S.lightbox;return `<div class="lightbox" data-act="closelb"><div class="lbox" data-stop="1"><div class="lbimg"><span class="bz" style="position:absolute;left:12px;top:12px;font-size:12px;font-weight:600;background:rgba(27,27,27,.8);color:#fff;border-radius:2px;padding:2px 7px">blurred</span>resident photo · ${esc(l.lab)}</div><div class="lbcap"><span>${l.id?`Attached to <code style="font-family:var(--mono)">${l.id}</code> · `:''}Faces and plates blurred at ingest</span><span class="btnrow"><button class="btn" data-act="closelb">Close</button></span></div></div></div>`}

 stage.addEventListener('click',e=>{
  const a=e.target.closest('[data-act]');if(!a){if(S.menu){S.menu=null;render()}return}
  if(a.dataset.act==='closeinsp'||a.dataset.act==='closelb'){if(e.target.closest('[data-stop]')&&!e.target.closest('.colbtn,.btn'))return}
  const v=a.dataset.v,act=a.dataset.act;
  switch(act){
  case 'scheme':S.scheme=v;S.sbs=false;break;
  case 'sbs':S.sbs=!S.sbs;S.drawer=false;break;
  case 'menu':S.menu=S.menu===a.dataset.m?null:a.dataset.m;break;
  case 'pickitem':S.menu=null;S.state=null;setItem(a.dataset.id);S.selTract=null;S.tractDetail=null;S.cats={};S.mvOpen=-1;S.chatExtra=[];S.openCite=null;break;
  case 'loadregion':S.menu=null;S.tractDetail=null;S.selTract=null;{const r=S.saved[+a.dataset.i];S.region=r;S.regions=[r];S.compare=false;S.modal=true;S.right=true}break;
  case 'compare':S.menu=null;S.regions=S.saved.slice(0,2);S.region=S.regions[0];S.compare=true;S.modal=true;S.sbs=false;break;
  case 'draw':S.armed=!S.armed;S.sbs=false;S.hint=S.armed?'Click to place the first point':null;S.preDraw=false;break;
  case 'left':S.left=!S.left;break;case 'right':S.right=!S.right;break;
  case 'tab':if(v==='region'&&!S.region&&S.tab!=='region'){S.modal=true}else S.tab=v;S.right=true;break;
  case 'stance':S.stance[v]=S.stance[v]?0:1;break;
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
  case 'cite':S.openCite=S.openCite===a.dataset.id?null:a.dataset.id;if(S.tab!=='chat'){S.inspector=D.comments.find(c=>c.id===a.dataset.id)}break;
  case 'lightbox':S.lightbox={lab:a.dataset.lab,id:a.dataset.id};break;
  case 'closelb':S.lightbox=null;break;
  case 'ask':S.tab='chat';S.chatRegion=true;break;
  case 'rmchip':S.chatRegion=false;break;
  case 'copy':{e.preventDefault();const p=a.closest('.brief,.sec').querySelector('p');if(p&&navigator.clipboard)navigator.clipboard.writeText(p.innerText).catch(()=>{});a.textContent='Copied';setTimeout(()=>{a.textContent='Copy brief'},1500)}return;
  case 'save':if(S.region&&!S.saved.includes(S.region))S.saved.push(S.region);break;
  case 'rename':{const i=document.querySelector('.rname');if(i){i.focus();i.select()}return}
  case 'del':S.modal=false;S.tractDetail=null;S.region={name:'All of San José',poly:'city'};S.regions=[S.region];S.compare=false;S.tab='missing';break;
  case 'docksend':{const q=(document.querySelector('.dockin')||{}).value||'';S.tab='chat';S.chatRegion=!!S.region;if(q.trim())S.chatExtra.push(`<div class="mu">${esc(q.trim())}</div>`,`<div class="ma refuse"><div class="rt">No supporting comments</div><p style="margin:0">I couldn’t find comments that address this. Try a topic residents raised, such as ${CATS[0].n.toLowerCase()}.</p></div>`)}break;
  case 'untract':S.tractDetail=null;S.selTract=null;S.modal=!!S.region;break;
  case 'anmode':S.anMode=v;break;
  case 'closemodal':S.modal=false;break;
  case 'analytics':S.view='analytics';S.modal=false;break;
  case 'back':S.view='main';S.modal=true;break;
  case 'send':{const ta=document.querySelector('.cbox textarea');const q=ta.value.trim();if(!q)return;S.chatExtra.push(`<div class="mu">${esc(q)}</div>`,`<div class="ma refuse"><div class="rt">No supporting comments</div><p style="margin:0">I couldn’t find comments ${S.region&&S.chatRegion?' in the area you drew':''} that address this. Try a topic residents raised, such as ${CATS[0].n.toLowerCase()} or ${CATS[1].n.toLowerCase()}.</p></div>`)}break;
  }
  render();
 });
 stage.addEventListener('change',e=>{const a=e.target.dataset.actChange;if(a==='attr'){S.attr=e.target.value;render()}});
 stage.addEventListener('input',e=>{if(e.target.classList.contains('rname')&&S.region){S.region.name=e.target.value;const n=document.querySelector('.rhandle .nm');if(n)n.lastChild.textContent=e.target.value}});
 stage.addEventListener('mouseover',e=>{const df=e.target.closest('[data-def]');if(df){const r=df.getBoundingClientRect();srcTip.innerHTML=esc(df.dataset.def);srcTip.style.display='block';srcTip.style.left=r.left+'px';srcTip.style.top=(r.bottom+8)+'px';srcTip.dataset.fixed='1';return}const q=e.target.closest('[data-hover]');if(q&&maps[0]){maps[0].pulse(D.comments.find(c=>c.id===q.dataset.hover))}const s=e.target.closest('[data-src]');if(s){srcTip.innerHTML='Source: <code>'+esc(s.dataset.src)+'</code>';srcTip.style.display='block'}});
 stage.addEventListener('mousemove',e=>{if(srcTip.style.display==='block'&&!srcTip.dataset.fixed){srcTip.style.left=Math.min(innerWidth-290,e.clientX+12)+'px';srcTip.style.top=(e.clientY+16)+'px'}});
 stage.addEventListener('mouseout',e=>{const df=e.target.closest('[data-def]');if(df&&!df.contains(e.relatedTarget)){srcTip.style.display='none';delete srcTip.dataset.fixed;return}const q=e.target.closest('[data-hover]');if(q&&!q.contains(e.relatedTarget)&&maps[0]&&!S.pulseId)maps[0].pulse(null);const s=e.target.closest('[data-src]');if(s&&!s.contains(e.relatedTarget))srcTip.style.display='none'});
 addEventListener('keydown',e=>{if(e.key==='Escape'){S.armed=false;S.hint=null;S.inspector=null;S.lightbox=null;S.menu=null;render()}});
 render();
 if(S.srcDemo){const el=document.querySelector(S.srcDemo);if(el){const r=el.getBoundingClientRect();srcTip.innerHTML='Source: <code>'+esc(el.dataset.src)+'</code>';srcTip.style.display='block';srcTip.style.left=r.left+'px';srcTip.style.top=(r.bottom+6)+'px'}}
 return {S,render,maps:()=>maps};
}

/* ---------- pitch ---------- */
async function pitch(root,which){
 await load();
 const stage=document.createElement('div');stage.id='stage';stage.style.width='1920px';stage.style.height='1080px';root.appendChild(stage);
 const fit=()=>{const s=Math.min(innerWidth/1920,innerHeight/1080);stage.style.transform=`translate(${(innerWidth-1920*s)/2}px,${(innerHeight-1080*s)/2}px) scale(${s})`};fit();addEventListener('resize',fit);
 const f=fairness(D.tracts,'renter');
 const head=`<div style="height:96px;display:flex;align-items:flex-end;justify-content:space-between;padding:0 72px 20px"><div><div style="font-size:16px;color:#5C5C58;margin-bottom:4px">CityLens · San José</div><div style="font-size:28px;font-weight:500;letter-spacing:-.01em">${ITEM.title}</div></div><div style="font-size:16px;color:#5C5C58;text-align:right" class="num">${fmt(ITEM.total)} public comments · ${fmt(D.located)} located · ${D.tracts.length} census tracts</div></div>`;
 if(which==='A'){
  stage.innerHTML=head+`<div style="display:flex;gap:0;padding:0 72px;height:780px"><div style="width:1240px;display:flex;flex-direction:column;border:1px solid #E3E3DF;background:#fff"><div style="flex:1;display:flex;min-height:0"><div class="map" id="pa"><div class="mlabel" style="font-size:20px;padding:6px 14px">Raw <span>comment volume</span></div></div><div class="divider"></div><div class="map" id="pb"><div class="mlabel" style="font-size:20px;padding:6px 14px">Underheard <span>participation gap</span></div></div></div><div style="height:72px;border-top:1px solid #E3E3DF;display:grid;grid-template-columns:1fr 1px 1fr;align-items:center"><div style="padding:0 24px;display:flex;gap:16px;align-items:center;font-size:16px"><span style="font-weight:600">Comments per tract</span><div style="width:240px"><div class="ramp">${RAW.map((c,i)=>`<div style="background:${i?c:RAWZ};height:12px;box-shadow:inset 0 0 0 1px rgba(0,0,0,.05)"></div>`).join('')}</div><div class="rampl" style="font-size:13px"><span>0</span><span>1–4</span><span>5–9</span><span>10–17</span><span>18+</span></div></div></div><div style="height:40px;background:#E3E3DF"></div><div style="padding:0 24px;display:flex;gap:16px;align-items:center;font-size:16px"><span style="font-weight:600">Gap vs. population share</span><div style="width:240px"><div class="ramp">${GAPM.map((c,i)=>`<div style="height:12px;background:${i===4?`repeating-linear-gradient(45deg,${c} 0 3px,#7B62B8 3px 4.5px)`:c}"></div>`).join('')}</div><div class="rampl" style="font-size:13px"><span>at/above share</span><span>−30%</span><span>−55%</span><span>−80%</span><span>silent</span></div></div></div></div></div>
  <div style="flex:1;padding-left:56px;display:flex;flex-direction:column;justify-content:center;gap:56px"><div><div style="font-size:20px;color:#5C5C58">Statistical parity difference</div><div style="font-size:120px;font-weight:500;line-height:1;letter-spacing:-.03em;margin:8px 0 12px" class="num">−${Math.abs(f.spd).toFixed(2)}</div><div style="font-size:24px;line-height:1.35;text-wrap:pretty">Renter-majority tracts are ${Math.abs(Math.round(f.spd*100))} points less likely to be high-volume.</div></div><div><div style="font-size:20px;color:#5C5C58;display:flex;gap:12px;align-items:center">Disparate impact <span class="flag" style="font-size:16px;padding:2px 10px"><i style="width:9px;height:9px"></i>Below 0.8</span></div><div style="font-size:120px;font-weight:500;line-height:1;letter-spacing:-.03em;margin:8px 0 14px" class="num">${f.di.toFixed(2)}</div><div style="position:relative;height:56px"><div style="position:absolute;left:0;right:0;top:8px;height:10px;background:#EFEFEB"></div><div style="position:absolute;left:0;top:8px;height:10px;width:${f.di/1.2*100}%;background:#1B1B1B"></div><div style="position:absolute;left:${.8/1.2*100}%;top:0;height:28px;border-left:2px dashed #B7791F"></div><div style="position:absolute;left:${.8/1.2*100}%;top:32px;transform:translateX(-50%);font-size:16px;color:#6B4710;white-space:nowrap">four-fifths threshold</div></div></div></div></div>
  <div style="height:204px;display:flex;align-items:center;padding:0 72px"><div style="font-size:40px;font-weight:500;letter-spacing:-.015em;white-space:nowrap">Unweighted, the top issue was potholes. Population-weighted, it was the school crosswalk.</div></div>`;
  const a=new MapView(stage.querySelector('#pa'),{static:true,pad:30,padTop:30}),b=new MapView(stage.querySelector('#pb'),{static:true,pad:30,padTop:30});
  const all=()=>true;a.style({scheme:'raw',dotFilter:all});b.style({scheme:'gap',dotFilter:all});
 } else {
  const tr=regionTracts(EAST_REGION);const ids=new Set(tr.map(t=>t.id));const cs=D.comments.filter(c=>ids.has(c.tract));const pop=tr.reduce((s,t)=>s+t.pop,0);const rf=fairness(tr,'renter');const silent=tr.filter(t=>t.n===0||gapBin(t)>=3).sort((a,b)=>(b.exp-b.n)-(a.exp-a.n));const totExp=tr.reduce((s,t)=>s+t.exp,0);
  stage.innerHTML=head+`<div style="display:flex;gap:40px;padding:0 72px;height:920px;padding-bottom:64px"><div style="flex:1;border:1px solid #E3E3DF;position:relative;display:flex"><div class="map" id="pa"><div class="legend" style="width:300px"><div class="lt" style="font-size:14px">Participation gap vs. population share</div><div class="ramp">${GAPM.map((c,i)=>`<div style="height:12px;background:${i===4?`repeating-linear-gradient(45deg,${c} 0 3px,#7B62B8 3px 4.5px)`:c}"></div>`).join('')}</div><div class="rampl" style="font-size:12px"><span>at/above share</span><span>−30%</span><span>−55%</span><span>−80%</span><span>silent</span></div></div></div></div>
  <div style="width:720px;background:#fff;border:1px solid #E3E3DF;padding:32px 36px;display:flex;flex-direction:column;gap:26px;overflow:hidden">
  <div><div style="font-size:16px;color:#5C5C58;margin-bottom:4px">Region you drew</div><div style="font-size:36px;font-weight:500;letter-spacing:-.015em">East Side — Story Rd corridor</div><div style="display:flex;gap:24px;font-size:20px;color:#5C5C58;margin-top:8px" class="num"><span><b style="color:#1B1B1B;font-weight:600">${tr.length}</b> tracts</span><span><b style="color:#1B1B1B;font-weight:600">${fmt(pop)}</b> residents</span><span><b style="color:#1B1B1B;font-weight:600">${cs.length}</b> comments of ${Math.round(totExp)} expected</span></div></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">${rf.few?`<div class="toofew" style="grid-column:1/-1;font-size:18px">Too few tracts in each group to compare fairly</div>`:`<div class="tile"><div class="k" style="font-size:16px">Statistical parity difference</div><div class="v" style="font-size:48px">−${Math.abs(rf.spd).toFixed(2)}</div><div class="c" style="font-size:16px">Renter-majority tracts</div></div><div class="tile"><div class="k" style="font-size:16px;justify-content:space-between">Disparate impact<span class="flag" style="font-size:14px"><i></i>Below 0.8</span></div><div class="v" style="font-size:48px">${rf.di.toFixed(2)}</div><div class="c" style="font-size:16px">four-fifths threshold 0.8</div></div>`}</div>
  <div style="flex:1;min-height:0;display:flex;flex-direction:column"><div style="font-size:16px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:#5C5C58;margin-bottom:10px">Who we’re not hearing from</div><div class="silent" style="flex:1;overflow:hidden"><div class="cap" style="font-size:18px;padding:12px 16px">No comments located here — unknown, not absent.</div>${silent.slice(0,5).map(t=>`<div class="srow" style="padding:14px 16px;grid-template-columns:14px 1fr auto"><div class="sw" style="width:14px;height:14px;background:${t.n===0?`repeating-linear-gradient(45deg,${GAP[4]} 0 3px,#8A74C4 3px 4.5px)`:GAPM[gapBin(t)]}"></div><div><div style="font-weight:600;font-size:20px">${t.nbhd}</div><div class="tid" style="font-size:14px">Tract ${t.id}</div></div><div class="nums" style="font-size:16px"><b>${fmt(t.pop)}</b> residents<br>${t.n} of ${Math.round(t.exp)} expected</div><div class="chips" style="gap:8px">${`<span class="acs" style="font-size:15px;height:28px;padding:0 10px">${pct(t.renter)} renters</span><span class="acs" style="font-size:15px;height:28px;padding:0 10px">${pct(t.lep)} limited-English</span><span class="acs" style="font-size:15px;height:28px;padding:0 10px">${incLabel(t)}</span>`}</div></div>`).join('')}</div></div></div></div>`;
  const m=new MapView(stage.querySelector('#pa'),{static:true,focus:[-121.93,37.28,-121.75,37.40],pad:20});
  const inR=new Set(tr.map(t=>t.id));m.style({scheme:'gap',polys:[EAST_REGION],dotFilter:()=>true});m.regions([{poly:EAST_REGION}]);
  const pts=EAST_REGION.map(p=>m.screen(p));const x=Math.max(...pts.map(p=>p[0])),y=Math.min(...pts.map(p=>p[1]));
  const h=document.createElement('div');h.className='rhandle';h.style.cssText=`left:${x-120}px;top:${y-50}px;font-size:16px;padding:6px 8px`;h.innerHTML=`<span class="nm" style="font-size:16px"><i style="width:10px;height:10px"></i>East Side — Story Rd corridor</span>`;m.el.appendChild(h);
 }
}
window.CVM={mount,pitch,load};
})();
