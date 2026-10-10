
import numpy as np, matplotlib as mpl, matplotlib.pyplot as plt
from scipy import signal as _sg

C = dict(truth="#EDB120", spec="#D95319", sg="#808080", whit="#0072BD",
         tv="#77AC30", ks="#000000", tik="#0072BD", bad="#BFBFBF", acc="#7E2F8E")
SL = (12.6, 5.6)      # full-width slide figure
HL = (6.15, 4.9)      # half-width

def _fin(fig, out):
    import matplotlib as _m, plotprefs as _tf
    _tf.latexify(fig)
    _m.rcParams["pdf.fonttype"] = 42
    fig.tight_layout(); fig.savefig(out, dpi=200)
    fig.savefig(out[:-4] + ".pdf"); return out

def f_illposed(t, dt, X, xn, A, out="s_illposed.png"):
    fig, axs = plt.subplots(1, 2, figsize=SL)
    f = np.logspace(-1, 3, 400); w = 2*np.pi*f
    ax = axs[0]
    for n, ls, lab in [(1,"-","one derivative  $\\times\\omega$"), (2,"--","two derivatives  $\\times\\omega^2$")]:
        ax.loglog(f, w**n, color=C["spec"], ls=ls, lw=2.6, label=lab)
    for n, ls, lab in [(1,"-","one integral  $\\times 1/\\omega$"), (2,"--","two integrals  $\\times 1/\\omega^2$")]:
        ax.loglog(f, w**-float(n), color=C["whit"], ls=ls, lw=2.6, label=lab)
    ax.axhline(1, color="k", lw=1.0, alpha=0.5)
    ax.set_xlabel("frequency (Hz)"); ax.set_ylabel("noise gain")
    ax.set_title("Noise gain is unbounded at both ends")
    ax.legend(frameon=False, fontsize=13, loc="lower left"); ax.set_ylim(1e-6, 1e8)
    ax = axs[1]
    fr, Pt = _sg.welch(A, fs=1/dt, nperseg=2048)
    fr, Pn = _sg.welch(np.gradient(np.gradient(xn, dt), dt), fs=1/dt, nperseg=2048)
    ax.loglog(fr[1:], Pt[1:], color=C["truth"], lw=3.4, label="true acceleration")
    ax.loglog(fr[1:], Pn[1:], color=C["spec"], lw=1.7, label="2nd finite difference of a 1% noisy position")
    ax.axvline(30, color="k", lw=1.2, ls=":")
    ax.set_ylim(1e-14, 1e4)
    ax.set_xlabel("frequency (Hz)"); ax.set_ylabel("acceleration PSD")
    ax.set_title("Above ~30 Hz the estimate is pure amplified noise")
    ax.legend(frameon=False, fontsize=12, loc="lower left")
    return _fin(fig, out)

def f_naive(t, dt, X, V, xn, an, A, x_naive, out="s_naive.png"):
    fig, axs = plt.subplots(1, 2, figsize=SL)
    ax = axs[0]
    anv = np.gradient(np.gradient(xn, dt), dt)
    ax.plot(t, anv, color=C["spec"], lw=0.6, label="2nd finite difference of the measurement")
    ax.plot(t, A, color=C["truth"], lw=3.2, label="true acceleration")
    ax.set_xlim(0.4, 0.7); ax.set_xlabel("time (s)"); ax.set_ylabel("acceleration (m/s$^2$)")
    ax.set_title("Differentiate twice, naively: %.0f%% rms error" % (100*np.sqrt(np.mean((anv-A)**2))/np.sqrt(np.mean(A**2))))
    ax.legend(frameon=False, fontsize=12, loc="upper right")
    ax = axs[1]
    ax.plot(t, x_naive*1e3, color=C["bad"], lw=2.0, label="cumulative trapezoid of the measurement")
    ax.plot(t, X*1e3, color=C["truth"], lw=3.0, label="true displacement")
    ax.set_xlabel("time (s)"); ax.set_ylabel("displacement (mm)")
    ax.set_title("Integrate twice, naively: drifts $%.0f\\times$ off scale" % (np.abs(x_naive).max()/np.abs(X).max()))
    ax.legend(frameon=False, fontsize=12, loc="upper left")
    return _fin(fig, out)

def f_tuning(can, ks_v, ks_a, out="s_tuning.png"):
    fig, axs = plt.subplots(1, 2, figsize=SL)
    for ax, key, lab, ks in [(axs[0], "curve1", "velocity", ks_v),
                             (axs[1], "curve2", "acceleration", ks_a)]:
        for nm, col in [("Spectral (FFT)", C["spec"]), ("Savitzky-Golay", C["sg"]),
                        ("Whittaker (p=3)", C["whit"])]:
            r = can[nm]; ax.loglog(r["grid"], r[key], color=col, lw=2.6, label=nm)
        ax.axhline(ks, color=C["ks"], ls="--", lw=2.2)
        ax.set_xlabel("low-pass cutoff chosen (Hz)"); ax.set_ylabel(f"{lab} error (% rms)")
        ax.set_xticks([20, 50, 100, 200, 500]); ax.set_xticks([], minor=True)
        ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
        ax.set_title(f"{lab.capitalize()}: pick it wrong, pay an order of magnitude")
    axs[0].legend(frameon=False, fontsize=13, loc="upper center")
    axs[1].text(0.5, 0.06, "self-tuned state-space smoother (no knob)", transform=axs[1].transAxes,
                ha="center", fontsize=13)
    return _fin(fig, out)

def f_edges(t, V, xn, dt, kf, ks_v, out="s_edges.png"):
    fig, ax = plt.subplots(figsize=SL)
    sl = slice(len(t)-380, len(t))
    ax.plot(t[sl], V[sl], color=C["truth"], lw=3.4, label="true velocity")
    ax.plot(t[sl], kf["spec"][sl], color=C["spec"], lw=2.0, label="spectral (FFT)")
    ax.plot(t[sl], kf["whit"][sl], color=C["whit"], lw=2.0, label="Whittaker")
    ax.plot(t[sl], ks_v[sl], color=C["ks"], lw=1.8, ls="--", label="state-space smoother")
    ax.set_xlabel("time (s)"); ax.set_ylabel("velocity (m/s)")
    ax.set_title("The last 0.2 s of the record: the FFT has to make the signal periodic")
    ax.legend(frameon=False, fontsize=13, loc="upper left", ncol=2)
    return _fin(fig, out)

def f_impact(ti, Vi, cand, timp, key_tv, scores_txt, out="s_impact.png"):
    fig, axs = plt.subplots(1, 2, figsize=SL, gridspec_kw=dict(width_ratios=[1.35, 1]))
    ax = axs[0]; tm = timp[3]; m = np.abs(ti - tm) < 0.008
    ax.plot(ti[m], Vi[m], color=C["truth"], lw=3.6, label="true velocity", zorder=1)
    ax.plot(ti[m], cand[key_tv][m], color=C["tv"], lw=2.2, label="total variation (L1)")
    ax.plot(ti[m], cand["Whittaker fc=350"][m], color=C["whit"], lw=2.0, label="Whittaker (L2)")
    ax.plot(ti[m], cand["Spectral fc=350"][m], color=C["spec"], lw=1.8, label="spectral")
    ax.set_xlabel("time (s)"); ax.set_ylabel("velocity (m/s)")
    ax.set_title("Impact: the velocity genuinely jumps")
    ax.legend(frameon=False, fontsize=12, loc="lower right")
    ax = axs[1]
    names = [n for n, _ in scores_txt]; vals = [v for _, v in scores_txt]
    cols = [C["tv"], C["whit"], C["spec"], C["ks"]]
    b = ax.barh(range(len(vals)), vals, color=cols, height=0.62)
    ax.set_yticks(range(len(vals))); ax.set_yticklabels(names); ax.invert_yaxis()
    ax.set_xlabel("velocity error near impact (% rms)")
    ax.set_title("Error within $\\pm$4 ms of contact")
    for i, v in enumerate(vals):
        ax.text(v + 0.5, i, f"{v:.1f}", va="center", fontsize=13)
    ax.set_xlim(0, max(vals)*1.22)
    return _fin(fig, out)

def f_integration(t, X, an, dt, x_naive, x_tik, x_ks, out="s_integration.png"):
    fig, ax = plt.subplots(figsize=SL)
    ax.plot(t, X*1e3, color=C["truth"], lw=3.4, label="true displacement", zorder=3)
    ax.plot(t, x_tik*1e3, color=C["tik"], lw=1.9, label="Tikhonov, high-pass 4 Hz", zorder=4)
    ax.plot(t, x_ks*1e3, color=C["ks"], lw=1.6, ls="--", label="state-space smoother + bias state", zorder=5)
    ax2 = ax.twinx(); ax2.plot(t, x_naive*1e3, color=C["bad"], lw=2.0, zorder=1)
    ax2.set_ylabel("cumulative trapezoid (mm)", color="#808080"); ax2.tick_params(axis="y", colors="#808080")
    ax.set_xlabel("time (s)"); ax.set_ylabel("displacement (mm)")
    ax.set_title("Displacement from a drifting accelerometer (1% noise + 0.5% drift + 0.5% offset)", pad=26)
    ax.legend(frameon=False, fontsize=12, ncol=3, loc="lower left",
              bbox_to_anchor=(0.0, 1.005), borderaxespad=0.0)
    ax.text(0.985, 0.95, "plain cumulative trapezoid\n(right axis, $64\\times$ larger)", transform=ax.transAxes,
            ha="right", va="top", fontsize=12, color="#808080")
    return _fin(fig, out)

def f_fusion(vals, out="s_fusion.png"):
    fig, ax = plt.subplots(figsize=SL)
    labs = ["displacement", "velocity", "acceleration"]
    xs = np.arange(3); w = 0.26
    for i, (nm, col, v) in enumerate(vals):
        b = ax.bar(xs + (i-1)*w, v, w, label=nm, color=col)
        for xx, vv in zip(xs + (i-1)*w, v):
            ax.text(xx, vv + 0.18, f"{vv:.2f}", ha="center", fontsize=12)
    ax.set_xticks(xs); ax.set_xticklabels(labs); ax.set_ylabel("error (% rms)")
    ax.set_title("One smoother, two sensors: fusion beats either channel alone")
    ax.legend(frameon=False, fontsize=13, ncol=3, loc="upper left"); ax.set_ylim(0, 12.5)
    return _fin(fig, out)

def f_selftune(ratios, out="s_selftune.png"):
    fig, ax = plt.subplots(figsize=SL)
    noise = [0.1, 1.0, 5.0]; xs = np.arange(3); w = 0.2
    series = [("n=4, velocity", C["whit"]), ("n=4, acceleration", C["spec"]),
              ("n=5, velocity", C["tv"]), ("n=5, acceleration", C["acc"])]
    for i, (nm, col) in enumerate(series):
        v = ratios[nm]
        ax.bar(xs + (i-1.5)*w, v, w, label=nm, color=col)
        for xx, vv in zip(xs + (i-1.5)*w, v):
            ax.text(xx, vv + 0.05, f"{vv:.2f}", ha="center", fontsize=11)
    ax.axhline(1.0, color="k", lw=1.6, ls="--")
    ax.text(-0.42, 1.12, "parity with a perfectly tuned method", fontsize=12, ha="left")
    ax.set_xticks(xs); ax.set_xticklabels([f"{n}% position noise" for n in noise])
    ax.set_ylabel("error / best oracle-tuned error")
    ax.set_title("What self-tuning costs: most on clean data, nothing when it matters")
    ax.legend(frameon=False, fontsize=13, ncol=4, loc="upper right"); ax.set_ylim(0, 4.6)
    return _fin(fig, out)

def f_uncertainty(t, A, ks, out="s_uncertainty.png"):
    fig, ax = plt.subplots(figsize=SL)
    sl = slice(2400, 2900)
    est = ks["a"][sl]; sd = ks["std"][sl, 2]
    ax.fill_between(t[sl], est-2*sd, est+2*sd, color=C["whit"], alpha=0.28, label="$\\pm 2\\sigma$ posterior band")
    ax.plot(t[sl], est, color=C["whit"], lw=2.0, label="estimated acceleration")
    ax.plot(t[sl], A[sl], color=C["truth"], lw=2.6, ls="--", label="true acceleration")
    ax.set_xlabel("time (s)"); ax.set_ylabel("acceleration (m/s$^2$)")
    ax.set_title("The smoother reports its own uncertainty -- no other method here does")
    ax.legend(frameon=False, fontsize=13, loc="upper right")
    return _fin(fig, out)
