"""Regenerate the nine original talk figures (s_*.png/pdf) in the NLD palette.

    python make_slide_figs.py        -> ../figures/s_{illposed,naive,tuning,edges,
                                        impact,integration,fusion,selftune,uncertainty}

Inputs are rebuilt from bench.py (Duffing decay, seeds 110 and 7) so every
curve is reproducible.  The bar charts for fusion and self-tuning cost plot the
tabulated values in README.md.  The vibro-impact record comes from
bench_delay.vibroimpact; the generator behind the earlier impact figure is not
in the repository, so its near-impact numbers differ (see README).
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
import bench_delay
import figs_slides as fs

pp.apply_preferences(sizes=(17, 15, 13))
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False})
OUT = os.path.join(HERE, "..", "figures")
C = fs.C


def out(name):
    return os.path.join(OUT, name + ".png")


def ctrap(y, dt):
    c = np.zeros_like(y)
    c[1:] = np.cumsum(0.5 * (y[1:] + y[:-1])) * dt
    return c


def main():
    t, dt, X, V, A = bench.duffing()
    xn = bench.noisy_position(X, dt, 1.0, np.random.default_rng(110))
    an = bench.noisy_acceleration(A, dt, 1.0, np.random.default_rng(7))
    x_naive = ctrap(ctrap(an, dt), dt)
    ks = kin.kinsmooth(t, x=xn, nstate=4)

    fs.f_illposed(t, dt, X, xn, A, out=out("s_illposed"))
    fs.f_naive(t, dt, X, V, xn, an, A, x_naive, out=out("s_naive"))

    grid = np.geomspace(15, 600, 30)
    can = {
        "Spectral (FFT)": bench.sweep(lambda f: (kin.diff_spectral(xn, dt, 1, fc=f),
                                                 kin.diff_spectral(xn, dt, 2, fc=f)), grid, V, A),
        "Savitzky-Golay": bench.sweep(lambda f: (kin.diff_savgol(xn, dt, 1, fc=f),
                                                 kin.diff_savgol(xn, dt, 2, fc=f)), grid, V, A),
        "Whittaker (p=3)": bench.sweep(lambda f: (kin.diff_whittaker(xn, dt, 1, fc=f),
                                                  kin.diff_whittaker(xn, dt, 2, fc=f)), grid, V, A),
    }
    fs.f_tuning(can, bench.relerr(ks["v"], V), bench.relerr(ks["a"], A), out=out("s_tuning"))

    kf = {"spec": kin.diff_spectral(xn, dt, 1, fc=69.76), "whit": kin.diff_whittaker(xn, dt, 1, fc=81.35)}
    fs.f_edges(t, V, xn, dt, kf, ks["v"], out=out("s_edges"))

    ti, dti, Xi, Vi, timp = bench_delay.vibroimpact()
    xi = Xi + 0.005 * Xi.std() * np.random.default_rng(3).standard_normal(len(Xi))
    sd = xi.std()
    cand = {"TV alpha=1e-5": kin.diff_tvreg(xi / sd, dti, 1e-5) * sd,
            "Whittaker fc=350": kin.diff_whittaker(xi, dti, 1, fc=350),
            "Spectral fc=350": kin.diff_spectral(xi, dti, 1, fc=350),
            "kinsmooth": kin.kinsmooth(ti, x=xi, nstate=4)["v"]}
    mask = np.zeros(len(ti), bool)
    for tc in timp:
        mask |= np.abs(ti - tc) <= 0.004
    loc = lambda e: 100 * np.linalg.norm(e[mask] - Vi[mask]) / np.linalg.norm(Vi[mask])
    scores = [("total variation", loc(cand["TV alpha=1e-5"])), ("Whittaker", loc(cand["Whittaker fc=350"])),
              ("spectral", loc(cand["Spectral fc=350"])), ("state-space", loc(cand["kinsmooth"]))]
    print("impact scores", scores)
    fs.f_impact(ti, Vi, cand, timp, "TV alpha=1e-5", scores, out=out("s_impact"))

    x_tik = kin.int_tikhonov(an, dt, 2, fc=4.0)
    x_ks = kin.kinsmooth(t, a=an, nstate=4, bias=True, hp=4.0)["x"]
    print("naive drift ratio", np.abs(x_naive).max() / np.abs(X).max())
    fs.f_integration(t, X, an, dt, x_naive, x_tik, x_ks, out=out("s_integration"))

    fs.f_fusion([("displacement only", C["acc"], [2.212, 3.864, 9.981]),
                 ("acceleration only", C["spec"], [1.721, 1.604, 1.829]),
                 ("fused", C["tv"], [1.285, 1.146, 1.668])], out=out("s_fusion"))
    fs.f_selftune({"n=4, velocity": [2.28, 1.54, 1.02], "n=4, acceleration": [3.74, 2.19, 1.11],
                   "n=5, velocity": [2.14, 1.80, 1.46], "n=5, acceleration": [1.91, 1.61, 1.24]},
                  out=out("s_selftune"))
    fs.f_uncertainty(t, A, ks, out=out("s_uncertainty"))
    plt.close("all")


if __name__ == "__main__":
    main()
