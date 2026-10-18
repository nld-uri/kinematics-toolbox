"""Motion-graphics animations for the talk and the web page.

    python animations.py [names...] [--frames N] [--still-only]

Writes figures/anim/<name>.mp4 (H.264 Main 4.0, 1600x700, 30 fps),
<name>.gif (web) and <name>_still.pdf. Every curve is computed with
kinematics.py on the benchmark signals of bench.py / bench_delay.py. Text is
set by LaTeX (Computer Modern); colours are the method bindings of
figs_slides.py.

  illposed  noise gain (i w)^n as the order sweeps from two integrals to two
            derivatives: the same problem, run in opposite directions
  knob      the one regularisation knob: Whittaker acceleration as the cutoff
            sweeps, with the U-shaped error curve
  fusion    Kalman forward filter, then RTS backward smoother, fusing a noisy
            displacement and a drifting accelerometer (posterior +-2 sigma)
  edges     the FFT treats the record as periodic: the wrap-around jump and
            the end error it causes, against the state-space smoother
  impact    a velocity jump at an impact: L2 smoothing rounds the corner,
            total variation keeps it
"""
import os
import sys
import shutil
import argparse
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker
from matplotlib.animation import FuncAnimation, FFMpegWriter
from scipy import signal as sg

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kinematics as kin   # noqa: E402
import bench               # noqa: E402
import bench_delay         # noqa: E402
from figs_slides import C  # noqa: E402  (method colour bindings)

OUT = os.path.join(HERE, '..', 'figures', 'anim')
INK, PAPER, REF = '#132433', '#F7F6F2', '#8A8578'
FIG, DPI = (8, 3.5), 200

if '/Library/TeX/texbin' not in os.environ.get('PATH', '') and os.path.isdir('/Library/TeX/texbin'):
    os.environ['PATH'] += os.pathsep + '/Library/TeX/texbin'
plt.rcParams.update({
    'text.usetex': shutil.which('latex') is not None, 'font.family': 'serif',
    'font.serif': ['Computer Modern Roman'], 'mathtext.fontset': 'cm',
    'text.latex.preamble': r'\usepackage{amsmath}\usepackage{amssymb}',
    'font.size': 12, 'axes.labelsize': 12, 'legend.fontsize': 9, 'xtick.labelsize': 10,
    'ytick.labelsize': 10, 'axes.linewidth': 0.6, 'lines.linewidth': 1.3,
    'figure.facecolor': PAPER, 'savefig.facecolor': PAPER, 'axes.facecolor': 'white',
    'text.color': INK, 'axes.labelcolor': INK, 'xtick.color': INK, 'ytick.color': INK,
    'axes.edgecolor': INK, 'legend.frameon': False})
FF_ARGS = ['-pix_fmt', 'yuv420p', '-profile:v', 'main', '-level:v', '4.0', '-g', '30',
           '-tag:v', 'avc1', '-colorspace', 'bt709', '-color_primaries', 'bt709',
           '-color_trc', 'bt709', '-brand', 'mp42', '-movflags', '+faststart']


def save(fig, anim, name, still_frame, still_only):
    os.makedirs(OUT, exist_ok=True)
    anim._func(still_frame)
    fig.savefig(os.path.join(OUT, name + '_still.pdf'))
    fig.savefig(os.path.join(OUT, name + '.jpg'), dpi=DPI, pil_kwargs=dict(quality=90))
    if not still_only:
        mp4 = os.path.join(OUT, name + '.mp4')
        anim.save(mp4, writer=FFMpegWriter(fps=30, codec='libx264', bitrate=4000, extra_args=FF_ARGS), dpi=DPI)
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', mp4, '-vf',
                        'fps=15,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];'
                        '[b][p]paletteuse=dither=bayer:bayer_scale=4', os.path.join(OUT, name + '.gif')], check=True)
        print('wrote', name)
    plt.close(fig)


# ------------------------------------------------------------------ 1 ill-posedness
def illposed(nf, still_only):
    t, dt, X, V, A = bench.duffing()
    fs = 1/dt
    f, Px = sg.welch(X, fs=fs, nperseg=1024)
    f, Px = f[1:], Px[1:]
    w = 2*np.pi*f
    noise = (0.01*X.std())**2*2*dt*np.ones_like(f)      # 1 % white noise on position
    ns = np.r_[np.linspace(-2, 2, nf//2), np.linspace(2, -2, nf - nf//2)]
    fig = plt.figure(figsize=FIG, dpi=DPI)
    ax1 = fig.add_axes([0.08, 0.16, 0.36, 0.72]); ax2 = fig.add_axes([0.56, 0.16, 0.41, 0.72])
    fg = np.logspace(-1, 3, 300); wg = 2*np.pi*fg
    for n in [-2, -1, 1, 2]:
        ax1.loglog(fg, wg**float(n), color=REF, lw=0.6, ls=':')
    ax1.axhline(1, color=REF, lw=0.6)
    gain, = ax1.loglog([], [], color=C['spec'], lw=2.2)
    ax1.set_ylim(1e-7, 1e7); ax1.set_xlim(fg[0], fg[-1])
    ax1.set_xlabel('frequency (Hz)'); ax1.set_ylabel(r'noise gain $\omega^{n}$')
    ax1.text(0.15, 1e5, r'derivatives: gain grows with $\omega$', fontsize=9, color=REF)
    ax1.text(0.15, 3e-6, r'integrals: gain grows as $\omega\to0$', fontsize=9, color=REF)
    lab = ax1.set_title('')
    sigl, = ax2.loglog([], [], color=C['truth'], ls='--', lw=1.8, label='signal')
    noil, = ax2.loglog([], [], color=C['spec'], lw=1.6, label='noise (1\\% white on position)')
    fill = [None]
    ax2.set_xlim(f[0], f[-1]); ax2.set_ylim(1e-22, 1e8)
    ax2.set_xlabel('frequency (Hz)'); ax2.set_ylabel(r'PSD of the $n$th derivative')
    ax2.legend(loc='upper left')
    ax2.set_title('where noise exceeds signal, the estimate is noise', fontsize=11)

    def fr(k):
        n = ns[k]
        gain.set_data(fg, wg**n)
        word = 'derivatives' if n > 0.05 else ('integrals' if n < -0.05 else 'identity')
        lab.set_text(rf'$n={n:+.2f}$ ({word})')
        S, N = Px*w**(2*n), noise*w**(2*n)
        sigl.set_data(f, S); noil.set_data(f, N)
        if fill[0] is not None:
            fill[0].remove()
        fill[0] = ax2.fill_between(f, 1e-30, 1e30, where=N > S, color=C['spec'], alpha=0.10, lw=0)
        return []
    anim = FuncAnimation(fig, fr, frames=nf, blit=False)
    save(fig, anim, 'illposed', int(0.85*(nf//2)), still_only)


# ------------------------------------------------------------------ 2 the knob
def knob(nf, still_only):
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(1)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    grid = np.geomspace(20, 600, 90)
    est = [kin.diff_whittaker(xn, dt, order=2, fc=fc) for fc in grid]
    err = np.array([bench.relerr(e, A) for e in est])
    i0 = int(np.argmin(err))
    seq = np.r_[np.linspace(0, len(grid) - 1, nf//2), np.linspace(len(grid) - 1, i0, nf - nf//2)].astype(int)
    win = (t > 0.30) & (t < 0.42)
    fig = plt.figure(figsize=FIG, dpi=DPI)
    ax1 = fig.add_axes([0.08, 0.16, 0.50, 0.72]); ax2 = fig.add_axes([0.68, 0.16, 0.30, 0.72])
    ax1.plot(t[win], A[win], color=C['truth'], ls='--', lw=2.0, label='true acceleration')
    estl, = ax1.plot([], [], color=C['whit'], lw=1.3, label='Whittaker estimate')
    lim = 1.35*np.abs(A[win]).max()
    ax1.set_ylim(-lim, lim); ax1.set_xlim(t[win][0], t[win][-1])
    ax1.set_xlabel(r'$t$ (s)'); ax1.set_ylabel(r'$\ddot x$ (m/s$^2$)'); ax1.legend(loc='upper right', ncol=2)
    ttl = ax1.set_title('')
    ax2.loglog(grid, err, color=C['whit'], lw=1.6)
    dot, = ax2.loglog([], [], 'o', color=C['spec'], ms=7)
    ax2.axvline(grid[i0], color=REF, ls=':', lw=0.8)
    ax2.set_xlabel(r'cutoff $f_c$ (Hz)'); ax2.set_ylabel(r'acceleration error (\%)')
    ax2.text(0.05, 0.86, r'too smooth: bias', transform=ax2.transAxes, fontsize=9, color=REF)
    ax2.text(0.95, 0.06, r'too rough: noise', transform=ax2.transAxes, fontsize=9, color=REF, ha='right')
    ax2.set_xticks([30, 100, 300]); ax2.set_xticklabels(['30', '100', '300'])
    ax2.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax2.set_title('one knob, one optimum', fontsize=11)

    def fr(k):
        j = seq[k]
        estl.set_data(t[win], est[j][win])
        dot.set_data([grid[j]], [err[j]])
        ttl.set_text(rf'1\% noisy position, $f_c={grid[j]:.0f}$ Hz: error {err[j]:.1f}\%')
        return []
    anim = FuncAnimation(fig, fr, frames=nf, blit=False)
    save(fig, anim, 'knob', nf - 1, still_only)


# ------------------------------------------------------------------ 3 fusion
def fusion(nf, still_only):
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(0)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    an = bench.noisy_acceleration(A, dt, 2.0, rng)
    rs = kin.kinsmooth(t, x=xn, a=an, nstate=4, bias=True)
    rf = kin.kinsmooth(t, x=xn, a=an, nstate=4, bias=True, causal=True, q=rs['q'])
    ef, es = rf['v'] - V, rs['v'] - V
    sf, ss = rf['std'][:, 1], rs['std'][:, 1]
    vs = V.std()
    pf, ps = bench.relerr(rf['v'], V), bench.relerr(rs['v'], V)
    n = len(t)
    nf1 = nf//2
    fig = plt.figure(figsize=FIG, dpi=DPI)
    ax0 = fig.add_axes([0.10, 0.68, 0.87, 0.22]); ax1 = fig.add_axes([0.10, 0.15, 0.87, 0.45])
    ax0.plot(t, xn/X.std(), color=C['whit'], lw=0.5, label=r'displacement, 1\% noise')
    ax0.plot(t, an/A.std() - 3.2, color=C['acc'], lw=0.5, label='accelerometer, noise and drift')
    ax0.set_xlim(t[0], t[-1]); ax0.set_yticks([]); ax0.set_xticklabels([])
    ax0.legend(loc='lower center', bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=9)
    ax1.axhline(0, color=REF, lw=0.6)
    ax1.set_xlim(t[0], t[-1]); ax1.set_ylim(-0.06, 0.06)
    ax1.set_xlabel(r'$t$ (s)'); ax1.set_ylabel(r'$(\hat{\dot x}-\dot x)/\sigma_{\dot x}$')
    band = [None]
    line, = ax1.plot([], [], lw=0.8, color=C['spec'])
    line2, = ax1.plot([], [], lw=0.8, color=C['ks'])
    cur = ax1.axvline(0, color=INK, lw=1.0)
    txt = ax1.text(0.01, 0.88, '', transform=ax1.transAxes, fontsize=10, zorder=10, bbox=dict(fc='white', ec='none', alpha=0.85, pad=2))

    def fr(k):
        if band[0] is not None:
            band[0].remove()
        if k < nf1:                                   # forward Kalman filter
            m = max(2, int((k + 1)/nf1*n))
            sl = slice(0, m)
            band[0] = ax1.fill_between(t[sl], -2*sf[sl]/vs, 2*sf[sl]/vs, color=C['ksbar'], alpha=0.45, lw=0)
            line.set_data(t[sl], ef[sl]/vs); line2.set_data([], [])
            cur.set_xdata([t[m - 1]]*2); cur.set_visible(True); cur.set_visible(True)
            txt.set_text(rf'forward Kalman filter (causal): error {pf:.2f}\% rms, band $\pm2\sigma$')
        else:                                         # backward RTS pass replaces from the end
            m = max(1, int((k - nf1 + 1)/(nf - nf1)*n))
            b = n - m
            e = np.r_[ef[:b], es[b:]]; s = np.r_[sf[:b], ss[b:]]
            band[0] = ax1.fill_between(t, -2*s/vs, 2*s/vs, color=C['ksbar'], alpha=0.45, lw=0)
            line.set_data(t[:b + 1], ef[:b + 1]/vs); line2.set_data(t[b:], es[b:]/vs)
            cur.set_xdata([t[min(max(b, 0), n - 1)]]*2); cur.set_visible(b > 0)
            txt.set_text(rf'backward RTS smoother: error {ps:.2f}\% rms, band shrinks')
        return []
    anim = FuncAnimation(fig, fr, frames=nf, blit=False)
    save(fig, anim, 'fusion', nf - 1, still_only)


# ------------------------------------------------------------------ 4 edges
def edges(nf, still_only):
    t, dt, X, V, A = bench.duffing()
    rng = np.random.default_rng(2)
    xn = bench.noisy_position(X, dt, 1.0, rng)
    vsp = kin.diff_spectral(xn, dt, order=1, fc=120)
    vks = kin.kinsmooth(t, x=xn, nstate=4)['v']
    T = t[-1] + dt
    sx, sv = X.std(), V.std()
    h = 0.12                                          # half window around the wrap
    fig = plt.figure(figsize=FIG, dpi=DPI)
    ax1 = fig.add_axes([0.07, 0.17, 0.40, 0.70]); ax2 = fig.add_axes([0.57, 0.17, 0.40, 0.70])
    ax1.set_xlim(T - h, T + h); ax1.set_ylim(-2.6, 2.6)
    ax1.set_xlabel(r'$t$ (s)'); ax1.set_ylabel(r'$x/\sigma_x$')
    ax1.set_title('the FFT sees the record as periodic', fontsize=11)
    e = t > T - h - 0.01
    ax1.plot(t[e], X[e]/sx, color=C['whit'], lw=1.6, label=r'end of record, $x(t)$')
    b = t < h + 0.05
    copy, = ax1.plot([], [], color=C['spec'], lw=1.6, label=r'its periodic copy, $x(t-T)$')
    ax1.axvline(T, color=REF, ls=':', lw=0.8)
    ax1.legend(loc='upper left', fontsize=8.5)
    note = ax1.text(T - h + 0.006, -2.35, '', fontsize=9.5, color=C['spec'])
    ax2.set_xlim(T - 0.15, T); ax2.set_ylim(-3.2, 3.2)
    ax2.set_xlabel(r'$t$ (s)'); ax2.set_ylabel(r'$\dot x/\sigma_{\dot x}$')
    ax2.set_title('velocity over the last 0.15 s, 1\\% noise', fontsize=11)
    w = t > T - 0.15
    ax2.plot(t[w], V[w]/sv, color=C['truth'], ls='--', lw=2.0, label='true')
    l_sp, = ax2.plot([], [], color=C['spec'], lw=1.3, label='spectral (FFT)')
    l_ks, = ax2.plot([], [], color=C['ks'], lw=1.3, label='state-space smoother')
    ax2.legend(loc='lower left', fontsize=8.5)
    tw, vspw, vksw = t[w], vsp[w]/sv, vks[w]/sv
    nf1 = nf//3

    def fr(k):
        if k < nf1:                                   # slide the periodic copy into place
            off = 0.10*(1 - k/(nf1 - 1))**2
            copy.set_data(t[b] + T + off, X[b]/sx)
            note.set_text('')
            l_sp.set_data([], []); l_ks.set_data([], [])
        else:
            copy.set_data(t[b] + T, X[b]/sx)
            note.set_text(r'jump at the wrap: $x(0)\neq x(T)$')
            m = max(2, int((k - nf1 + 1)/(nf - nf1 - 20)*len(tw)))
            l_sp.set_data(tw[:m], vspw[:m]); l_ks.set_data(tw[:m], vksw[:m])
        return []
    anim = FuncAnimation(fig, fr, frames=nf, blit=False)
    save(fig, anim, 'edges', nf - 1, still_only)


# ------------------------------------------------------------------ 5 impact
def impact(nf, still_only):
    t, dt, X, V, timp = bench_delay.vibroimpact()
    rng = np.random.default_rng(3)
    xn = X + 0.005*X.std()*rng.standard_normal(len(X))
    sd = xn.std()
    vtv = kin.diff_tvreg(xn/sd, dt, 1e-5)*sd           # as in bench_delay.py
    vwh = kin.diff_whittaker(xn, dt, order=1, fc=350)
    vsp = kin.diff_spectral(xn, dt, order=1, fc=350)
    mask = np.zeros(len(t), bool)
    for tk in timp:
        mask |= np.abs(t - tk) <= 0.004
    loc = lambda e: 100*np.linalg.norm(e[mask] - V[mask])/np.linalg.norm(V[mask])
    ti = timp[3]
    h1 = 0.008
    zooms = np.r_[np.geomspace(0.25, h1, nf*2//3), np.full(nf - nf*2//3, h1)]
    fig = plt.figure(figsize=FIG, dpi=DPI)
    ax = fig.add_axes([0.09, 0.16, 0.88, 0.72])
    ax.plot(t, V, color=C['truth'], ls='--', lw=2.2, label='true velocity', zorder=5)
    ax.plot(t, vsp, color=C['spec'], lw=1.2, label=rf'spectral: {loc(vsp):.1f}\%')
    ax.plot(t, vwh, color=C['whit'], lw=1.4, label=rf'Whittaker ($L_2$): {loc(vwh):.1f}\%')
    ax.plot(t, vtv, color=C['tv'], lw=1.8, label=rf'total variation ($L_1$): {loc(vtv):.1f}\%')
    for tk in timp:
        ax.axvline(tk, color=REF, lw=0.5, ls=':')
    ax.set_xlabel(r'$t$ (s)'); ax.set_ylabel(r'$\dot x$ (m/s)')
    ax.legend(loc='lower right', framealpha=0.9, frameon=True, edgecolor='none',
              title=r'velocity error within $\pm4$ ms of the 5 impacts', title_fontsize=9)
    ttl = ax.set_title('')

    def fr(k):
        h = zooms[k]
        ax.set_xlim(ti - h, ti + h)
        s = (t > ti - h) & (t < ti + h)
        lo, hi = V[s].min(), V[s].max()
        pad = 0.18*(hi - lo + 1e-12)
        ax.set_ylim(lo - pad, hi + pad)
        ttl.set_text(rf'vibro-impact oscillator, 0.5\% noise: $\pm{1000*h:.0f}$ ms around an impact')
        return []
    anim = FuncAnimation(fig, fr, frames=nf, blit=False)
    save(fig, anim, 'impact', nf - 1, still_only)


ALL = dict(illposed=illposed, knob=knob, fusion=fusion, edges=edges, impact=impact)
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('names', nargs='*')
    p.add_argument('--frames', type=int, default=240)
    p.add_argument('--still-only', action='store_true')
    a = p.parse_args()
    for nm in (a.names or ALL):
        ALL[nm](a.frames if nm != 'fusion' else int(a.frames*1.5), a.still_only)
