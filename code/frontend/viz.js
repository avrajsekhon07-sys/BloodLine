/* BloodLine visual kit: dependency-free SVG components (droplet, gauge, donut, area, bars, sparkline) + tooltip + count-up. */
const V=(()=>{let u=0,tip;const RM=matchMedia("(prefers-reduced-motion:reduce)").matches,
PAL=["#D5708B","#B9486A","#E9A8B8","#8B6FD0","#5B9BE6","#4FB3BF","#E0B04F","#5FBF85"],col={HIGH:"var(--crit)",MODERATE:"var(--warn)",LOW:"var(--ok)"};
const T=()=>tip||(tip=document.body.appendChild(Object.assign(document.createElement("div"),{className:"tip"})));
const show=(e,h)=>{const t=T();t.innerHTML=h;t.style.opacity=1;t.style.left=Math.min(e.clientX+14,innerWidth-t.offsetWidth-8)+"px";t.style.top=Math.min(e.clientY+14,innerHeight-t.offsetHeight-8)+"px"},hide=()=>tip&&(tip.style.opacity=0);
const tipOn=(n,h)=>{n.addEventListener("mousemove",e=>show(e,typeof h=="function"?h():h));n.addEventListener("mouseleave",hide)};
function count(root){root.querySelectorAll("[data-count]").forEach(el=>{const to=+el.dataset.count,d=+(el.dataset.dec||0);if(RM){el.textContent=to.toFixed(d);return}
 const t0=performance.now(),f=t=>{const k=Math.min((t-t0)/900,1);el.textContent=(to*(1-Math.pow(1-k,3))).toFixed(d);if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)})}
const DP="M50 6C50 6 12 46 12 74a38 38 0 0 0 76 0C88 46 50 6 50 6Z";
function droplet(level,color,label){const id="dp"+u++,y=(1-Math.max(.04,Math.min(1,level)))*100;
 return `<svg viewBox="0 0 100 120" class="dropsvg" aria-hidden="true"><defs><clipPath id="${id}"><path d="${DP}"/></clipPath><linearGradient id="${id}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".98"/><stop offset="1" stop-color="${color}" stop-opacity=".6"/></linearGradient></defs>
 <path d="${DP}" fill="rgba(128,128,140,.12)" stroke="rgba(128,128,140,.4)" stroke-width="1.5"/><g clip-path="url(#${id})"><rect class="liq" x="0" y="6" width="100" height="108" fill="url(#${id}g)" style="--y:${y}%"/><ellipse cx="34" cy="72" rx="5" ry="14" fill="#fff" opacity=".18" transform="rotate(18 34 72)"/></g>
 <text x="50" y="84" text-anchor="middle" font-size="22" font-weight="700" fill="#fff" style="paint-order:stroke;stroke:rgba(0,0,0,.4);stroke-width:3">${label}</text></svg>`}
function gauge(frac,{label="",text="",redHigh=true}={}){frac=Math.max(0,Math.min(1,frac));let s="";const N=36;
 for(let i=0;i<N;i++){const k=i/(N-1),a=Math.PI*(1+k),r0=60,r1=r0+(i%3?15:22),h=redHigh?120-k*120:k*120;
  s+=`<line class="tk" style="animation-delay:${i*16}ms" x1="${(100+r0*Math.cos(a)).toFixed(1)}" y1="${(100+r0*Math.sin(a)).toFixed(1)}" x2="${(100+r1*Math.cos(a)).toFixed(1)}" y2="${(100+r1*Math.sin(a)).toFixed(1)}" stroke="hsl(${h} 78% 58%)" stroke-width="3.2" stroke-linecap="round" opacity="${k<=frac+1e-9?1:.16}"/>`}
 return `<svg viewBox="0 0 200 116" class="gauge" role="img" aria-label="${label} ${text}">${s}<text x="100" y="94" text-anchor="middle" class="gv">${text}</text><text x="100" y="111" text-anchor="middle" class="gl">${label}</text></svg>`}
function donut(el,items,{center="Total"}={}){const tot=items.reduce((a,b)=>a+b.value,0)||1,R=70,C=2*Math.PI*R;let off=0;
 el.innerHTML=`<svg viewBox="0 0 200 200" class="donut"><g transform="rotate(-90 100 100)">${items.map((it,i)=>{const len=Math.max(it.value/tot*C-2,0),s=`<circle class="seg" data-i="${i}" cx="100" cy="100" r="${R}" fill="none" stroke="${it.color}" stroke-width="24" stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-off}"/>`;off+=it.value/tot*C;return s}).join("")}</g><text x="100" y="100" text-anchor="middle" class="dv">${tot}</text><text x="100" y="120" text-anchor="middle" class="dl">${center}</text></svg>
 <div class="legend">${items.map((it,i)=>`<span data-i="${i}"><i style="background:${it.color}"></i>${it.label}<b>${it.value}</b></span>`).join("")}</div>`;
 const dv=el.querySelector(".dv"),dl=el.querySelector(".dl"),segs=el.querySelectorAll(".seg");
 el.querySelectorAll("[data-i]").forEach(n=>{n.onmouseenter=()=>{const it=items[n.dataset.i];dv.textContent=it.value;dl.textContent=it.label+" · "+Math.round(it.value/tot*100)+"%";segs.forEach(s=>s.classList.toggle("dim",s.dataset.i!=n.dataset.i))};
  n.onmouseleave=()=>{dv.textContent=tot;dl.textContent=center;segs.forEach(s=>s.classList.remove("dim"))}})}
function area(el,{series,height=240}){const W=720,H=height,L=36,B=24,Tp=10,R=10,xs=series[0].data.map(d=>d.x),n=xs.length,id="ar"+u++,
 mx=Math.max(1,...series.flatMap(s=>s.data.map(d=>d.y).filter(v=>v!=null)))*1.12,X=i=>L+i/(n-1||1)*(W-L-R),Y=v=>Tp+(1-v/mx)*(H-Tp-B);
 const path=s=>{let d="",o=false;s.data.forEach((p,i)=>{if(p.y==null){o=false;return}d+=(o?"L":"M")+X(i).toFixed(1)+" "+Y(p.y).toFixed(1);o=true});return d};
 const fill=s=>{const ix=s.data.map((p,i)=>p.y==null?-1:i).filter(i=>i>=0);return ix.length?path(s)+`L${X(ix[ix.length-1]).toFixed(1)} ${Y(0)}L${X(ix[0]).toFixed(1)} ${Y(0)}Z`:""};
 const grid=[0,.25,.5,.75,1].map(k=>`<line x1="${L}" x2="${W-R}" y1="${Y(mx*k/1.12)}" y2="${Y(mx*k/1.12)}" stroke="var(--ln)" stroke-dasharray="3 5"/><text x="${L-6}" y="${Y(mx*k/1.12)+4}" text-anchor="end" font-size="10" fill="var(--mut)">${Math.round(mx*k/1.12)}</text>`).join("");
 const lab=[0,.33,.66,1].map(k=>{const i=Math.round(k*(n-1));return `<text x="${X(i)}" y="${H-6}" text-anchor="${k==1?"end":k==0?"start":"middle"}" font-size="10" fill="var(--mut)">${xs[i]}</text>`}).join("");
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%" class="area">${`<defs>${series.map((s,i)=>`<linearGradient id="${id}${i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.color}" stop-opacity=".35"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient>`).join("")}</defs>`}${grid}${lab}
 ${series.map((s,i)=>`${s.fill?`<path d="${fill(s)}" fill="url(#${id}${i})"/>`:""}<path class="ln" pathLength="1" d="${path(s)}" fill="none" stroke="${s.color}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" ${s.dash?`stroke-dasharray="${s.dash}"`:""}/>`).join("")}
 <line id="${id}x" y1="${Tp}" y2="${H-B}" stroke="var(--mut)" stroke-dasharray="2 4" opacity="0"/>${series.map((s,i)=>`<circle id="${id}c${i}" r="4.5" fill="${s.color}" stroke="var(--s)" stroke-width="2" opacity="0"/>`).join("")}<rect x="${L}" y="0" width="${W-L-R}" height="${H}" fill="transparent" id="${id}o"/></svg>`;
 const svg=el.querySelector("svg"),o=svg.querySelector("#"+id+"o"),xl=svg.querySelector("#"+id+"x");
 o.addEventListener("mousemove",e=>{const r=svg.getBoundingClientRect(),i=Math.max(0,Math.min(n-1,Math.round(((e.clientX-r.left)/r.width*W-L)/(W-L-R)*(n-1))));xl.setAttribute("x1",X(i));xl.setAttribute("x2",X(i));xl.style.opacity=1;
  series.forEach((s,k)=>{const c=svg.querySelector("#"+id+"c"+k),y=s.data[i].y;if(y==null)c.style.opacity=0;else{c.setAttribute("cx",X(i));c.setAttribute("cy",Y(y));c.style.opacity=1}});
  show(e,`<b>${xs[i]}</b>`+series.filter(s=>s.data[i].y!=null).map(s=>`<div><i style="background:${s.color}"></i>${s.name}: <b>${s.data[i].y}</b></div>`).join(""))});
 o.addEventListener("mouseleave",()=>{hide();xl.style.opacity=0;svg.querySelectorAll("circle").forEach(c=>c.style.opacity=0)})}
function bars(el,{groups,height=210}){const W=520,H=height,L=30,B=24,Tp=8,mx=Math.max(1,...groups.flatMap(g=>g.bars.map(b=>b.v||0)))*1.15,gw=(W-L)/groups.length,id="bh"+u++;let k=0;
 const Y=v=>Tp+(1-v/mx)*(H-Tp-B);
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%"><defs><pattern id="${id}" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="3" height="7" fill="#fff" opacity=".4"/></pattern></defs>
 ${[0,.5,1].map(f=>`<line x1="${L}" x2="${W}" y1="${Y(mx*f/1.15)}" y2="${Y(mx*f/1.15)}" stroke="var(--ln)" stroke-dasharray="3 5"/><text x="${L-5}" y="${Y(mx*f/1.15)+4}" text-anchor="end" font-size="10" fill="var(--mut)">${+(mx*f/1.15).toFixed(1)}</text>`).join("")}
 ${groups.map((g,gi)=>{const bw=Math.min(26,(gw-14)/g.bars.length),x0=L+gi*gw+(gw-bw*g.bars.length)/2;return g.bars.map((b,bi)=>{const x=x0+bi*bw,h=Math.max(0,(b.v||0)/mx*(H-Tp-B)),y=H-B-h,t=`<b>${g.label}</b><div>${b.name}: <b>${b.v??"-"}</b></div>`,i=k++;
  return `<g data-t='${t.replace(/'/g,"&#39;")}'><rect class="bar" style="--i:${i}" x="${x+1}" y="${y}" width="${bw-2}" height="${h}" rx="4" fill="${b.color}"/>${b.hatch?`<rect class="bar" style="--i:${i}" x="${x+1}" y="${y}" width="${bw-2}" height="${h}" rx="4" fill="url(#${id})"/>`:""}</g>`}).join("")+`<text x="${L+gi*gw+gw/2}" y="${H-7}" text-anchor="middle" font-size="10" fill="var(--mut)">${g.label}</text>`}).join("")}</svg>`;
 el.querySelectorAll("[data-t]").forEach(n=>tipOn(n,n.dataset.t))}
function spark(v,color="var(--pri)"){if(v.length<2)return"";const mx=Math.max(...v),mn=Math.min(...v),p=v.map((y,i)=>`${i/(v.length-1)*100},${26-(y-mn)/(mx-mn||1)*22}`).join(" ");
 return `<svg viewBox="0 0 100 30" class="spark" preserveAspectRatio="none"><polyline points="${p}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>`}
return {count,droplet,gauge,donut,area,bars,spark,tipOn,PAL,col}})();
