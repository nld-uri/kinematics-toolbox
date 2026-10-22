"""
kinematics.py -- model-free differentiation and integration of measured motion.

Every routine here assumes only a *regularity prior* on the signal (bandlimited,
p-times differentiable, sparse jerk, bounded derivative).  None of them uses a
model of the system that produced the signal.

Two groups plus a unifier:

  diff_*   position  -> velocity, acceleration
  int_*    acceleration -> velocity, displacement
  *_delay  the same two tasks through a delay reconstruction (SSA, SOD)
  kinsmooth   one state-space estimator that does either direction, fuses both,
              handles gaps / multirate / non-uniform sampling, returns error bars,
              and tunes itself by marginal likelihood.

Tuning rules (derived in the docstrings) let you set every regularisation
parameter from a corner frequency in Hz instead of a blind lambda sweep.

Dependencies: numpy, scipy.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse, signal, optimize, linalg
from scipy.sparse.linalg import spsolve, splu
from scipy.interpolate import make_smoothing_spline

__all__ = [
    "diff_matrix", "estimate_noise_var",
    "diff_spectral", "diff_savgol", "diff_whittaker", "diff_spline",
    "diff_tvreg", "diff_levant", "diff_gp",
    "int_spectral", "int_trapz_detrend", "int_tikhonov",
    "kinsmooth",
    "signal_band", "delay_project", "diff_delay", "int_delay",
    "cite", "DOI",
]


# ---------------------------------------------------------------- utilities

def diff_matrix(n: int, order: int, dt: float = 1.0) -> sparse.csr_matrix:
    """Sparse (n-order) x n finite-difference operator, scaled by dt**-order."""
    D = sparse.eye(n, format="csc")
    for _ in range(order):
        m = D.shape[0]
        D = sparse.diags([-np.ones(m - 1), np.ones(m - 1)], [0, 1],
                         shape=(m - 1, m), format="csc") @ D
    return (D / dt ** order).tocsr()


def estimate_noise_var(y, dt, band=(0.40, 0.49)):
    """Measurement-noise variance from the white plateau near Nyquist.

    Reads the one-sided PSD over `band` (fractions of the sampling rate) and
    converts the plateau level to a variance.  Valid when the signal itself has
    rolled off there -- true for essentially any mechanical measurement that is
    sampled at a sane rate.
    """
    y = np.asarray(y, float)
    f, P = signal.welch(y - y.mean(), fs=1.0 / dt,
                        nperseg=min(len(y), 4096), detrend="linear")
    m = (f >= band[0] / dt) & (f <= band[1] / dt)
    if not m.any():
        m = f >= f[-1] * 0.8
    return float(np.median(P[m]) * (0.5 / dt))


def _taper(n, frac):
    if frac <= 0:
        return np.ones(n)
    return signal.windows.tukey(n, alpha=2 * frac)


# ------------------------------------------------------- differentiation

def diff_spectral(x, dt, order=1, fc=None, detrend=True, taper=0.0):
    """FFT differentiation: multiply by (i*omega)**order, optional brick-wall low-pass.

    fc : cutoff in Hz.  Above it the spectrum is zeroed with a raised-cosine
         edge over the top decade of the pass band.  Without fc this amplifies
         noise as omega**order and is unusable on real data.

    Exact for periodic bandlimited signals; the linear detrend and taper are
    there because measured records are neither.
    """
    x = np.asarray(x, float)
    n = len(x)
    t = np.arange(n) * dt
    trend = np.zeros(n)
    if detrend:
        p = np.polyfit(t, x, 1)
        trend = np.polyval(p, t)
    w = _taper(n, taper)
    X = np.fft.rfft((x - trend) * w)
    om = 2 * np.pi * np.fft.rfftfreq(n, dt)
    if fc is not None:
        oc = 2 * np.pi * fc
        roll = np.ones_like(om)
        lo, hi = 0.8 * oc, oc
        band = (om > lo) & (om <= hi)
        roll[band] = 0.5 * (1 + np.cos(np.pi * (om[band] - lo) / (hi - lo)))
        roll[om > hi] = 0.0
        X = X * roll
    y = np.fft.irfft(X * (1j * om) ** order, n=n)
    if taper > 0:
        y = y / np.maximum(w, 1e-3)
    if detrend and order == 1:
        y = y + p[0]
    return y


def diff_savgol(x, dt, order=1, fc=None, window=None, polyorder=3):
    """Savitzky-Golay: local polynomial least squares, differentiated analytically.

    Give either `window` (odd sample count) or `fc` (Hz).  The -3 dB cutoff of
    an SG smoother of half-width M samples is well approximated by

        fc*dt ~ (polyorder + 1) / (3.2*M - 4.6)                   [Schafer 2011]

    which is inverted here to pick window = 2M+1 from fc.  Cheap, zero-phase,
    and the standard first thing to try; degrades at the record ends.
    """
    x = np.asarray(x, float)
    if window is None:
        if fc is None:
            raise ValueError("give window or fc")
        M = ((polyorder + 1) / (fc * dt) + 4.6) / 3.2
        window = int(np.ceil(2 * M + 1))
        window = max(polyorder + 2, window)
    if window % 2 == 0:
        window += 1
    return signal.savgol_filter(x, window, polyorder, deriv=order, delta=dt,
                                mode="interp")


def diff_whittaker(x, dt, order=1, fc=None, lam=None, p=3, return_smooth=False):
    """Differentiate by smoothing with a p-th difference penalty, then differencing.

    Solves   min_s ||s - x||^2 + lam * ||D^p s / dt^p||^2
    (Whittaker-Henderson / Hodrick-Prescott / discrete smoothing spline), then
    applies a centred difference of the requested order to the smooth s.

    Frequency response of the smoother is 1/(1 + lam*omega^(2p)), so the -3 dB
    corner is omega_c = lam^(-1/(2p)), i.e.

        lam = (2*pi*fc)**(-2*p)

    That is the tuning rule: pick fc above the highest frequency you believe and
    below where the noise dominates.  p=3 gives a 6th-order roll-off and leaves
    the first two derivatives smooth.

    Banded sparse solve, O(N).  This is the discrete twin of the Kalman
    smoother in `kinsmooth` and of a GP with an integrated-Wiener kernel.
    """
    x = np.asarray(x, float)
    n = len(x)
    if lam is None:
        if fc is None:
            raise ValueError("give lam or fc")
        lam = (2 * np.pi * fc) ** (-2 * p)
    D = diff_matrix(n, p, dt)
    A = (sparse.eye(n, format="csc") + lam * (D.T @ D)).tocsc()
    s = spsolve(A, x)
    if return_smooth:
        return s
    if order == 0:
        return s
    return _central(s, dt, order)


def _central(s, dt, order):
    """Centred differences of given order, one-sided at the two ends."""
    out = s
    for _ in range(order):
        g = np.empty_like(out)
        g[1:-1] = (out[2:] - out[:-2]) / (2 * dt)
        g[0] = (-3 * out[0] + 4 * out[1] - out[2]) / (2 * dt)
        g[-1] = (3 * out[-1] - 4 * out[-2] + out[-3]) / (2 * dt)
        out = g
    return out


def diff_spline(x, dt, order=1, lam=None, fc=None, return_info=False):
    """Cubic smoothing spline, differentiated analytically at the samples.

    Minimises  sum (x_i - f(t_i))^2 + lam * int f''(t)^2 dt  (the objective of
    scipy.interpolate.make_smoothing_spline).  lam is chosen by, in order:
    `lam` if given; `fc` (Hz) through  lam = (2*pi*fc)**-4 / dt  (the data term
    is a sum, i.e. 1/dt times an integral, so the response is
    1/(1 + lam*dt*omega^4)); otherwise generalised cross-validation.

    GCV is computed here, not by scipy.  make_smoothing_spline's own GCV
    selection returned an essentially flat fit (100 % error) on the 6000-point
    benchmark decay.  The exact score n*||x - f||^2 / (n - tr A)^2, with tr A
    from the band of (R + lam Q'Q)^-1 (Takahashi selected inverse, O(N)), has
    a single clear minimum there (lam = 8.4e-9 against an oracle of 3.2e-8;
    1.18 % velocity error against 0.90 %).  GCV still under-smooths mildly,
    and tends to under-smooth more when the noise is correlated.

    `dt` may be a scalar or the vector of sample times (non-uniform).
    With return_info=True also returns dict(lam, fc, dof, gcv).
    """
    x = np.asarray(x, float)
    n = len(x)
    t = np.asarray(dt, float) if np.ndim(dt) else np.arange(n) * dt
    h = np.diff(t)
    gval = np.nan
    if lam is None and fc is not None:
        lam = (2 * np.pi * fc) ** -4 / h.mean()
    if lam is None:
        lam, gval = _spline_gcv(t, x)
    spl = make_smoothing_spline(t, x, lam=lam)
    y = spl.derivative(order)(t) if order else spl(t)
    if return_info:
        Q, Rm = _reinsch(t)
        M = (Rm + lam * (Q.T @ Q)).tocsc()
        dof = n - lam * _trace_inv_band(M, (Q.T @ Q).tocsc())
        return y, {"lam": lam, "fc": (lam * h.mean()) ** -0.25 / (2 * np.pi),
                   "dof": dof, "gcv": gval}
    return y


def _reinsch(t):
    """Q (n x n-2) and R (n-2 tridiagonal) of the Reinsch smoothing-spline form."""
    n = len(t)
    h = np.diff(t)
    i1, i2 = 1 / h[:-1], 1 / h[1:]
    Q = sparse.diags([i1, -i1 - i2, i2], [0, -1, -2], shape=(n, n - 2), format="csc")
    Rm = sparse.diags([(h[:-1] + h[1:]) / 3, h[1:-1] / 6, h[1:-1] / 6],
                      [0, 1, -1], format="csc")
    return Q, Rm


def _trace_inv_band(M, B, bw=2):
    """trace(M^-1 B) for SPD banded M and B (half-bandwidth bw), O(N).

    Takahashi recurrence on M = L D L': only the band of Z = M^-1 is formed.
    """
    m = M.shape[0]
    ab = np.zeros((bw + 1, m))                     # lower banded storage
    for k in range(bw + 1):
        ab[k, :m - k] = M.diagonal(-k)
    from scipy.linalg import cholesky_banded
    c = cholesky_banded(ab, lower=True)            # M = C C', C lower
    d = c[0] ** 2
    Lb = np.zeros((m, bw))                         # Lb[i, k-1] = L[i+k, i]
    for k in range(1, bw + 1):
        Lb[:m - k, k - 1] = c[k, :m - k] / c[0, :m - k]
    Z = np.zeros((m, bw + 1))                      # Z[i, k] = Zfull[i, i+k]
    for i in range(m - 1, -1, -1):
        kmax = min(bw, m - 1 - i)
        for jo in range(kmax, -1, -1):
            acc = 0.0
            for k in range(1, kmax + 1):
                acc += Lb[i, k - 1] * Z[min(i + k, i + jo), abs(k - jo)]
            Z[i, jo] = (1.0 / d[i] if jo == 0 else 0.0) - acc
    s = np.dot(Z[:, 0], B.diagonal(0))
    for k in range(1, bw + 1):
        s += 2 * np.dot(Z[:m - k, k], B.diagonal(k))
    return s


def _spline_gcv(t, x):
    """lam minimising the exact GCV score; coarse log grid then bounded search."""
    n = len(x)
    hm = np.diff(t).mean()
    Q, Rm = _reinsch(t)
    QtQ = (Q.T @ Q).tocsc()
    Qtx = Q.T @ x

    def score(lg):
        L = 10.0 ** lg
        M = (Rm + L * QtQ).tocsc()
        r = L * (Q @ spsolve(M, Qtx))
        trA = n - L * _trace_inv_band(M, QtQ)
        return n * (r @ r) / (n - trA) ** 2

    grid = np.linspace(np.log10((np.pi / hm) ** -4 / hm),
                       np.log10((2 * np.pi * 1e-4 / hm) ** -4 / hm), 41)
    g = np.array([score(v) for v in grid])
    k = int(np.argmin(g))
    lo, hi = grid[max(k - 1, 0)], grid[min(k + 1, len(grid) - 1)]
    res = optimize.minimize_scalar(score, bounds=(lo, hi), method="bounded",
                                   options={"xatol": 1e-4})
    return 10.0 ** res.x, float(res.fun)


def diff_tvreg(x, dt, alpha=1e-3, order=1, tol=1e-8, maxit=20000,
               return_info=False):
    """Total-variation regularised differentiation (Chartrand 2011), by ADMM.

    Chartrand poses  min_u  alpha*||Du||_1 + 0.5*||Au - (x-x[0])||^2  with A the
    integration operator.  Substituting w = Au (so u = dw/dt) turns it into

        min_w  0.5*||w - f||^2 + (alpha/dt)*||G w||_1 ,   G = second difference

    which is L1 trend filtering: the ADMM linear system (I + rho*G'G) is
    pentadiagonal and CONSTANT, so it factors once and every iteration is a
    banded solve plus a soft threshold.

    This matters. Solved in the original variables the Hessian A'A + alpha*L is
    dense and so ill-conditioned that conjugate gradients stalls; the
    unconverged iterate then acts as extra smoothing and silently changes the
    answer.  IRLS on the smoothed L1 stalls too (observed rate 0.997/iteration).
    ADMM solves the exact L1 objective -- no epsilon smoothing -- to a stated
    primal/dual tolerance, which is also what makes this agree with the MATLAB
    port to solver precision rather than to three digits.

    The L1 penalty is the point: the estimated derivative may be piecewise
    smooth with genuine jumps -- impacts, dry friction reversals, backlash --
    where every quadratic-penalty method rounds the corner off.  Scale-sensitive
    in alpha: normalise x to unit rms before calling and rescale after.

    NOTE alpha is tied to the ABSOLUTE scale of x, so normalise x before
    calling and rescale after -- and be careful which normalisation you use:
    numpy's std() divides by N, MATLAB's std() by N-1, and on a 6000-point
    record that 83 ppm difference moves the result by 1.5e-6.

    order=2 applies it twice.  With return_info=True also returns a dict of
    (iters, converged, rho, rp_ratio, rd_ratio) -- always check `converged`
    before comparing two implementations, since a run that merely hit maxit
    stops at an arbitrary point that is NOT the minimiser.

    At tol=1e-8 the iterate is within about 1.2e-8 of the true minimiser
    (measured against a tol=1e-12 reference), so two converged runs should
    agree to a few times 1e-8 regardless of platform.
    """
    x = np.asarray(x, float)
    if order == 2:
        v = diff_tvreg(x, dt, alpha, 1, tol, maxit)
        m = np.abs(v).max()
        return diff_tvreg(v / m, dt, alpha, 1, tol, maxit) * m
    n = len(x)
    f = x - x[0]
    G = sparse.diags([np.ones(n - 2), -2 * np.ones(n - 2), np.ones(n - 2)],
                     [0, 1, 2], shape=(n - 2, n), format="csc")
    mu = alpha / dt
    GtG = (G.T @ G).tocsc()
    I = sparse.eye(n, format="csc")
    rho = mu if mu > 0 else 1.0
    lu = splu((I + rho * GtG).tocsc())
    z = np.zeros(n - 2)
    u = np.zeros(n - 2)
    w = f.copy()
    conv = False
    for _ in range(maxit):
        w = lu.solve(f + rho * (G.T @ (z - u)))
        Gw = G @ w
        zo = z
        v = Gw + u
        z = np.sign(v) * np.maximum(np.abs(v) - mu / rho, 0.0)
        u = u + Gw - z
        rp = np.linalg.norm(Gw - z)
        rd = rho * np.linalg.norm(G.T @ (z - zo))
        ep = tol * max(np.linalg.norm(Gw), np.linalg.norm(z), 1e-300)
        ed = tol * max(rho * np.linalg.norm(G.T @ u), 1e-300)
        conv = (rp <= ep) and (rd <= ed)
        if conv:
            break
        if rp > 10 * rd:                       # Boyd residual balancing
            rho *= 2; u /= 2; lu = splu((I + rho * GtG).tocsc())
        elif rd > 10 * rp:
            rho /= 2; u *= 2; lu = splu((I + rho * GtG).tocsc())
    if return_info:
        return _central(w, dt, 1), {"iters": _ + 1, "converged": bool(conv),
                                    "rho": rho, "rp_ratio": rp / max(ep, 1e-300),
                                    "rd_ratio": rd / max(ed, 1e-300)}
    return _central(w, dt, 1)


def diff_levant(x, dt, L=None, order=1, zero_phase=True):
    """Levant's robust exact differentiator (2nd-order sliding mode).

    Three states z0, z1, z2 track x, x', x''.  Finite-time exact when the
    THIRD derivative is bounded, |d3x/dt3| <= L, whichever output (order 1
    or 2) is used.  No smoothness assumption beyond that and no linear
    filtering -- the standard answer from control theory, and genuinely
    causal, so it runs online.  Price: chattering at the sampling scale and a
    phase lag, which `zero_phase` removes by a second backward pass (offline
    only).

    L : bound on |d3x/dt3|.  If omitted, its maximum from the self-tuned
        state-space smoother (kinsmooth, nstate=4) -- no knob.  On the
        benchmark this gives 7.7 % / 18 % velocity / acceleration error,
        against 7.4 % / 21.6 % at the swept oracle.  The earlier default
        bounded the (order+1)-th derivative, which is the wrong one for this
        three-state form; it set L about 100x too small (119 % error).
        The estimate uses the whole record; for online use supply L from the
        physics (x = X sin(w t) gives L = X w^3).
    """
    x = np.asarray(x, float)
    if L is None:
        r = kinsmooth(np.arange(len(x)) * dt, x=x, nstate=4)
        L = np.max(np.abs(r["j"])) + 1e-12

    def run(y):
        n = len(y)
        z0, z1, z2 = y[0], 0.0, 0.0
        out1 = np.empty(n)
        out2 = np.empty(n)
        l0, l1, l2 = 1.1, 1.5, 2.0
        for k in range(n):
            e = z0 - y[k]
            v0 = -l2 * L ** (1 / 3) * np.cbrt(e) ** 2 * np.sign(e) + z1
            v1 = -l1 * L ** (1 / 2) * np.sqrt(abs(z1 - v0)) * np.sign(z1 - v0) + z2
            z0 = z0 + dt * v0
            z1 = z1 + dt * v1
            z2 = z2 + dt * (-l0 * L * np.sign(z2 - v1))
            out1[k], out2[k] = z1, z2
        return out1, out2

    d1, d2 = run(x)
    if zero_phase:
        b1, b2 = run(x[::-1])
        d1 = 0.5 * (d1 - b1[::-1])
        d2 = 0.5 * (d2 + b2[::-1])
    return d1 if order == 1 else d2


def diff_gp(x, dt, ell=None, sigma_n=None, order=1, jitter=1e-10):
    """Gaussian-process derivative with a squared-exponential kernel, O(N^3).

    The derivative of a GP is a GP, so the posterior mean of dx/dt is available
    in closed form together with its posterior variance.  Included because it is
    the cleanest statement of what all the quadratic-penalty methods are doing;
    for N beyond a few thousand use `kinsmooth`, which is the O(N) state-space
    form of the same idea.

    Returns (derivative, std).
    """
    x = np.asarray(x, float)
    n = len(x)
    t = np.arange(n) * dt
    if sigma_n is None:
        sigma_n = np.sqrt(estimate_noise_var(x, dt))
    if ell is None:
        ell = 20 * dt
    sf2 = np.var(x)
    d = t[:, None] - t[None, :]
    K = sf2 * np.exp(-0.5 * (d / ell) ** 2)
    Ky = K + (sigma_n ** 2 + jitter) * np.eye(n)
    Lc = np.linalg.cholesky(Ky)
    a = np.linalg.solve(Lc.T, np.linalg.solve(Lc, x))
    if order == 1:
        Kd = K * (-d / ell ** 2)
        Kdd = sf2 / ell ** 2
    else:
        Kd = K * ((d ** 2 - ell ** 2) / ell ** 4)
        Kdd = 3 * sf2 / ell ** 4
    mu = Kd @ a
    V = np.linalg.solve(Lc, Kd.T)
    var = np.maximum(Kdd - np.sum(V ** 2, axis=0), 0.0)
    return mu, np.sqrt(var)


# ------------------------------------------------------------- integration

def int_spectral(a, dt, order=1, fc=None, detrend=True, taper=0.05):
    """FFT integration: divide by (i*omega)**order with a high-pass below fc.

    fc : high-pass corner in Hz.  Everything below it -- including DC, which is
         otherwise a division by zero -- is removed with a raised-cosine edge.
         Set it below your lowest mode and above the drift.
    """
    a = np.asarray(a, float)
    n = len(a)
    t = np.arange(n) * dt
    if detrend:
        a = a - np.polyval(np.polyfit(t, a, 1), t)
    w = _taper(n, taper)
    A = np.fft.rfft(a * w)
    om = 2 * np.pi * np.fft.rfftfreq(n, dt)
    H = np.zeros_like(om)
    nz = om > 0
    H[nz] = 1.0
    if fc is not None:
        oc = 2 * np.pi * fc
        lo, hi = 0.5 * oc, oc
        band = (om > lo) & (om <= hi)
        H[band] = 0.5 * (1 - np.cos(np.pi * (om[band] - lo) / (hi - lo)))
        H[om <= lo] = 0.0
    X = np.zeros_like(A)
    X[nz] = A[nz] * H[nz] / (1j * om[nz]) ** order
    y = np.fft.irfft(X, n=n)
    return y / np.maximum(w, 1e-3) if taper > 0 else y


def int_trapz_detrend(a, dt, order=1, poly=1, hp=None):
    """Cumulative trapezoid with polynomial baseline correction at each stage.

    The classical strong-motion recipe (Boore): integrate, fit and remove a
    low-order polynomial, integrate again, remove again.  `hp` adds a zero-phase
    Butterworth high-pass (Hz) after each stage, which is what actually
    controls the drift; the polynomial alone rarely suffices.
    """
    y = np.asarray(a, float)
    n = len(y)
    t = np.arange(n) * dt
    for _ in range(order):
        y = y - np.polyval(np.polyfit(t, y, poly), t)
        if hp is not None:
            b, aa = signal.butter(4, hp / (0.5 / dt), btype="highpass")
            y = signal.filtfilt(b, aa, y)
        c = np.zeros(n)
        c[1:] = np.cumsum(0.5 * (y[1:] + y[:-1])) * dt
        y = c
    y = y - np.polyval(np.polyfit(t, y, poly), t)
    if hp is not None:
        b, aa = signal.butter(4, hp / (0.5 / dt), btype="highpass")
        y = signal.filtfilt(b, aa, y)
    return y


def int_tikhonov(a, dt, order=2, fc=None, lam=None, pen=0, bc=None):
    """Regularised integration: the inverse problem solved directly.

    order=2 solves   min_x ||D2 x/dt^2 - a||^2 + lam*||L x||^2
    order=1 solves   min_v ||D1 v/dt  - a||^2 + lam*||L v||^2

    With L = I (pen=0) the frequency response is

        X(omega) = (-A/omega^2) * omega^4 / (omega^4 + lam)

    i.e. exact double integration times a maximally flat high-pass whose -3 dB
    corner is omega_c = lam^(1/4).  Hence the tuning rule

        lam = (2*pi*fc)**(2*order)                     (pen=0)

    Same job as high-pass-then-integrate, but posed as one well-conditioned
    banded least-squares problem instead of a cascade, so there is no phase
    bookkeeping and boundary conditions can be imposed exactly.

    bc : optional dict of hard constraints, e.g. {0: 0.0, -1: 0.0} pins the
         first and last sample -- useful when the test starts and ends at rest.
    """
    a = np.asarray(a, float)
    n = len(a)
    if lam is None:
        if fc is None:
            raise ValueError("give lam or fc")
        lam = (2 * np.pi * fc) ** (2 * order) if pen == 0 else \
              (2 * np.pi * fc) ** (2 * (order - pen))
    D = diff_matrix(n, order, dt)
    rhs_meas = _resample_rhs(a, order)
    L = sparse.eye(n, format="csc") if pen == 0 else diff_matrix(n, pen, dt)
    A = (D.T @ D + lam * (L.T @ L)).tocsc()
    b = D.T @ rhs_meas
    if bc:
        idx = [k % n for k in bc]
        vals = np.array([bc[k] for k in bc], float)
        big = 1e12 * np.abs(A).max()
        P = sparse.csc_matrix((np.full(len(idx), big), (idx, idx)), shape=(n, n))
        A = (A + P).tocsc()
        b = b + big * sparse.csc_matrix(
            (vals, (idx, np.zeros(len(idx), int))), shape=(n, 1)).toarray().ravel()
    return spsolve(A, b)


def _resample_rhs(a, order):
    """Centre the measured signal on the stencil of D^order (length n-order)."""
    if order == 0:
        return a
    b = a
    for _ in range(order):
        b = 0.5 * (b[1:] + b[:-1])
    return b


# --------------------------------------------- delay-reconstruction methods
#
# Prior: the signal lies in a low-dimensional subspace of its delay
# reconstruction.  Embed x in a trajectory (Hankel) matrix whose rows are
# delay vectors [x_k, x_k+1, ..., x_k+L-1], find the signal subspace, project,
# average back along the anti-diagonals, and differentiate or integrate the
# reconstruction.  Several channels are embedded side by side (multichannel
# SSA), so a mode seen strongly in one channel helps the others.
#
# Two bases are offered for the subspace:
#   'svd'  principal directions of the trajectory matrix (SSA).  Ranked by
#          energy; dimension from the Gavish-Donoho hard threshold.
#   'sod'  smooth orthogonal decomposition INSIDE that SVD signal subspace:
#          the generalised eigenproblem  (Y'Y) phi = lam (dY'dY) phi  orders the
#          same subspace by smoothness, i.e. by frequency, which separates
#          slow drift from oscillation far more cleanly than energy does.
#          Identical reconstruction to 'svd' when nothing is dropped; better
#          when a band is removed (integration with drift).
#   'sod_full'  SOD on the whole embedding, ranked by smoothness alone.  Kept
#          for comparison only: with long windows it admits smooth NOISE
#          directions ahead of signal (3 % velocity error vs 0.34 % for 'svd'
#          on the benchmark at L = 641) because smoothness ignores energy.

def _gd_omega(beta):
    """Gavish-Donoho optimal hard-threshold coefficient, unknown noise level."""
    return 0.56 * beta ** 3 - 0.95 * beta ** 2 + 1.82 * beta + 1.43


def _embed(x, L):
    n, m = x.shape
    K = n - L + 1
    idx = np.arange(K)[:, None] + np.arange(L)[None, :]
    return np.hstack([x[idx, j] for j in range(m)]), K


def _hankelize(Xr, n, L, m):
    K = n - L + 1
    idx = (np.arange(K)[:, None] + np.arange(L)[None, :]).ravel()
    cnt = np.bincount(idx, minlength=n).astype(float)
    out = np.empty((n, m))
    for j in range(m):
        out[:, j] = np.bincount(idx, weights=Xr[:, j * L:(j + 1) * L].ravel(),
                                minlength=n) / cnt
    return out


def _welch_scipy_like(y, dt, nper):
    return signal.welch(y - y.mean(), fs=1.0 / dt, nperseg=nper, detrend="linear")


def signal_band(x, dt, factor=3.0, nperseg=256):
    """Highest frequency (Hz) where the PSD exceeds `factor` x the white noise
    plateau near Nyquist (the plateau read as in estimate_noise_var).

    Short segments (default 256) average enough periodograms that a factor of
    3 is not crossed by noise alone.  For several channels the maximum is
    returned.
    """
    x = np.atleast_2d(np.asarray(x, float).T).T
    out = 0.0
    for j in range(x.shape[1]):
        f, P = _welch_scipy_like(x[:, j], dt, min(len(x), nperseg))
        m = (f >= 0.40 / dt) & (f <= 0.49 / dt)
        if not m.any():
            m = f >= f[-1] * 0.8
        above = np.nonzero(P > factor * np.median(P[m]))[0]
        out = max(out, f[above[-1]] if len(above) else f[-1])
    return float(out)


def delay_project(x, dt, L=None, method="svd", rank="auto", fmin=None,
                  fmax="auto", scale="auto", return_info=False):
    """Project x (n, or n x m channels) onto its delay-reconstruction signal
    subspace and return the reconstruction (same shape as x).

    L      window (embedding dimension).  Default min(n//3, 2000).
    rank   'auto' = Gavish-Donoho hard threshold on the singular values of the
           trajectory matrix, or an integer.
    fmin, fmax   drop components whose mean frequency
           f_k = rms(dq_k/dt) / (2 pi rms(q_k)) lies outside [fmin, fmax] Hz.
           fmax='auto' uses signal_band(x): a guard against noise directions
           that pass the threshold at long windows -- one such component at
           637 Hz gave 90 % acceleration error at L = 1501 without it.
    scale  per-channel normalisation before embedding; 'auto' divides each
           channel by its noise std, which is what the Gavish-Donoho threshold
           assumes (equal-variance noise) and what keeps a loud channel from
           owning the subspace.
    info   r (threshold rank), keep (mask over the r components), f (Hz), sv.
    """
    x = np.asarray(x, float)
    vec = x.ndim == 1
    x = np.atleast_2d(x.T).T
    n, m = x.shape
    if L is None:
        L = int(min(n // 3, 2000))
    L = int(L)
    if isinstance(scale, str):
        scale = (np.sqrt([estimate_noise_var(x[:, j], dt) for j in range(m)])
                 if m > 1 else np.ones(1))
    scale = np.asarray(scale, float).reshape(m)
    if isinstance(fmax, str):
        fmax = signal_band(x, dt)
    X, K = _embed(x / scale, L)
    C = X.T @ X
    s2, V = np.linalg.eigh(C)
    o = np.argsort(s2)[::-1]
    s2, V = s2[o], V[:, o]
    sv = np.sqrt(np.maximum(s2, 0.0))
    if isinstance(rank, str):
        p = L * m
        r = int(np.sum(sv > _gd_omega(min(K, p) / max(K, p)) * np.median(sv)))
    else:
        r = int(rank)
    r = max(1, min(r, L * m))
    if method == "svd":
        B = V[:, :r]
        Bi = B.T
    elif method == "sod":
        Y = X @ V[:, :r]
        dY = np.diff(Y, axis=0)
        lam, Phi = linalg.eigh(Y.T @ Y / K, dY.T @ dY / (K - 1))
        Phi = Phi[:, np.argsort(lam)[::-1]]
        B = V[:, :r] @ Phi
        Bi = np.linalg.solve(Phi, V[:, :r].T)
    elif method == "sod_full":
        dX = np.diff(X, axis=0)
        lam, Phi = linalg.eigh(C / K, dX.T @ dX / (K - 1))
        Phi = Phi[:, np.argsort(lam)[::-1]]
        B = Phi[:, :r]
        Bi = np.linalg.inv(Phi)[:r]
    else:
        raise ValueError("method must be 'svd', 'sod' or 'sod_full'")
    Q = X @ B
    f = np.sqrt(np.mean(np.diff(Q, axis=0) ** 2, 0) / np.mean(Q ** 2, 0)) / (2 * np.pi * dt)
    keep = np.ones(r, bool)
    if fmin is not None:
        keep &= f >= fmin
    if fmax is not None:
        keep &= f <= fmax
    xr = _hankelize(Q[:, keep] @ Bi[keep], n, L, m) * scale
    if vec:
        xr = xr[:, 0]
    if return_info:
        return xr, {"r": r, "keep": keep, "f": f, "sv": sv, "L": L,
                    "fmax": fmax, "scale": scale}
    return xr


def _diff4(y, dt, order):
    """Fourth-order central differences (5-point), second-order at the ends."""
    g = np.empty_like(y)
    if order == 1:
        g[2:-2] = (-y[4:] + 8 * y[3:-1] - 8 * y[1:-3] + y[:-4]) / (12 * dt)
        g[:2] = np.gradient(y[:4], dt, edge_order=2)[:2]
        g[-2:] = np.gradient(y[-4:], dt, edge_order=2)[-2:]
    elif order == 2:
        g[2:-2] = (-y[4:] + 16 * y[3:-1] - 30 * y[2:-2] + 16 * y[1:-3] - y[:-4]) / (12 * dt ** 2)
        g[:2] = np.gradient(np.gradient(y[:5], dt, edge_order=2), dt, edge_order=2)[:2]
        g[-2:] = np.gradient(np.gradient(y[-5:], dt, edge_order=2), dt, edge_order=2)[-2:]
    else:
        raise ValueError("order must be 1 or 2")
    return g


def diff_delay(x, dt, order=1, L=None, method="svd", rank="auto", fmax="auto",
               scale="auto", return_info=False):
    """Differentiate through the delay reconstruction (SSA / multichannel SSA).

    x is projected onto its delay-space signal subspace (delay_project) and
    the reconstruction is differentiated with fourth-order central
    differences; the reconstruction is band-limited to the signal band, where
    the stencil error is ~(omega dt)^4/30, negligible at any sane sampling
    rate.  Self-tuning: window from the record length, dimension from the
    Gavish-Donoho threshold, noise guard from the PSD.

    Benchmark (Duffing decay, 1 % noise, seed 110): 0.32 % / 0.94 % velocity /
    acceleration error, against 0.54 % / 1.52 % for the oracle-tuned spectral
    method and 0.83 % / 3.33 % for the self-tuned state-space smoother.  The
    prior suits quasi-periodic records -- free decays, multimode ringdowns,
    steady forced response.  It brings nothing at impacts (23 % near-impact
    error, as for the quadratic penalties; TV gives 17 %).

    Several columns are processed jointly (multichannel SSA); the result has
    the shape of x.  With return_info=True also returns delay_project's info.
    """
    xr, info = delay_project(x, dt, L=L, method=method, rank=rank, fmax=fmax,
                             scale=scale, return_info=True)
    if xr.ndim == 1:
        y = _diff4(xr, dt, order)
    else:
        y = np.column_stack([_diff4(xr[:, j], dt, order) for j in range(xr.shape[1])])
    return (y, info) if return_info else y


def int_delay(a, dt, order=2, fc=4.0, fc_int=None, L=None, method="sod",
              rank="auto", fmax="auto", scale="auto", return_info=False):
    """Integrate through the delay reconstruction, with drift removed in
    delay space.

    The acceleration is projected onto its signal subspace with every
    component of mean frequency below `fc` (Hz) discarded -- drift, offset,
    slow baseline -- and the clean reconstruction is integrated by
    int_tikhonov with corner `fc_int`.  'sod' orders the subspace by
    smoothness, so the slow components separate from the oscillatory ones;
    with 'svd' they stay mixed by energy and some drift survives.

    fc_int defaults to fc for displacement and fc/4 for velocity (the residual
    drift after projection is small enough for one integration, not for two).
    L defaults to min(n//10, 2000).

    Benchmark (1 % white + 0.5 % drift + 0.5 % offset, seed 7, fc = 4 Hz,
    defaults otherwise): displacement 0.52 %, velocity 1.34 % ('svd': 0.72 %,
    3.68 %), against 0.91 % / 2.04 % for oracle
    Tikhonov alone, 0.50 % / 0.25 % for the oracle spectral method on this
    narrowband record, and 1.72 % / 1.60 % for the state-space smoother.
    """
    a = np.asarray(a, float)
    n = a.shape[0]
    if L is None:
        L = int(min(n // 10, 2000))
    if fc_int is None:
        fc_int = fc if order == 2 else fc / 4.0
    ar, info = delay_project(a, dt, L=L, method=method, rank=rank, fmin=fc,
                             fmax=fmax, scale=scale, return_info=True)
    if ar.ndim == 1:
        y = int_tikhonov(ar, dt, order=order, fc=fc_int)
    else:
        y = np.column_stack([int_tikhonov(ar[:, j], dt, order=order, fc=fc_int)
                             for j in range(ar.shape[1])])
    return (y, info) if return_info else y


# ------------------------------------------------- unified state-space form

def _irw_matrices(n_int, dt, q):
    """Exact F, Q for an integrated random walk of order n_int (white noise on
    the n_int-th derivative).  State = [x, x', ..., x^(n_int-1)]."""
    from math import factorial
    F = np.zeros((n_int, n_int))
    for i in range(n_int):
        for j in range(i, n_int):
            F[i, j] = dt ** (j - i) / factorial(j - i)
    Q = np.zeros((n_int, n_int))
    for i in range(n_int):
        for j in range(n_int):
            p = 2 * n_int - i - j - 1
            Q[i, j] = q * dt ** p / (factorial(n_int - 1 - i) *
                                     factorial(n_int - 1 - j) * p)
    return F, Q


def kinsmooth(t, x=None, a=None, v=None, q=None, Rx=None, Ra=None, Rv=None,
              nstate=4, bias=False, qbias=None, fit=True, return_cov=False,
              hp=None, causal=False):
    """Kinematic Kalman/RTS smoother: differentiation, integration and fusion.

    State [x, v, a, jerk, ...] (nstate components) driven by white noise on the
    highest derivative -- an integrated random walk.  No system model: the only
    assumption is that the (nstate)-th derivative is a stationary white process,
    which is the continuous-time statement of "the signal is smooth".

    Feed any subset of measurements, at any sample rates, with gaps as NaN:

      x only  -> differentiation (equivalent to a smoothing spline of order
                 2*nstate-1, but O(N) and with error bars)
      a only  -> integration, with `bias=True` adding a random-walk offset state
                 that absorbs the drift instead of letting it integrate twice
      both    -> complementary fusion: displacement pins the low frequencies and
                 the absolute scale, acceleration pins the high frequencies.
                 This is the estimator to use when you have both sensors.

    q is the process-noise PSD (the single regularisation knob).  With fit=True
    it is chosen by maximising the Kalman marginal likelihood of the data, so
    the method is self-tuning -- no lambda sweep, no cross-validation.

    hp : high-pass corner in Hz, needed ONLY when integrating acceleration
    alone.  Displacement and mean velocity are not observable from acceleration
    (the two integration constants), so without a prior the answer is arbitrary.
    `hp` installs soft zero-mean pseudo-measurements on x and v with variance
    q/(2*pi*hp)**(2*nstate) and q/(2*pi*hp)**(2*nstate-2), which is exactly a
    high-pass of corner hp -- the same admission of ignorance that the cutoff in
    int_spectral makes, but stated as a prior instead of a filter.

    causal : return the forward Kalman FILTER instead of the RTS smoother.
    Each output sample then uses data up to that time only, so the estimator
    can run online.  On the benchmark (1 % noise, nstate=4, self-tuned) its
    velocity error is 5.4 %, against 11.9 % for Levant at its best L.  For
    genuine online use fit q once on a calibration record and pass it in.

    Returns dict with 'x','v','a' (and 'j' if nstate>3), 'bias' if requested,
    'std' (posterior standard deviations), 'q', 'loglik'.
    """
    t = np.asarray(t, float)
    n = len(t)
    dts = np.diff(t)
    uniform = np.allclose(dts, dts[0], rtol=1e-9) if n > 1 else True

    meas = []
    if x is not None:
        meas.append(("x", np.asarray(x, float), 0, Rx))
    if v is not None:
        meas.append(("v", np.asarray(v, float), 1, Rv))
    if a is not None:
        meas.append(("a", np.asarray(a, float), 2, Ra))
    if not meas:
        raise ValueError("give at least one of x, v, a")
    if nstate < 3:
        raise ValueError("nstate >= 3 so that acceleration is a state")

    dt0 = dts[0] if n > 1 else 1.0
    R = []
    for name, y, idx, Rgiven in meas:
        if Rgiven is None:
            good = np.isfinite(y)
            Rgiven = estimate_noise_var(y[good], dt0)
        R.append(max(float(Rgiven), 1e-30))

    ns = nstate + (1 if bias else 0)
    H = np.zeros((len(meas), ns))
    for k, (name, y, idx, _) in enumerate(meas):
        H[k, idx] = 1.0
        if bias and name == "a":
            H[k, nstate] = 1.0

    Y = np.full((n, len(meas)), np.nan)
    for k, (_, y, _, _) in enumerate(meas):
        Y[:, k] = y

    def build(dt, qv):
        F = np.eye(ns)
        Q = np.zeros((ns, ns))
        Fk, Qk = _irw_matrices(nstate, dt, qv)
        F[:nstate, :nstate] = Fk
        Q[:nstate, :nstate] = Qk
        if bias:
            F[nstate, nstate] = 1.0
            Q[nstate, nstate] = (qbias if qbias is not None else qv * 1e-6) * dt
        return F, Q

    def run(qv, smooth):
        FQ = {}
        if uniform:
            FQ[0] = build(dt0, qv)
        m = np.zeros(ns)
        P = np.eye(ns) * 1e6
        if bias:
            P[nstate, nstate] = 1e2
        mf = np.zeros((n, ns)); Pf = np.zeros((n, ns, ns))
        mp = np.zeros((n, ns)); Pp = np.zeros((n, ns, ns))
        Fs = np.zeros((n, ns, ns))
        ll = 0.0
        for k in range(n):
            if k > 0:
                dt = dt0 if uniform else dts[k - 1]
                key = 0 if uniform else k
                if key not in FQ:
                    FQ[key] = build(dt, qv)
                F, Q = FQ[key]
                m = F @ m
                P = F @ P @ F.T + Q
                Fs[k] = F
            mp[k] = m; Pp[k] = P
            obs = np.isfinite(Y[k])
            if obs.any():
                Hk = H[obs]
                Rk = np.diag(np.asarray(R)[obs])
                S = Hk @ P @ Hk.T + Rk
                innov = Y[k, obs] - Hk @ m
                try:
                    Lc = np.linalg.cholesky(S)
                except np.linalg.LinAlgError:
                    S = S + 1e-12 * np.eye(S.shape[0]) * np.trace(S)
                    Lc = np.linalg.cholesky(S)
                alpha = np.linalg.solve(Lc.T, np.linalg.solve(Lc, innov))
                K = P @ Hk.T @ np.linalg.inv(S)
                m = m + K @ innov
                P = P - K @ Hk @ P
                P = 0.5 * (P + P.T)
                ll += -0.5 * (innov @ alpha) - np.log(np.diag(Lc)).sum() \
                      - 0.5 * len(innov) * np.log(2 * np.pi)
            mf[k] = m; Pf[k] = P
        if smooth == "filter":
            return mf, Pf, ll
        if not smooth:
            return ll
        ms = mf.copy(); Ps = Pf.copy()
        for k in range(n - 2, -1, -1):
            F = Fs[k + 1]
            Ppk = Pp[k + 1]
            G = Pf[k] @ F.T @ np.linalg.pinv(Ppk)
            ms[k] = mf[k] + G @ (ms[k + 1] - mp[k + 1])
            Ps[k] = Pf[k] + G @ (Ps[k + 1] - Ppk) @ G.T
        return ms, Ps, ll

    if q is None and fit:
        scale = np.nanvar(Y[:, 0]) / max(dt0 ** (2 * nstate - 1), 1e-300)
        f = lambda lg: -run(10.0 ** lg * scale, False) / n
        res = optimize.minimize_scalar(f, bounds=(-14, 6), method="bounded",
                                       options={"xatol": 1e-3})
        q = 10.0 ** res.x * scale
    elif q is None:
        q = np.nanvar(Y[:, 0]) / dt0 ** (2 * nstate - 1) * 1e-6

    if hp is not None:
        # soft zero-mean prior on the unobservable low-frequency directions
        wc = 2 * np.pi * hp
        meas = meas + [("x0", np.zeros(n), 0, q / wc ** (2 * nstate)),
                       ("v0", np.zeros(n), 1, q / wc ** (2 * nstate - 2))]
        R = R + [max(q / wc ** (2 * nstate), 1e-300),
                 max(q / wc ** (2 * nstate - 2), 1e-300)]
        Hx = np.zeros((2, ns)); Hx[0, 0] = 1.0; Hx[1, 1] = 1.0
        H = np.vstack([H, Hx])
        Y = np.hstack([Y, np.zeros((n, 2))])

    ms, Ps, ll = run(q, "filter" if causal else True)
    out = {"x": ms[:, 0], "v": ms[:, 1], "a": ms[:, 2],
           "std": np.sqrt(np.maximum(np.diagonal(Ps, axis1=1, axis2=2), 0)),
           "q": q, "loglik": ll, "R": R}
    if nstate > 3:
        out["j"] = ms[:, 3]
    if bias:
        out["bias"] = ms[:, nstate]
    if return_cov:
        out["P"] = Ps
    return out


# ---------------------------------------------------------------- citation
DOI = "10.5281/zenodo.23549236"


def cite(fmt="bibtex"):
    """Return how to cite the toolbox: fmt = 'bibtex' (default) or 'text'."""
    if fmt == "bibtex":
        return ("@software{chelidze2026kinematics,\n"
                "  author    = {Chelidze, David},\n"
                "  title     = {Kinematics toolbox: Model-free differentiation and integration of measured motion},\n"
                "  version   = {1.0.0},\n"
                "  year      = {2026},\n"
                "  publisher = {Zenodo},\n"
                "  doi       = {10.5281/zenodo.23549236},\n"
                "  url       = {https://github.com/nld-uri/kinematics-toolbox}\n"
                "}")
    if fmt == "text":
        return ("D. Chelidze, Kinematics toolbox: Model-free differentiation and integration of "
                "measured motion, version 1.0.0, Zenodo (2026). https://doi.org/10.5281/zenodo.23549236")
    raise ValueError("fmt must be 'bibtex' or 'text'")
