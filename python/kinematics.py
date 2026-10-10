"""
kinematics.py -- model-free differentiation and integration of measured motion.

Every routine here assumes only a *regularity prior* on the signal (bandlimited,
p-times differentiable, sparse jerk, bounded derivative).  None of them uses a
model of the system that produced the signal.

Two groups plus a unifier:

  diff_*   position  -> velocity, acceleration
  int_*    acceleration -> velocity, displacement
  kinsmooth   one state-space estimator that does either direction, fuses both,
              handles gaps / multirate / non-uniform sampling, returns error bars,
              and tunes itself by marginal likelihood.

Tuning rules (derived in the docstrings) let you set every regularisation
parameter from a corner frequency in Hz instead of a blind lambda sweep.

Dependencies: numpy, scipy.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse, signal, optimize
from scipy.sparse.linalg import spsolve, splu
from scipy.interpolate import make_smoothing_spline

__all__ = [
    "diff_matrix", "estimate_noise_var",
    "diff_spectral", "diff_savgol", "diff_whittaker", "diff_spline",
    "diff_tvreg", "diff_levant", "diff_gp",
    "int_spectral", "int_trapz_detrend", "int_tikhonov",
    "kinsmooth",
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


def diff_spline(x, dt, order=1, lam=None):
    """Cubic smoothing spline (GCV-selected lambda by default), differentiated.

    scipy.interpolate.make_smoothing_spline picks lambda by generalised
    cross-validation, so this is the one differentiator with no knob at all.
    Good default when you have no idea what the noise level is; GCV tends to
    under-smooth when the noise is correlated.
    """
    x = np.asarray(x, float)
    t = np.arange(len(x)) * dt
    spl = make_smoothing_spline(t, x, lam=lam)
    return spl.derivative(order)(t) if order else spl(t)


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

    Finite-time exact for signals whose (order+1)-th derivative is bounded by L,
    with no assumption of smoothness beyond that and no linear filtering -- it
    is the standard answer from control theory and is genuinely causal, so it
    runs online.  Price: chattering at the sampling scale and a phase lag,
    which `zero_phase` removes by a second backward pass (offline only).

    L : bound on the (order+1)-th derivative.  Estimated crudely if omitted.
    """
    x = np.asarray(x, float)
    if L is None:
        L = np.max(np.abs(_central(signal.savgol_filter(
            x, min(len(x) // 4 * 2 + 1, 101), 3), dt, order + 1))) * 2 + 1e-12

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
              hp=None):
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

    ms, Ps, ll = run(q, True)
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
