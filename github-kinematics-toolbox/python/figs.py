"""Figures for the differentiation / integration benchmark. Run inside the
kernel that holds the benchmark variables (see bench.py)."""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt

C = {"Spectral (FFT)": "#D95319", "Savitzky-Golay": "#808080",
     "Whittaker (p=3)": "#0072BD", "Smoothing spline": "#7E2F8E",
     "TV-regularised": "#77AC30", "kinsmooth": "#000000",
     "Trapz + detrend + HP": "#808080", "Tikhonov": "#0072BD",
     "truth": "#EDB120"}


def fig_int(ires, t, X, V, A, an, dt, kin, naive_x, rx, ra, rf, relerr,
            xslow, out="fig2_integration_fusion.png"):
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 5.4))

    # (a) displacement recovered from acceleration
    ax = axs[0, 0]
    ax.plot(t, X * 1e3, color=C["truth"], lw=2.4, label="true displacement", zorder=3)
    ax.plot(t, kin.int_tikhonov(an, dt, 2, fc=4.18) * 1e3, color=C["Tikhonov"],
            lw=1.0, label="Tikhonov, $f_c$ = 4 Hz", zorder=4)
    ax2 = ax.twinx()
    ax2.plot(t, naive_x * 1e3, color="#BFBFBF", lw=1.2, zorder=1)
    ax2.set_ylabel("naive result (mm)", color="#808080")
    ax2.tick_params(axis="y", colors="#808080")
    ax.set_xlabel("time (s)"); ax.set_ylabel("displacement (mm)")
    ax.set_title("Double integration without regularisation diverges")
    bb = dict(facecolor="white", alpha=0.8, edgecolor="none", pad=1.0)
    ax.text(0.02, 0.97, "true displacement", transform=ax.transAxes, va="top",
            fontsize=6, color="#9C7A0A", bbox=bb, zorder=12)
    ax.text(0.02, 0.88, "Tikhonov, $f_c$ = 4 Hz", transform=ax.transAxes, va="top",
            fontsize=6, color=C["Tikhonov"], bbox=bb, zorder=12)
    ax.text(0.60, 0.97, "plain cumulative trapezoid\n(right axis, $64\\times$ larger)",
            transform=ax.transAxes, ha="left", va="top", fontsize=6,
            color="#808080", bbox=bb, zorder=12)
    ax.margins(0.04)

    # (b) sensitivity to the high-pass corner
    ax = axs[0, 1]
    for name in ["Spectral (FFT)", "Trapz + detrend + HP", "Tikhonov"]:
        r = ires[name]
        ax.loglog(r["grid"], r["curve2"], color=C[name], lw=1.4, label=name)
    ax.set_xlabel("high-pass corner applied (Hz)")
    ax.set_ylabel("displacement error (% rms)")
    ax.set_xticks([0.5, 1, 2, 5, 10]); ax.set_xticks([], minor=True)
    ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
    ax.set_title("Every integrator needs a corner below the modes")
    ax.legend(frameon=False, fontsize=6, loc="upper right")
    ax.margins(0.04)

    # (c) fusion bars
    ax = axs[1, 0]
    labs = ["displacement\nonly", "acceleration\nonly", "fused"]
    cols = ["#7E2F8E", "#D95319", "#77AC30"]
    w = 0.26
    for i, (r, lab, col) in enumerate(zip([rx, ra, rf], labs, cols)):
        vals = [relerr(r["x"], X), relerr(r["v"], V), relerr(r["a"], A)]
        ax.bar(np.arange(3) + (i - 1) * w, vals, w, color=col, label=lab)
        for j, vv in enumerate(vals):
            ax.text(j + (i - 1) * w, vv + 0.12, f"{vv:.1f}", ha="center",
                    fontsize=5.5, color=col)
    ax.set_xticks(range(3)); ax.set_xticklabels(["displacement", "velocity", "acceleration"])
    ax.set_ylabel("error (% rms)")
    ax.set_title("Fusing both sensors beats either alone")
    ax.legend(frameon=False, fontsize=6, ncol=3, loc="upper center")
    ax.margins(0.04); ax.set_ylim(0, 12.5)

    # (d) fusion time trace
    ax = axs[1, 1]
    sl = slice(1200, 1500)
    ax.plot(t[sl], X[sl] * 1e3, color=C["truth"], lw=2.4, label="true displacement")
    m = np.isfinite(xslow[sl])
    ax.plot(t[sl][m], xslow[sl][m] * 1e3, "o", ms=2.6, color="#7E2F8E",
            label="displacement samples (200 Hz)")
    ax.plot(t[sl], rf["x"][sl] * 1e3, color="#77AC30", lw=1.1, label="fused estimate")
    ax.set_xlabel("time (s)"); ax.set_ylabel("displacement (mm)")
    ax.set_title("Acceleration fills in between displacement samples")
    ax.legend(frameon=False, fontsize=6, loc="upper right")
    ax.margins(0.04)

    import plotprefs as _tf
    _tf.latexify(fig)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    fig.savefig(out[:-4] + '.pdf')
    return fig


def fig_diff(res, ks_v, ks_a, t, V, A, xn, dt, kin,
             ti, Vi, cand, timp, out="fig1_differentiation.png"):
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 5.4))

    for ax, key, tru, lab in [(axs[0, 0], "curve1", V, "velocity"),
                              (axs[0, 1], "curve2", A, "acceleration")]:
        for name in ["Spectral (FFT)", "Savitzky-Golay", "Whittaker (p=3)"]:
            r = res[name]
            ax.loglog(r["grid"], r[key], color=C[name], lw=1.4, label=name)
        yv = ks_v if key == "curve1" else ks_a
        ax.axhline(yv, color="k", lw=1.2, ls="--")
        ax.set_xlabel("low-pass cutoff applied (Hz)")
        ax.set_ylabel(f"{lab} error (% rms)")
        ax.set_xticks([20, 50, 100, 200, 400])
        ax.set_xticks([], minor=True)
        ax.xaxis.set_major_formatter(mpl.ticker.ScalarFormatter())
        ax.margins(0.04)
    axs[0, 0].set_title("Velocity: every method has an optimum you must find")
    axs[0, 1].set_title("Acceleration: the optimum is sharper still")
    axs[0, 1].text(0.5, 0.10, "self-tuned state-space smoother (no knob)",
                   transform=axs[0, 1].transAxes, ha="center", va="bottom", fontsize=6)
    axs[0, 0].legend(frameon=False, loc="upper left", fontsize=6)

    # (c) record end
    ax = axs[1, 0]
    n = len(t); sl = slice(int(0.94 * n), n)
    ax.plot(t[sl], V[sl], color=C["truth"], lw=2.4, label="true velocity", zorder=1)
    for name, fn, fc in [("Spectral (FFT)", kin.diff_spectral, 72.2),
                         ("Whittaker (p=3)", kin.diff_whittaker, 72.2)]:
        ax.plot(t[sl], fn(xn, dt, 1, fc=fc)[sl], color=C[name], lw=1.2, label=name)
    ax.plot(t[sl], ks_curve[sl], color="k", lw=1.0, ls="--", label="state-space smoother")
    ax.set_xlabel("time (s)"); ax.set_ylabel("velocity (m/s)")
    ax.set_title("FFT differentiation fails at the record ends")
    ax.legend(frameon=False, fontsize=6, loc="lower left")
    ax.margins(0.04)

    # (d) impact
    ax = axs[1, 1]
    tm = timp[3]; m = np.abs(ti - tm) < 0.008
    ax.plot(ti[m], Vi[m], color=C["truth"], lw=2.4, label="true velocity", zorder=1)
    for k, col, lab in [("TV alpha=1e-05", C["TV-regularised"], "total-variation"),
                        ("Whittaker fc=350", C["Whittaker (p=3)"], "Whittaker"),
                        ("Spectral fc=350", C["Spectral (FFT)"], "spectral")]:
        ax.plot(ti[m], cand[k][m], color=col, lw=1.2, label=lab)
    ax.set_xlabel("time (s)"); ax.set_ylabel("velocity (m/s)")
    ax.set_title("At an impact, the L1 penalty tracks the jump best")
    ax.legend(frameon=False, fontsize=6, loc="lower right")
    ax.margins(0.04)
    import plotprefs as _tf
    _tf.latexify(fig)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    fig.savefig(out[:-4] + '.pdf')
    return fig
