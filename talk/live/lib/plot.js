// Tiny canvas plotting kit for NLD slide embeds. Logical canvas 1600 x 700.
var W=1600,H=700,cv=document.createElement('canvas'),g=cv.getContext('2d'),S=1,OX=0,OY=0;
document.body.style.cssText='margin:0;overflow:hidden;background:#F7F6F2';document.body.appendChild(cv);
var INK='#132433',REF='#8A8578',PAP='#F7F6F2',C=['#1F5A85','#B4622A','#588A75','#CA863E','#774860'];
var SANS='"IBM Plex Sans",Helvetica,Arial,sans-serif',MATH='"Latin Modern Math","CMU Serif","STIX Two Math","Cambria Math","Times New Roman",serif';
function rs(){var d=devicePixelRatio||1,w=innerWidth,h=innerHeight;cv.width=w*d;cv.height=h*d;cv.style.width=w+'px';cv.style.height=h+'px';S=Math.min(w/W,h/H)*d;OX=(w*d-W*S)/2;OY=(h*d-H*S)/2}
addEventListener('resize',rs);rs();
function b64(s,sc,o,t){var b=atob(s),n=b.length,u=new Uint8Array(n);for(var i=0;i<n;i++)u[i]=b.charCodeAt(i);
var a=t==8?new Int8Array(u.buffer):new Int16Array(u.buffer),r=new Float64Array(a.length);for(i=0;i<a.length;i++)r[i]=a[i]*sc+(o||0);return r}
function mu(a,m){for(var i=0;i<a.length;i++){var x=a[i]/127;a[i]=m*Math.sign(x)*(Math.pow(256,Math.abs(x))-1)/255}return a}
// mini TeX: $..$ math with ^{} _{} ; letters italic, digits upright
function tx(s,x,y,o){o=o||{};var fs=o.s||28,al=o.a||'l',col=o.c||INK,rot=o.r||0,parts=[],m=0,i,ch,cs=Array.from(s);
function push(t,mt,lv){parts.push([t,mt,lv])}
for(i=0;i<cs.length;i++){ch=cs[i];if(ch=='$'){m=!m;continue}
if(m&&(ch=='^'||ch=='_')){var lv=ch=='^'?1:-1,t='';if(cs[i+1]=='{'){i+=2;while(cs[i]!='}')t+=cs[i++]}else t=cs[++i];push(t,1,lv);continue}
if(/[\u0300-\u036f]/.test(ch)&&parts.length){parts[parts.length-1][0]+=ch;continue}push(ch,m,0)}
g.save();g.translate(x,y);if(rot)g.rotate(rot);g.fillStyle=col;g.textBaseline='alphabetic';
function fnt(p){var z=p[2]?fs*.68:fs;if(!p[1])return (o.w||'')+' '+z+'px '+SANS;return(/[A-Za-zα-ω]/.test(p[0])&&!o.up?'italic ':'')+z+'px '+MATH}
var w=0,ws=[];for(i=0;i<parts.length;i++){g.font=fnt(parts[i]);ws.push(g.measureText(parts[i][0]).width);w+=ws[i]}
var cx=al=='c'?-w/2:al=='r'?-w:0;for(i=0;i<parts.length;i++){g.font=fnt(parts[i]);g.fillText(parts[i][0],cx,parts[i][2]>0?-.42*fs:parts[i][2]<0?.22*fs:0);cx+=ws[i]}
g.restore();return w}
function Ax(x,y,w,h,o){var a=this;a.x=x;a.y=y;a.w=w;a.h=h;a.o=o;a.xl=o.xl||[0,1];a.yl=o.yl||[0,1];return a}
Ax.prototype={
X:function(v){var a=this.xl,lg=this.o.xlog;if(lg){v=Math.log10(v);return this.x+(v-Math.log10(a[0]))/(Math.log10(a[1])-Math.log10(a[0]))*this.w}return this.x+(v-a[0])/(a[1]-a[0])*this.w},
Y:function(v){var a=this.yl,lg=this.o.ylog;if(lg){v=Math.log10(Math.max(v,1e-300));return this.y+this.h-(v-Math.log10(a[0]))/(Math.log10(a[1])-Math.log10(a[0]))*this.h}return this.y+this.h-(v-a[0])/(a[1]-a[0])*this.h},
frame:function(){var a=this,o=a.o;g.fillStyle=o.bg||'#fff';g.fillRect(a.x,a.y,a.w,a.h);g.strokeStyle=INK;g.lineWidth=1.6;g.strokeRect(a.x,a.y,a.w,a.h);
(o.xt||[]).forEach(function(t){var p=a.X(t[0]);g.beginPath();g.moveTo(p,a.y+a.h);g.lineTo(p,a.y+a.h-9);g.stroke();tx(t[1],p,a.y+a.h+32,{a:'c',s:24})});
(o.yt||[]).forEach(function(t){var p=a.Y(t[0]);g.beginPath();g.moveTo(a.x,p);g.lineTo(a.x+9,p);g.stroke();tx(t[1],a.x-8,p+8,{a:'r',s:24})});
if(o.xlab)tx(o.xlab,a.x+a.w/2,a.y+a.h+66,{a:'c'});if(o.ylab)tx(o.ylab,a.x-(o.yoff||62),a.y+a.h/2,{a:'c',r:-Math.PI/2});
if(o.title)tx(o.title,a.x+a.w/2,a.y-16,{a:'c',s:o.ts||27})},
clip:function(f){g.save();g.beginPath();g.rect(this.x,this.y,this.w,this.h);g.clip();f();g.restore()},
line:function(xs,ys,st,n0,n1){var a=this;st=st||{};n0=n0||0;n1=n1==null?xs.length:n1;a.clip(function(){g.beginPath();g.strokeStyle=st.c||INK;g.lineWidth=st.w||2.4;g.setLineDash(st.d||[]);g.globalAlpha=st.al||1;
for(var i=n0,pp,qq;i<n1;i++){var p=a.X(xs[i]),q=a.Y(ys[i]);i==n0?g.moveTo(p,q):st.sm?g.quadraticCurveTo(pp,qq,(p+pp)/2,(q+qq)/2):g.lineTo(p,q);pp=p;qq=q}g.stroke();g.setLineDash([]);g.globalAlpha=1})},
band:function(xs,lo,hi,c,al,n0,n1){var a=this;n0=n0||0;n1=n1==null?xs.length:n1;a.clip(function(){g.beginPath();g.fillStyle=c;g.globalAlpha=al||.3;for(var i=n0;i<n1;i++)g.lineTo(a.X(xs[i]),a.Y(hi[i]));for(i=n1-1;i>=n0;i--)g.lineTo(a.X(xs[i]),a.Y(lo[i]));g.fill();g.globalAlpha=1})},
dot:function(x,y,c,r,open){var a=this;a.clip(function(){g.beginPath();g.arc(a.X(x),a.Y(y),r||7,0,7);if(open){g.strokeStyle=c;g.lineWidth=2.4;g.fillStyle='#fff';g.fill();g.stroke()}else{g.fillStyle=c;g.fill()}})},
vl:function(x,c,d,w){this.line([x,x],this.yl,{c:c||REF,d:d||[6,6],w:w||1.6})},
hl:function(y,c,d,w){this.line([this.xl[0],this.xl[1]],[y,y],{c:c||REF,d:d||[],w:w||1.4})}};
function leg(x,y,items,s){s=s||24;items.forEach(function(it,i){var yy=y+i*s*1.4;g.strokeStyle=it[1];g.lineWidth=it[3]||3;g.setLineDash(it[2]||[]);g.beginPath();g.moveTo(x,yy-s*.32);g.lineTo(x+44,yy-s*.32);g.stroke();g.setLineDash([]);tx(it[0],x+54,yy,{s:s})})}
function run(T,draw){var t0=null,FP=location.hash.slice(3);function f(t){if(FP)t=+FP*T*1000,t0=0;else if(t0==null)t0=t;var ph=((t-t0)/1000%T)/T;g.setTransform(1,0,0,1,0,0);g.fillStyle=PAP;g.fillRect(0,0,cv.width,cv.height);g.setTransform(S,0,0,S,OX,OY);draw(ph);if(!FP)requestAnimationFrame(f)}requestAnimationFrame(f)}
function lin(a,b,n){for(var r=[],i=0;i<n;i++)r.push(a+(b-a)*i/(n-1));return r}
function ease(p){return p<.5?2*p*p:1-2*(1-p)*(1-p)}
