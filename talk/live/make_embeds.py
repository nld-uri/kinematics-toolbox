"""Browser-native versions of the kinematics talk animations (one <x-embed> page each).
Data computed with the toolbox exactly as kinematics-toolbox/python/animations.py does."""
import os, sys
import numpy as np
from scipy import signal as sg
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'python'))
from embedkit import e16, js, build
import base64
import kinematics as kin
import bench
import bench_delay
OUT = os.path.join(HERE, 'embeds'); os.makedirs(OUT, exist_ok=True)
CM = dict(truth="#8A8578", spec="#B4622A", whit="#1F5A85", tv="#588A75", ks="#132433", ksbar="#8FA3B0", acc="#774860")


def e8(x, amp):
    """plain int8 of x scaled so |x|<=amp maps to 127; decode with b64(s, amp/127, 0, 8)."""
    q = np.clip(np.round(np.asarray(x, float)/amp*127), -127, 127).astype('i1')
    return base64.b64encode(q.tobytes()).decode()


def illposed():
    t, dt, X, V, A = bench.duffing()
    fs = 1/dt
    f, Px = sg.welch(X, fs=fs, nperseg=1024)
    f, Px = f[1:], Px[1:]
    noise = (0.01*X.std())**2*2*dt
    D = dict(lf=e16(np.log10(f), 1e-4), lp=e16(np.log10(Px), 1e-3), ln=float(np.log10(noise)))
    code = f"""var D={js(D)},CM={js(CM)},F=b64(D.lf,1e-4).map(function(v){{return Math.pow(10,v)}}),LP=b64(D.lp,1e-3),nf=F.length,PI2=2*Math.PI,
fg=lin(-1,3,120).map(function(v){{return Math.pow(10,v)}});
var a1=new Ax(150,70,560,520,{{xl:[.1,1000],yl:[1e-7,1e7],xlog:1,ylog:1,xt:[[.1,'$10^{{−1}}$'],[1,'$10^{{0}}$'],[10,'$10^{{1}}$'],[100,'$10^{{2}}$'],[1000,'$10^{{3}}$']],yt:[[1e-6,'$10^{{−6}}$'],[1e-3,'$10^{{−3}}$'],[1,'$10^{{0}}$'],[1e3,'$10^{{3}}$'],[1e6,'$10^{{6}}$']],xlab:'frequency (Hz)',ylab:'noise gain $ω^{{n}}$',yoff:84}});
var a2=new Ax(930,70,630,520,{{xl:[F[0],F[nf-1]],yl:[1e-22,1e8],xlog:1,ylog:1,xt:[[10,'$10^{{1}}$'],[100,'$10^{{2}}$'],[1000,'$10^{{3}}$']],yt:[[1e-20,'$10^{{−20}}$'],[1e-12,'$10^{{−12}}$'],[1e-4,'$10^{{−4}}$'],[1e4,'$10^{{4}}$']],xlab:'frequency (Hz)',ylab:'PSD of the $n$th derivative',yoff:96,title:'where noise exceeds signal, the estimate is noise',ts:26}});
run(16,function(p){{var n=p<.5?-2+8*p:6-8*p,wd=n>.05?'derivatives':n<-.05?'integrals':'identity';
a1.frame();[-2,-1,1,2].forEach(function(k){{a1.line(fg,fg.map(function(f){{return Math.pow(PI2*f,k)}}),{{c:REF,w:1.4,d:[3,5]}})}});a1.hl(1,REF);
a1.line(fg,fg.map(function(f){{return Math.pow(PI2*f,n)}}),{{c:CM.spec,w:4}});
tx('derivatives: gain grows with $ω$',a1.x+16,a1.y+40,{{s:24,c:REF}});tx('integrals: gain grows as $ω→$0',a1.x+16,a1.y+a1.h-18,{{s:24,c:REF}});
tx('$n=$'+(n<0?'−':'+')+Math.abs(n).toFixed(2)+' ('+wd+')',a1.x+a1.w/2,a1.y-18,{{a:'c',s:30}});
var S=[],N=[];for(var i=0;i<nf;i++){{var w2=2*n*Math.log10(PI2*F[i]);S.push(Math.pow(10,LP[i]+w2));N.push(Math.pow(10,D.ln+w2))}}
a2.frame();a2.clip(function(){{g.fillStyle='rgba(180,98,42,.12)';for(var i=0,st=-1;i<=nf;i++){{var on=i<nf&&N[i]>S[i];if(on&&st<0)st=i;if(!on&&st>=0){{var x0=a2.X(F[st]),x1=a2.X(F[Math.min(i,nf-1)]);g.fillRect(x0,a2.y,x1-x0,a2.h);st=-1}}}}}});
a2.line(F,S,{{c:CM.truth,w:3,d:[10,7]}});a2.line(F,N,{{c:CM.spec,w:3}});
leg(a2.x+20,a2.y+40,[['signal',CM.truth,[10,7]],['noise (1% white on position)',CM.spec]])}});"""
    build('illposed', code, OUT)


def knob():
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(1)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    grid = np.geomspace(20, 600, 90)
    est = [kin.diff_whittaker(xn, dt, order=2, fc=fc) for fc in grid]
    err = np.array([bench.relerr(e, A) for e in est])
    i0 = int(np.argmin(err))
    sel = np.unique(np.r_[np.round(np.linspace(0, 89, 40)).astype(int), i0])
    j0 = int(np.where(sel == i0)[0][0])
    win = np.where((t > 0.30) & (t < 0.42))[0][::2]
    lim = 1.35*np.abs(A[win]).max()
    Es = np.concatenate([np.clip(est[k][win], -lim, lim) for k in sel])
    D = dict(t0=float(t[win][0]), dt=float(2*dt), m=len(win), A=e8(A[win], lim), E=e8(Es, lim), lim=lim,
             g=np.round(grid, 3).tolist(), er=np.round(err, 3).tolist(), sel=sel.tolist(), j0=j0)
    code = f"""var D={js(D)},CM={js(CM)},m=D.m,L=D.lim,AA=b64(D.A,L/127,0,8),EE=b64(D.E,L/127,0,8),tw=lin(D.t0,D.t0+(m-1)*D.dt,m),ns=D.sel.length;
var a1=new Ax(140,70,820,520,{{xl:[tw[0],tw[m-1]],yl:[-L,L],xt:[[.32,'0.32'],[.34,'0.34'],[.36,'0.36'],[.38,'0.38'],[.4,'0.40']],yt:[[-10,'−10'],[0,'0'],[10,'10']],xlab:'$t$ (s)',ylab:'$ẍ$ (m/s$^{{2}}$)',yoff:66}});
var a2=new Ax(1160,70,400,520,{{xl:[20,600],yl:[2,200],xlog:1,ylog:1,xt:[[30,'30'],[100,'100'],[300,'300']],yt:[[3,'3'],[10,'10'],[30,'30'],[100,'100']],xlab:'cutoff $f_{{c}}$ (Hz)',ylab:'acceleration error (%)',yoff:64,title:'one knob, one optimum',ts:26}});
run(14,function(p){{var k=Math.round(p<.5?2*p*(ns-1):(ns-1)+(D.j0-(ns-1))*ease(2*p-1)),i=D.sel[k],f=D.g[i],e=D.er[i];
a1.frame();a1.line(tw,AA,{{c:CM.truth,w:4,d:[12,8]}});a1.line(tw,EE.slice(k*m,k*m+m),{{c:CM.whit,w:2.4}});
leg(a1.x+a1.w-440,a1.y+40,[['true acceleration',CM.truth,[12,8]],['Whittaker estimate',CM.whit]]);
tx('1% noisy position, $f_{{c}}=$'+Math.round(f)+' Hz: error '+e.toFixed(1)+'%',a1.x+a1.w/2,a1.y-18,{{a:'c',s:30}});
a2.frame();a2.vl(D.g[D.sel[D.j0]],REF,[3,5]);a2.line(D.g,D.er,{{c:CM.whit,w:3}});a2.dot(f,e,CM.spec,10);
tx('too smooth: bias',a2.x+14,a2.y+36,{{s:24,c:REF}});tx('too rough: noise',a2.x+a2.w-14,a2.y+a2.h-18,{{s:24,c:REF,a:'r'}})}});"""
    build('knob', code, OUT)


def fusion():
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(0)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    an = bench.noisy_acceleration(A, dt, 2.0, rng)
    rs = kin.kinsmooth(t, x=xn, a=an, nstate=4, bias=True)
    rf = kin.kinsmooth(t, x=xn, a=an, nstate=4, bias=True, causal=True, q=rs['q'])
    vs = V.std()
    ef, es = (rf['v'] - V)/vs, (rs['v'] - V)/vs
    sf, ss = rf['std'][:, 1]/vs, rs['std'][:, 1]/vs
    pf, ps = bench.relerr(rf['v'], V), bench.relerr(rs['v'], V)
    print(f'fusion: causal {pf:.2f} %, smoother {ps:.2f} %')
    k = slice(0, len(t), 6)
    D = dict(T=float(t[-1]), n=len(t[k]), x=e8(xn[k]/X.std(), 2.6), a=e8(an[k]/A.std(), 2.6),
             ef=e8(ef[k], .06), es=e8(es[k], .06), sf=e8(2*sf[k], .06), ss=e8(2*ss[k], .06), pf=round(pf, 2), ps=round(ps, 2))
    code = f"""var D={js(D)},CM={js(CM)},n=D.n,tt=lin(0,D.T,n),XS=b64(D.x,2.6/127,0,8),AS=b64(D.a,2.6/127,0,8).map(function(v){{return v-3.2}}),
EF=b64(D.ef,.06/127,0,8),ES=b64(D.es,.06/127,0,8),SF=b64(D.sf,.06/127,0,8),SS=b64(D.ss,.06/127,0,8);
function neg(a){{return a.map(function(v){{return-v}})}}
var a0=new Ax(150,70,1410,150,{{xl:[0,D.T],yl:[-6,2.6]}}),
a1=new Ax(150,280,1410,300,{{xl:[0,D.T],yl:[-.06,.06],xt:[[0,'0'],[.5,'0.5'],[1,'1'],[1.5,'1.5'],[2,'2'],[2.5,'2.5']],yt:[[-.05,'−0.05'],[0,'0'],[.05,'0.05']],xlab:'$t$ (s)',ylab:'velocity error$/σ$',yoff:110}});
run(16,function(p){{a0.frame();a0.line(tt,XS,{{c:CM.whit,w:1.2}});a0.line(tt,AS,{{c:CM.acc,w:1.2}});
leg(a0.x+330,a0.y-22,[['displacement, 1% noise',CM.whit]]);leg(a0.x+800,a0.y-22,[['accelerometer, noise and drift',CM.acc]]);
a1.frame();a1.hl(0);var lab;
if(p<.5){{var m=Math.max(2,Math.round(2*p*n));a1.band(tt,neg(SF),SF,CM.ksbar,.45,0,m);a1.line(tt,EF,{{c:CM.spec,w:1.4}},0,m);a1.vl(tt[m-1],INK,[],2.4);
lab='forward Kalman filter (causal): error '+D.pf.toFixed(2)+'% rms, band ±2σ'}}
else{{var b=n-Math.round((2*p-1)*n),SG=Array.from(SF.slice(0,b)).concat(Array.from(SS.slice(b)));
a1.band(tt,neg(SG),SG,CM.ksbar,.45);a1.line(tt,EF,{{c:CM.spec,w:1.4}},0,Math.min(b+1,n));a1.line(tt,ES,{{c:CM.ks,w:1.4}},Math.max(b,0));if(b>0)a1.vl(tt[Math.min(b,n-1)],INK,[],2.4);
lab='backward RTS smoother: error '+D.ps.toFixed(2)+'% rms, band shrinks'}}
g.fillStyle='rgba(255,255,255,.88)';g.fillRect(a1.x+8,a1.y+8,700,44);tx(lab,a1.x+18,a1.y+40,{{s:27}})}});"""
    build('fusion', code, OUT)


def edges():
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(2)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    vsp = kin.diff_spectral(xn, dt, order=1, fc=120)
    vks = kin.kinsmooth(t, x=xn, nstate=4)['v']
    T = t[-1] + dt
    sx, sv = X.std(), V.std()
    e = t > T - 0.13; b = t < 0.17; w = t > T - 0.15
    print('edges: spectral end err %.2f sigma, smoother %.3f' % (np.abs(vsp - V)[-400:].max()/sv, np.abs(vks - V)[-400:].max()/sv))
    D = dict(T=float(T), dt=float(dt), te=float(t[e][0]), ne=int(e.sum()), nb=int(b.sum()), tw=float(t[w][0]), nw=int(w.sum()),
             xe=e8(X[e]/sx, 3), xb=e8(X[b]/sx, 3), v=e8(V[w]/sv, 3.2), vs=e8(vsp[w]/sv, 3.2), vk=e8(vks[w]/sv, 3.2))
    code = f"""var D={js(D)},CM={js(CM)},T=D.T,h=.12,XE=b64(D.xe,3/127,0,8),XB=b64(D.xb,3/127,0,8),VV=b64(D.v,3.2/127,0,8),VS=b64(D.vs,3.2/127,0,8),VK=b64(D.vk,3.2/127,0,8),
te=lin(D.te,D.te+(D.ne-1)*D.dt,D.ne),tb=lin(0,(D.nb-1)*D.dt,D.nb),tw=lin(D.tw,D.tw+(D.nw-1)*D.dt,D.nw);
var a1=new Ax(140,70,620,520,{{xl:[T-h,T+h],yl:[-2.6,2.6],xt:[[2.9,'2.90'],[2.95,'2.95'],[3,'3.00'],[3.05,'3.05'],[3.1,'3.10']],yt:[[-2,'−2'],[-1,'−1'],[0,'0'],[1,'1'],[2,'2']],xlab:'$t$ (s)',ylab:'$x/σ_{{x}}$',yoff:56,title:'the FFT sees the record as periodic',ts:26}}),
a2=new Ax(940,70,620,520,{{xl:[T-.15,T],yl:[-3.2,3.2],xt:[[2.875,'2.875'],[2.925,'2.925'],[2.975,'2.975']],yt:[[-3,'−3'],[-2,'−2'],[-1,'−1'],[0,'0'],[1,'1'],[2,'2'],[3,'3']],xlab:'$t$ (s)',ylab:'$ẋ/σ_{{ẋ}}$',yoff:56,title:'velocity over the last 0.15 s, 1% noise',ts:26}});
run(12,function(p){{var q=p/.33,off=q<1?.1*(1-q)*(1-q):0;
a1.frame();a1.vl(T,REF,[3,5]);a1.line(te,XE,{{c:CM.whit,w:3}});a1.line(tb.map(function(v){{return v+T+off}}),XB,{{c:CM.spec,w:3}});
leg(a1.x+18,a1.y+40,[['end of record, $x(t)$',CM.whit],['its periodic copy, $x(t−T)$',CM.spec]]);
if(q>=1)tx('jump at the wrap: $x$(0) ≠ $x(T)$',a1.x+14,a1.y+a1.h-18,{{s:26,c:CM.spec}});
a2.frame();a2.line(tw,VV,{{c:CM.truth,w:4,d:[12,8]}});if(q>=1){{var m=Math.max(2,Math.round(Math.min(1,(p-.33)/.55)*D.nw));a2.line(tw,VS,{{c:CM.spec,w:2.6}},0,m);a2.line(tw,VK,{{c:CM.ks,w:2.6}},0,m)}}
leg(a2.x+18,a2.y+a2.h-100,[['true',CM.truth,[12,8]],['spectral (FFT)',CM.spec],['state-space smoother',CM.ks]])}});"""
    build('edges', code, OUT)


def impact():
    t, dt, X, V, timp = bench_delay.vibroimpact()
    rng = np.random.default_rng(3)
    xn = X + 0.005*X.std()*rng.standard_normal(len(X))
    sd = xn.std()
    vtv = kin.diff_tvreg(xn/sd, dt, 1e-5)*sd
    vwh = kin.diff_whittaker(xn, dt, order=1, fc=350)
    vsp = kin.diff_spectral(xn, dt, order=1, fc=350)
    mask = np.zeros(len(t), bool)
    for tk in timp:
        mask |= np.abs(t - tk) <= 0.004
    loc = lambda e: 100*np.linalg.norm(e[mask] - V[mask])/np.linalg.norm(V[mask])
    L = dict(sp=round(loc(vsp), 1), wh=round(loc(vwh), 1), tv=round(loc(vtv), 1))
    print('impact', L)
    ti = timp[3]
    w = np.abs(t - ti) <= 0.25
    vm = np.abs(V[w]).max()
    dmax = max(np.abs(x[w] - V[w]).max() for x in (vsp, vwh, vtv))
    D = dict(ti=float(ti), t0=float(t[w][0]), dt=float(dt), n=int(w.sum()), V=e16(V[w], vm/32000), vm=vm/32000, dm=dmax,
             sp=e8(vsp[w] - V[w], dmax), wh=e8(vwh[w] - V[w], dmax), tv=e8(vtv[w] - V[w], dmax),
             ti_all=[float(x) for x in timp if abs(x - ti) <= 0.25], L=L)
    code = f"""var D={js(D)},CM={js(CM)},n=D.n,tt=lin(D.t0,D.t0+(n-1)*D.dt,n),VV=b64(D.V,D.vm),
add=function(s){{var d=b64(s,D.dm/127,0,8);return VV.map(function(v,i){{return v+d[i]}})}},SP=add(D.sp),WH=add(D.wh),TV=add(D.tv);
var ax=new Ax(150,70,1410,520,{{xl:[0,1],yl:[0,1],xlab:'$t$ (s)',ylab:'$ẋ$ (m/s)',yoff:110}});
function nice(r){{var s=Math.pow(10,Math.floor(Math.log10(r/4))),m=r/4/s;return s*(m<1.5?1:m<3.5?2:5)}}
function ticks(a,b,f){{var s=nice(b-a),r=[];for(var v=Math.ceil(a/s)*s;v<=b;v+=s)r.push([v,(Math.abs(v)<s/2?0:v).toFixed(f)]);return r}}
run(14,function(p){{var q=Math.min(1,p/.66),h=Math.exp(Math.log(.25)+(Math.log(.008)-Math.log(.25))*ease(q)),lo=1e9,hi=-1e9;
for(var i=0;i<n;i++)if(Math.abs(tt[i]-D.ti)<h){{lo=Math.min(lo,VV[i]);hi=Math.max(hi,VV[i])}}var pd=.18*(hi-lo);
ax.xl=[D.ti-h,D.ti+h];ax.yl=[lo-pd,hi+pd];var fd=h>.05?2:3;ax.o.xt=ticks(ax.xl[0],ax.xl[1],fd);ax.o.yt=ticks(ax.yl[0],ax.yl[1],2);
ax.frame();D.ti_all.forEach(function(x){{ax.vl(x,REF,[3,5],1.4)}});
ax.line(tt,VV,{{c:CM.truth,w:4.4,d:[12,8]}});ax.line(tt,SP,{{c:CM.spec,w:2.2}});ax.line(tt,WH,{{c:CM.whit,w:2.6}});ax.line(tt,TV,{{c:CM.tv,w:3.2}});
tx('vibro-impact oscillator, 0.5% noise: ±'+Math.round(1000*h)+' ms around an impact',ax.x+ax.w/2,ax.y-18,{{a:'c',s:30}});
g.fillStyle='rgba(255,255,255,.92)';g.fillRect(ax.x+ax.w-560,ax.y+ax.h-232,548,220);
tx('velocity error within ±4 ms of the 5 impacts',ax.x+ax.w-546,ax.y+ax.h-196,{{s:24,c:'#5B6168'}});
leg(ax.x+ax.w-546,ax.y+ax.h-150,[['true velocity',CM.truth,[12,8]],['spectral: '+D.L.sp+'%',CM.spec],['Whittaker ($L_{{2}}$): '+D.L.wh+'%',CM.whit],['total variation ($L_{{1}}$): '+D.L.tv+'%',CM.tv]])}});"""
    build('impact', code, OUT)


if __name__ == '__main__':
    for nm in (sys.argv[1:] or ['illposed', 'knob', 'fusion', 'edges', 'impact']):
        globals()[nm]()
