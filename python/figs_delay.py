"""Slide figures for the October 2026 additions: delay reconstruction (SVD/SOD)
and causal differentiation.  Same style as figs_slides.py: LaTeX text,
MATLAB ColorOrder with colour bound to method, white panel, PNG + vector PDF.

    python figs_delay.py      -> ../figures/s_delay_*.{png,pdf}, s_causal.{png,pdf}
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(HERE)
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotprefs as pp
import kinematics as kin
import bench

pp.apply_preferences(sizes=(17, 15, 13))
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
OUT = os.path.join(HERE, "..", "figures")
SL = (12.6, 5.6)

# NLD figure palette, bound to method as in figs_slides.py
C = dict(truth="#8A8578", spec="#B4622A", whit="#1F5A85", ks="#132433",
         ksbar="#8FA3B0", delay="#774860", sod="#CA863E", lev="#CA863E", noise="#8A8578")


def _fin(fig, name):
    pp.latexify(fig)
    plt.rcParams["pdf.fonttype"] = 42
    fig.tight_layout()
    out = os.path.join(OUT, name)
    fig.savefig(out + ".png", dpi=200)
    fig.savefig(out + ".pdf")
    plt.close(fig)
    print("wrote", os.path.normpath(out) + ".{png,pdf}")


def pe(e, g, trim=0.05):
    k = int(trim * len(g)); s = slice(k, len(g) - k)
    return 100 * np.linalg.norm(e[s] - g[s]) / np.linalg.norm(g[s])


def oracle(fn, grid, tru):
    return min(pe(fn(g), tru) for g in grid)


t, dt, X, V, A = bench.duffing()
FCG = np.geomspace(20, 400, 40)


def fig_method():
    xn = bench.noisy_position(X, dt, 1.0, np.random.default_rng(110))
    a, info = kin.diff_delay(xn, dt, 2, return_info=True)
    aw = kin.diff_whittaker(xn, dt, 2, fc=69.8)
    fig, axs = plt.subplots(1, 2, figsize=SL, gridspec_kw={"width_ratios": [1, 1.25]})
    ax = axs[0]
    sv = info["sv"]; r = info["r"]; keep = info["keep"]
    k = np.arange(1, 81)
    ax.semilogy(k, sv[:80], "o", ms=4, color=C["noise"], label="noise directions")
    kk = np.arange(1, r + 1)
    ax.semilogy(kk[keep], sv[:r][keep], "o", ms=6, color=C["delay"], label="kept: signal subspace")
    if (~keep).any():
        ax.semilogy(kk[~keep], sv[:r][~keep], "x", ms=8, mew=2, color=C["ks"],
                    label="above threshold, outside signal band")
    p = info["L"]; K = len(xn) - p + 1; beta = min(K, p) / max(K, p)
    thr = (0.56 * beta ** 3 - 0.95 * beta ** 2 + 1.82 * beta + 1.43) * np.median(sv)
    ax.axhline(thr, color=C["truth"], lw=1.4, ls="--")
    ax.text(80, thr * 1.25, "Gavish--Donoho threshold", ha="right", fontsize=13)
    ax.set_xlabel("component index"); ax.set_ylabel("singular value")
    ax.set_title(f"Delay window L = {info['L']}: {keep.sum()} of 2000 directions kept")
    ax.legend(frameon=False, fontsize=12, loc="center right")
    ax = axs[1]
    sl = slice(300, 1300)
    ax.plot(t[sl], aw[sl] - A[sl], color=C["whit"], lw=1.2, label=f"Whittaker, oracle cutoff ({pe(aw, A):.2f}%)")
    ax.plot(t[sl], a[sl] - A[sl], color=C["delay"], lw=1.6, label=f"delay SVD, self-tuned ({pe(a, A):.2f}%)")
    ax.axhline(0, color=C["truth"], lw=0.8)
    ax.set_ylim(-0.7, 0.7)
    ax.set_xlabel("time (s)"); ax.set_ylabel("acceleration error (m/s$^2$)")
    ax.set_title("Acceleration error, 1% noisy position")
    ax.legend(frameon=False, fontsize=12, loc="upper right", ncol=1)
    _fin(fig, "s_delay_method")


def fig_bench():
    noise = [0.1, 1.0, 5.0]
    names = [("Spectral (FFT), oracle", C["spec"]), ("Whittaker, oracle", C["whit"]),
             ("State-space, self-tuned", C["ksbar"]), ("Delay SVD, self-tuned", C["delay"])]
    res = {n: ([], []) for n, _ in names}
    for pct in noise:
        xn = bench.noisy_position(X, dt, pct, np.random.default_rng(110))
        r = kin.kinsmooth(t, x=xn, nstate=4)
        vals = [(oracle(lambda f: kin.diff_spectral(xn, dt, 1, fc=f), FCG, V),
                 oracle(lambda f: kin.diff_spectral(xn, dt, 2, fc=f), FCG, A)),
                (oracle(lambda f: kin.diff_whittaker(xn, dt, 1, fc=f), FCG, V),
                 oracle(lambda f: kin.diff_whittaker(xn, dt, 2, fc=f), FCG, A)),
                (pe(r["v"], V), pe(r["a"], A)),
                (pe(kin.diff_delay(xn, dt, 1), V), pe(kin.diff_delay(xn, dt, 2), A))]
        for (n, _), (ev, ea) in zip(names, vals):
            res[n][0].append(ev); res[n][1].append(ea)
    fig, axs = plt.subplots(1, 2, figsize=SL)
    xs = np.arange(3); w = 0.2
    for ax, j, lab in [(axs[0], 0, "velocity"), (axs[1], 1, "acceleration")]:
        for i, (n, col) in enumerate(names):
            v = res[n][j]
            ax.bar(xs + (i - 1.5) * w, v, w, color=col, label=n)
            for xx, vv in zip(xs + (i - 1.5) * w, v):
                ax.text(xx, vv * 1.08, f"{vv:.2f}", ha="center", fontsize=10.5, rotation=90, va="bottom")
        ax.set_yscale("log"); ax.set_ylim(0.03, 60 if j else 20)
        ax.set_xticks(xs); ax.set_xticklabels([f"{n}% noise" for n in noise])
        ax.set_ylabel(f"{lab} error (% rms)")
        ax.set_title(lab.capitalize())
    axs[0].legend(frameon=False, fontsize=12, loc="upper left")
    _fin(fig, "s_delay_bench")
    return res


def fig_sod():
    xn = bench.noisy_position(X, dt, 1.0, np.random.default_rng(110))
    Ls = [41, 81, 161, 321, 641, 1001, 1501, 2000]
    esvd = [pe(kin.diff_delay(xn, dt, 1, L=L), V) for L in Ls]
    esod = [pe(kin.diff_delay(xn, dt, 1, L=L, method="sod_full"), V) for L in Ls]
    an = bench.noisy_acceleration(A, dt, 1.0, np.random.default_rng(7))
    g = np.geomspace(0.5, 15, 30)
    r = kin.kinsmooth(t, a=an, nstate=4, bias=True, hp=4.0)
    ints = [("Tikhonov, oracle", C["whit"], oracle(lambda f: kin.int_tikhonov(an, dt, 2, fc=f), g, X),
             oracle(lambda f: kin.int_tikhonov(an, dt, 1, fc=f), g, V)),
            ("State-space, hp = 4 Hz", C["ksbar"], pe(r["x"], X), pe(r["v"], V)),
            ("Delay SVD, fc = 4 Hz", C["delay"], pe(kin.int_delay(an, dt, 2, method="svd"), X),
             pe(kin.int_delay(an, dt, 1, method="svd"), V)),
            ("Delay SOD, fc = 4 Hz", C["sod"], pe(kin.int_delay(an, dt, 2), X), pe(kin.int_delay(an, dt, 1), V))]
    fig, axs = plt.subplots(1, 2, figsize=SL)
    ax = axs[0]
    ax.loglog(Ls, esvd, "o-", color=C["delay"], lw=2.4, label="SVD: ranked by energy")
    ax.loglog(Ls, esod, "s-", color=C["sod"], lw=2.4, label="SOD alone: ranked by smoothness")
    ax.set_xlabel("delay window L (samples)"); ax.set_ylabel("velocity error (% rms)")
    ax.set_title("Differentiation: energy ranking wins")
    ax.legend(frameon=False, fontsize=12, loc="upper left")
    ax.text(0.04, 0.72, "long windows let smooth noise\ndirections outrank the signal",
            transform=ax.transAxes, ha="left", fontsize=12, color=C["sod"])
    ax = axs[1]
    xs = np.arange(2); w = 0.2
    for i, (n, col, ex, ev) in enumerate(ints):
        v = [ex, ev]
        ax.bar(xs + (i - 1.5) * w, v, w, color=col, label=n)
        for xx, vv in zip(xs + (i - 1.5) * w, v):
            ax.text(xx, vv + 0.06, f"{vv:.2f}", ha="center", fontsize=11)
    ax.set_xticks(xs); ax.set_xticklabels(["displacement", "velocity"])
    ax.set_ylabel("error (% rms)"); ax.set_ylim(0, 4.4)
    ax.set_title("Integration: SOD separates the drift")
    ax.legend(frameon=False, fontsize=12, loc="upper left")
    _fin(fig, "s_delay_sod")
    return esvd, esod, ints


def fig_causal():
    xn = bench.noisy_position(X, dt, 1.0, np.random.default_rng(110))
    Lg = np.geomspace(1e2, 1e5, 31)
    errs = [pe(kin.diff_levant(xn, dt, L, 1, zero_phase=False), V) for L in Lg]
    Lb = Lg[int(np.argmin(errs))]
    vl = kin.diff_levant(xn, dt, Lb, 1, zero_phase=False)
    rc = kin.kinsmooth(t, x=xn, nstate=4, causal=True)
    rs = kin.kinsmooth(t, x=xn, nstate=4)
    fig, axs = plt.subplots(1, 2, figsize=SL, gridspec_kw={"width_ratios": [1.6, 1]})
    ax = axs[0]
    sl = slice(1000, 1300)
    ax.plot(t[sl], vl[sl], color=C["lev"], lw=1.4, label=f"Levant ({pe(vl, V):.1f}%)")
    ax.plot(t[sl], rc["v"][sl], color=C["ks"], lw=2.0, label=f"Kalman filter ({pe(rc['v'], V):.1f}%)")
    ax.plot(t[sl], V[sl], color=C["truth"], lw=2.6, ls="--", label="true velocity")
    ax.set_xlabel("time (s)"); ax.set_ylabel("velocity (m/s)")
    ax.set_title("Online: only past samples are used")
    ax.set_ylim(-0.13, 0.165)
    ax.legend(frameon=False, fontsize=12, loc="upper center", ncol=3)
    ax = axs[1]
    labs = ["Levant\n(oracle L)", "Kalman filter\n(causal)", "RTS smoother\n(offline)"]
    vals = [pe(vl, V), pe(rc["v"], V), pe(rs["v"], V)]
    cols = [C["lev"], C["ksbar"], C["whit"]]
    ax.bar(range(3), vals, 0.6, color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.25, f"{v:.2f}", ha="center", fontsize=13)
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=13)
    ax.set_ylabel("velocity error (% rms)"); ax.set_ylim(0, 14)
    ax.set_title("Same record, 1% noise")
    _fin(fig, "s_causal")
    return vals, Lb


if __name__ == "__main__":
    fig_method()
    print("bench", fig_bench())
    print("sod", fig_sod())
    print("causal", fig_causal())
