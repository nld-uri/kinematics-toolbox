"""Benchmark of the delay-reconstruction methods (and the other additions of
October 2026) against the existing library, on exact ground truth.

    python bench_delay.py            -> prints tables, writes ../data/delay_benchmark.csv

Signals: the Duffing free decay of bench.py; a 3-DOF chain with a cubic
grounding spring (multimode, three sensors); a vibro-impact oscillator.
Oracle = knob swept against the truth; self = no truth used.
"""
import os, sys, csv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy.integrate import solve_ivp
import kinematics as kin
import bench

ROWS = []
def rec(task, method, tuning, metric, value, note=""):
    ROWS.append([task, method, tuning, metric, round(float(value), 4), note])

def pe(e, g, trim=0.05):
    k = int(trim * len(g)); s = slice(k, len(g) - k)
    return 100 * np.linalg.norm(e[s] - g[s]) / np.linalg.norm(g[s])

def oracle(fn, grid, tru):
    return min(pe(fn(g), tru) for g in grid)


def chain3(fs=2000.0, T=3.0, x0=(0, 0, 2e-3), zeta=0.005, beta_rel=0.4):
    """3-DOF chain (20 Hz unit springs), cubic grounding spring on mass 1."""
    k = (2 * np.pi * 20) ** 2
    K = k * np.array([[2, -1, 0], [-1, 2, -1], [0, -1, 1.0]])
    w, Phi = np.linalg.eigh(K); w = np.sqrt(w)
    C = Phi @ np.diag(2 * zeta * w) @ Phi.T
    beta = beta_rel * k / (1e-3) ** 2
    def f(t, y):
        x, v = y[:3], y[3:]
        return np.r_[v, -(K @ x + C @ v + np.array([beta * x[0] ** 3, 0, 0]))]
    dt = 1 / fs; t = np.arange(0, T, dt)
    s = solve_ivp(f, (0, T), np.r_[x0, 0, 0, 0], t_eval=t, rtol=1e-11, atol=1e-14, method="DOP853")
    X, V = s.y[:3].T, s.y[3:].T
    A = np.array([f(0, np.r_[X[i], V[i]])[3:] for i in range(len(t))])
    return t, dt, X, V, A


def vibroimpact(fs=2000.0, T=1.5, f0=15.0, zeta=0.01, x0=1e-3, gap=-0.6e-3, e=0.85):
    w0 = 2 * np.pi * f0; dt = 1 / fs; tg = np.arange(0, T, dt)
    rhs = lambda t, y: [y[1], -2 * zeta * w0 * y[1] - w0 ** 2 * y[0]]
    hit = lambda t, y: y[0] - gap; hit.terminal = True; hit.direction = -1
    t0, y0 = 0.0, [x0, 0.0]; Ts, Xs, Vs, timp = [], [], [], []
    while t0 < T:
        s = solve_ivp(rhs, (t0, T), y0, t_eval=tg[tg >= t0], events=hit,
                      rtol=1e-12, atol=1e-15, method="DOP853")
        Ts.append(s.t); Xs.append(s.y[0]); Vs.append(s.y[1])
        if s.status != 1:
            break
        tc, yc = s.t_events[0][0], s.y_events[0][0]
        timp.append(tc); t0 = tc + 1e-12; y0 = [gap, -e * yc[1]]
    t = np.concatenate(Ts); _, i = np.unique(t, return_index=True)
    return t[i], dt, np.concatenate(Xs)[i], np.concatenate(Vs)[i], np.array(timp)


def main():
    t, dt, X, V, A = bench.duffing()
    fcg = np.geomspace(20, 400, 40)
    print("\n== differentiate position (Duffing decay, seed 110): velocity / acceleration % rms")
    for pct in (0.1, 1.0, 5.0):
        xn = bench.noisy_position(X, dt, pct, np.random.default_rng(110))
        res = {
            "Spectral (FFT), oracle": (oracle(lambda f: kin.diff_spectral(xn, dt, 1, fc=f), fcg, V),
                                       oracle(lambda f: kin.diff_spectral(xn, dt, 2, fc=f), fcg, A)),
            "Whittaker p=3, oracle": (oracle(lambda f: kin.diff_whittaker(xn, dt, 1, fc=f), fcg, V),
                                      oracle(lambda f: kin.diff_whittaker(xn, dt, 2, fc=f), fcg, A)),
            "Smoothing spline, GCV": (pe(kin.diff_spline(xn, dt, 1), V), pe(kin.diff_spline(xn, dt, 2), A)),
        }
        r = kin.kinsmooth(t, x=xn, nstate=4)
        res["State-space n=4, self"] = (pe(r["v"], V), pe(r["a"], A))
        res["Delay SVD, self"] = (pe(kin.diff_delay(xn, dt, 1), V), pe(kin.diff_delay(xn, dt, 2), A))
        res["Delay SOD (in subspace), self"] = (pe(kin.diff_delay(xn, dt, 1, method="sod"), V),
                                                pe(kin.diff_delay(xn, dt, 2, method="sod"), A))
        for L in (161, 641):
            res[f"Delay SOD full, L={L}"] = (pe(kin.diff_delay(xn, dt, 1, L=L, method="sod_full"), V),
                                            pe(kin.diff_delay(xn, dt, 2, L=L, method="sod_full"), A))
        print(f"  {pct}% noise")
        for k, (ev, ea) in res.items():
            print(f"    {k:34s} {ev:7.3f} / {ea:7.3f}")
            tun = "oracle" if "oracle" in k else ("GCV" if "GCV" in k else "self")
            rec("differentiate position", k, tun, "velocity error % rms", ev, f"{pct}% noise, seed 110")
            rec("differentiate position", k, tun, "acceleration error % rms", ea, f"{pct}% noise, seed 110")

    print("\n== integrate acceleration (1% white + 0.5% drift + 0.5% offset): displacement / velocity")
    for seed in (7, 11):
        an = bench.noisy_acceleration(A, dt, 1.0, np.random.default_rng(seed))
        g = np.geomspace(0.5, 15, 30)
        res = {
            "Tikhonov, oracle": (oracle(lambda f: kin.int_tikhonov(an, dt, 2, fc=f), g, X),
                                 oracle(lambda f: kin.int_tikhonov(an, dt, 1, fc=f), g, V)),
            "Spectral, oracle": (oracle(lambda f: kin.int_spectral(an, dt, 2, fc=f), g, X),
                                 oracle(lambda f: kin.int_spectral(an, dt, 1, fc=f), g, V)),
        }
        r = kin.kinsmooth(t, a=an, nstate=4, bias=True, hp=4.0)
        res["State-space (self q, hp=4)"] = (pe(r["x"], X), pe(r["v"], V))
        res["Delay SOD, fc=4"] = (pe(kin.int_delay(an, dt, 2), X), pe(kin.int_delay(an, dt, 1), V))
        res["Delay SVD, fc=4"] = (pe(kin.int_delay(an, dt, 2, method="svd"), X),
                                  pe(kin.int_delay(an, dt, 1, method="svd"), V))
        print(f"  seed {seed}")
        for k, (ex, ev) in res.items():
            print(f"    {k:34s} {ex:7.3f} / {ev:7.3f}")
            tun = "oracle" if "oracle" in k else "fc=4 Hz"
            rec("integrate acceleration", k, tun, "displacement error % rms", ex, f"seed {seed}")
            rec("integrate acceleration", k, tun, "velocity error % rms", ev, f"seed {seed}")

    print("\n== multimode, 3 sensors (3-DOF chain, 1% noise): velocity / acceleration per channel")
    t3, dt3, X3, V3, A3 = chain3()
    Xn = X3 + 0.01 * X3.std(0) * np.random.default_rng(5).standard_normal(X3.shape)
    single = [kin.diff_delay(Xn[:, j], dt3, 1) for j in range(3)]
    singlea = [kin.diff_delay(Xn[:, j], dt3, 2) for j in range(3)]
    mv, ma = kin.diff_delay(Xn, dt3, 1, L=213), kin.diff_delay(Xn, dt3, 2, L=213)
    for j in range(3):
        wv = oracle(lambda f: kin.diff_whittaker(Xn[:, j], dt3, 1, fc=f), fcg, V3[:, j])
        wa = oracle(lambda f: kin.diff_whittaker(Xn[:, j], dt3, 2, fc=f), fcg, A3[:, j])
        r = kin.kinsmooth(t3, x=Xn[:, j], nstate=4)
        res = {"Whittaker p=3, oracle": (wv, wa), "State-space n=4, self": (pe(r["v"], V3[:, j]), pe(r["a"], A3[:, j])),
               "Delay SVD, one channel": (pe(single[j], V3[:, j]), pe(singlea[j], A3[:, j])),
               "Delay SVD, 3 channels (L=213)": (pe(mv[:, j], V3[:, j]), pe(ma[:, j], A3[:, j]))}
        print(f"  channel {j + 1}")
        for k, (ev, ea) in res.items():
            print(f"    {k:34s} {ev:7.3f} / {ea:7.3f}")
            rec("multimode, 3 sensors", k, "oracle" if "oracle" in k else "self",
                f"channel {j + 1} velocity error % rms", ev, "1% noise, seed 5")
            rec("multimode, 3 sensors", k, "oracle" if "oracle" in k else "self",
                f"channel {j + 1} acceleration error % rms", ea, "1% noise, seed 5")

    print("\n== vibro-impact (0.5% noise): velocity error within +/-4 ms of impacts / whole record")
    ti, dti, Xi, Vi, timp = vibroimpact()
    xi = Xi + 0.005 * Xi.std() * np.random.default_rng(3).standard_normal(len(Xi))
    mask = np.zeros(len(ti), bool)
    for tc in timp:
        mask |= np.abs(ti - tc) <= 0.004
    loc = lambda e: 100 * np.linalg.norm(e[mask] - Vi[mask]) / np.linalg.norm(Vi[mask])
    sd = xi.std()
    res = {"Total variation, alpha=1e-5": kin.diff_tvreg(xi / sd, dti, 1e-5) * sd,
           "Whittaker fc=350": kin.diff_whittaker(xi, dti, 1, fc=350),
           "State-space n=4, self": kin.kinsmooth(ti, x=xi, nstate=4)["v"],
           "Delay SVD, self": kin.diff_delay(xi, dti, 1)}
    for k, v in res.items():
        print(f"    {k:34s} {loc(v):7.2f} / {pe(v, Vi):7.2f}")
        rec("vibro-impact", k, "self" if "self" in k else "fixed", "velocity error % rms near impacts", loc(v),
            f"+/-4 ms, {len(timp)} impacts, 0.5% noise, seed 3")

    print("\n== causal (online) differentiation, 1% noise seed 110: velocity / acceleration")
    xn = bench.noisy_position(X, dt, 1.0, np.random.default_rng(110))
    Lg = np.geomspace(1e2, 1e5, 31)
    lev = (oracle(lambda L: kin.diff_levant(xn, dt, L, 1, zero_phase=False), Lg, V),
           oracle(lambda L: kin.diff_levant(xn, dt, L, 2, zero_phase=False), Lg, A))
    rc = kin.kinsmooth(t, x=xn, nstate=4, causal=True)
    for k, (ev, ea) in {"Levant, oracle L": lev, "Kalman filter n=4, self": (pe(rc["v"], V), pe(rc["a"], A))}.items():
        print(f"    {k:34s} {ev:7.3f} / {ea:7.3f}")
        rec("causal differentiation", k, "oracle" if "oracle" in k else "self", "velocity error % rms", ev, "1% noise, seed 110")
        rec("causal differentiation", k, "oracle" if "oracle" in k else "self", "acceleration error % rms", ea, "1% noise, seed 110")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "delay_benchmark.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["task", "method", "tuning", "metric", "value", "note"]); w.writerows(ROWS)
    print("\nwrote", os.path.normpath(out))


if __name__ == "__main__":
    main()
