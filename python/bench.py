"""Benchmark of model-free differentiators / integrators on a Duffing free decay.

Ground truth comes from a tight ODE solve, so every reported error is a true
error, not a comparison against another estimate.  Each method's single knob is
swept and the ORACLE minimum is reported -- the best that method could do if you
tuned it perfectly.  kinsmooth is reported self-tuned (marginal likelihood, no
oracle) so it can be compared against everyone else's best case.
"""
import os, sys, time
sys.path.append(os.getcwd())
import numpy as np
from scipy.integrate import solve_ivp
from scipy import signal as sig
import kinematics as kin


# ------------------------------------------------------------------ truth
def duffing(fs=2000.0, T=3.0, f0=15.0, zeta=0.004, x0=1e-3, shift=0.25):
    w0 = 2 * np.pi * f0
    beta = ((1 + shift) ** 2 - 1) / 0.75 * w0 ** 2 / x0 ** 2
    fun = lambda t, y: [y[1], -2 * zeta * w0 * y[1] - w0 ** 2 * y[0] - beta * y[0] ** 3]
    dt = 1 / fs
    t = np.arange(0, T, dt)
    s = solve_ivp(fun, (0, T), [x0, 0.0], t_eval=t, rtol=1e-12, atol=1e-15,
                  method="DOP853")
    X, V = s.y
    A = -2 * zeta * w0 * V - w0 ** 2 * X - beta * X ** 3
    return t, dt, X, V, A


def relerr(est, tru, trim=0.05):
    k = int(trim * len(tru))
    s = slice(k, len(tru) - k)
    return 100 * np.sqrt(np.mean((est[s] - tru[s]) ** 2)) / np.sqrt(np.mean(tru[s] ** 2))


def sweep(fn, grid, tru1, tru2):
    """Run fn(knob) -> (d1, d2); return best errors, best knobs, robustness."""
    e1, e2 = [], []
    for g in grid:
        try:
            d1, d2 = fn(g)
            e1.append(relerr(d1, tru1)); e2.append(relerr(d2, tru2))
        except Exception:
            e1.append(np.inf); e2.append(np.inf)
    e1, e2 = np.array(e1), np.array(e2)
    i1, i2 = int(np.argmin(e1)), int(np.argmin(e2))
    # robustness: decades of knob within 2x of the optimum (1st derivative)
    ok = e1 <= 2 * e1[i1]
    g = np.asarray(grid, float)
    span = np.log10(g[ok].max() / g[ok].min()) if ok.sum() > 1 else 0.0
    return dict(e1=e1[i1], e2=e2[i2], k1=g[i1], k2=g[i2], span=span,
                curve1=e1, curve2=e2, grid=g)


# ------------------------------------------------------- noise generators
def noisy_position(X, dt, pct, rng):
    return X + pct / 100 * X.std() * rng.standard_normal(len(X))


def noisy_acceleration(A, dt, pct, rng, drift_pct=0.5, offset_pct=0.5, fdrift=0.7):
    n = len(A)
    white = pct / 100 * A.std() * rng.standard_normal(n)
    b, a = sig.butter(2, fdrift / (0.5 / dt))
    drift = sig.lfilter(b, a, rng.standard_normal(n))
    drift = drift / drift.std() * drift_pct / 100 * A.std()
    return A + white + drift + offset_pct / 100 * A.std()
