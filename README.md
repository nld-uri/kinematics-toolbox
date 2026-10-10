# Model-free differentiation and integration of measured motion

Differentiating a measured displacement and integrating a measured acceleration
are **the same ill-posed linear inverse problem**, run in opposite directions.
Write the measurement as

    y = A u + e

with `A` the integration operator (for differentiation, `u` is the derivative
you want) or the double-integration operator (for integration, `u` is the
displacement). In both cases `A` is compact, its inverse is unbounded, and the
noise `e` is amplified without limit — as `ω` per derivative going up, as `1/ω`
per integration going down. No amount of cleverness removes this. Every usable
method adds a **regularity prior** and differs only in which one:

| prior | method |
|---|---|
| signal is bandlimited and periodic | spectral (FFT × (iω)ⁿ) |
| signal is locally a low-order polynomial | Savitzky–Golay, Lanczos |
| signal lies in a low-rank delay-embedding subspace | SVD / SSA |
| p-th derivative is small in L2 | Whittaker–Henderson, Tikhonov, smoothing spline |
| **derivative is piecewise smooth (L1)** | **total-variation (Chartrand)** |
| **(n)-th derivative is white noise** | **Kalman/RTS kinematic smoother, GP** |
| **(n+1)-th derivative is merely bounded** | **Levant sliding-mode differentiator** |

The three in bold are the families beyond the frequency-domain and SVD methods
you already know. The last two are worth separating out:

- The **state-space (Kalman/RTS) smoother** is the one to reach for. It is
  exactly equivalent to a smoothing spline and to a Gaussian process with an
  integrated-Wiener kernel, but runs in O(N) instead of O(N³), tunes itself by
  marginal likelihood, handles gaps, non-uniform sampling and multi-rate
  channels, returns posterior error bars, and — the reason it matters here —
  **does differentiation and integration in the same estimator**, so you can
  feed it a displacement and an acceleration channel at once.
- **Total variation** is the only family that does not round off a genuine
  corner. If your signal has impacts, dry friction reversals or backlash, the
  L1 penalty is not a refinement, it is the point.

---

## What the benchmark shows

Ground truth is a Duffing free decay (15 Hz, ζ = 0.004, 25 % hardening shift at
the initial amplitude), 2 kHz, 3 s, solved to `rtol = 1e-12`, so every error
below is a true error. Each method's single knob was swept and the **oracle
minimum** is reported — the best that method could do if tuned perfectly. The
state-space smoother is reported **self-tuned**, with no oracle. Errors are
relative rms over the interior 90 % of the record.

### Differentiating position (velocity / acceleration error, % rms)

| method | 0.1 % noise | 1 % noise | 5 % noise |
|---|---|---|---|
| Spectral (FFT), oracle | 0.080 / 0.343 | 0.538 / 1.516 | 2.395 / 6.469 |
| Whittaker p=3, oracle | 0.133 / 0.564 | 0.759 / 2.486 | 2.393 / 6.788 |
| Savitzky–Golay, oracle | 0.171 / 1.878 | 0.888 / 5.091 | 2.603 / 10.424 |
| Smoothing spline, oracle | 0.182 / 0.888 | 0.908 / 3.648 | 2.662 / 7.700 |
| **State-space n=4, self-tuned** | 0.182 / 1.282 | 0.827 / 3.328 | 2.437 / 7.186 |
| **State-space n=5, self-tuned** | 0.171 / 0.654 | 0.968 / 2.441 | 3.501 / 8.002 |

**The headline: what self-tuning costs depends on how clean the data are, and
it is cheapest where you need it most.** Ratio of the self-tuned state-space
error to the *best oracle-tuned error of any method* in the same column:

| | 0.1 % noise | 1 % noise | 5 % noise |
|---|---|---|---|
| n=4, velocity | 2.28× | 1.54× | 1.02× |
| n=4, acceleration | 3.74× | 2.19× | 1.11× |
| n=5, velocity | 2.14× | 1.80× | 1.46× |
| n=5, acceleration | 1.91× | 1.61× | 1.24× |

The gap is widest on very clean data (up to 3.7× at 0.1 % noise, for the n=4
acceleration) and closes to essentially parity at 5 % noise. This is the right
way round: when the record is nearly noise-free, a hand-tuned cutoff can be
pushed high and wins, but the absolute errors there are a fraction of a percent
and the choice rarely matters. When the data are noisy — the case where tuning
actually decides the answer — the self-tuned estimator is within 1.0–1.5× of a
perfectly tuned one. Raise `nstate` to 5 if your records are clean and you want
acceleration: it roughly halves the low-noise penalty.

Against the oracle you do not have, the sensitivity is what matters: a
factor-of-3 error in the cutoff costs an order of magnitude in the acceleration
estimate (Fig. 1a,b).

Other families on the same smooth signal, oracle-tuned at 1 % noise: Gaussian
process 1.227 / 6.048 (and 46 s at N = 6000, versus 2 s), total variation
5.071 / 14.863, Levant 7.162 / 19.780. On a *smooth* signal the L1 and
sliding-mode methods are simply worse — which is the correct result, not a
defect.

Every differentiation number in this section — the table above, these three
families, and the edge-effect table below — comes from the **same** noise
realisation and the same knob grid, so the entries are directly comparable.
`benchmark_summary.csv` records each one with its optimal knob value.

### The edge effect (velocity error, 1 % noise)

| method | interior 90 % | full record |
|---|---|---|
| Spectral (FFT) | 0.538 | **8.352** |
| Whittaker | 0.759 | 0.852 |
| Savitzky–Golay | 0.888 | 0.945 |
| State-space | 0.827 | 0.827 |

This is the practical case against the frequency-domain method: a **15×
degradation** in the last few percent of the record, because the FFT enforces
periodicity on a record that is not periodic. Tapering trades the error for
attenuation rather than removing it. For a free-decay test, where the
high-amplitude information is at the *start* of the record, this matters.

### When the derivative is genuinely discontinuous

Vibro-impact oscillator, 10 impacts with restitution 0.85. Velocity error
within ±4 ms of an impact:

| method | error |
|---|---|
| **Total variation** | **19.2 %** |
| Whittaker | 22.3 % |
| Spectral | 24.1 % |
| State-space | 26.7 % |

TV is the only one that tracks the jump most closely (Fig. 1d) — a 14 % reduction
in local error against the best quadratic-penalty method. If you are measuring
impact velocities or restitution coefficients, that difference is the
measurement.

### Integrating acceleration (1 % white + 0.5 % drift + 0.5 % offset)

| method | velocity | displacement | knob robustness |
|---|---|---|---|
| Naive cumulative trapezoid | 60.2 % | **4105 %** | — |
| Spectral, oracle | 0.251 % | 0.503 % | 0.46 decades |
| Tikhonov, oracle | 2.041 % | 0.905 % | 0.46 decades |
| Trapezoid + detrend + high-pass | 1.789 % | 2.839 % | 0.11 decades |
| State-space (self q, hp = 4 Hz) | 1.604 % | 1.721 % | — |

Two things to take from this. First, the classical strong-motion recipe
(integrate, remove a polynomial, high-pass) is both the least accurate and by
far the **most brittle** — its usable cutoff window is a third of a decade
wide, against half a decade for the others. Second, the spectral method wins
here partly because this signal is narrowband at 15 Hz and the drift sits at
0.7 Hz, so a 9 Hz corner is available. With a structure whose lowest mode is
near the drift band, that separation does not exist and the ranking changes.

### Fusing both sensors

200 Hz displacement at 3 % noise + 2 kHz acceleration at 1 % noise with drift:

| input | displacement | velocity | acceleration |
|---|---|---|---|
| displacement only | 2.212 % | 3.864 % | 9.981 % |
| acceleration only | 1.721 % | 1.604 % | 1.829 % |
| **both, fused** | **1.285 %** | **1.146 %** | **1.668 %** |

Fusion beats either channel alone on all three kinematic quantities. It also
**removes the high-pass knob entirely**: displacement observes the low
frequencies that acceleration cannot, so the integration constants become
identified and no prior corner has to be invented. If you have both sensors,
this is the answer.

---

## Recommendation

1. **Have both a displacement and an acceleration channel?** Fuse them in one
   state-space smoother. Best accuracy, no cutoff to choose, error bars
   included, and the two channels are guaranteed kinematically consistent —
   which separate processing never gives you.
2. **Differentiating position, smooth signal, one knob acceptable?** Whittaker
   with `p = 3` and a physically chosen corner. One banded solve, no edge
   damage, and the λ ↔ f_c rule below means you set it from the physics.
3. **Differentiating position, want no knob?** The self-tuned state-space
   smoother — `nstate = 4` for noisy records, `nstate = 5` if the data are
   clean (≲0.1 % noise) and you want acceleration, where n=4 pays a 3.7×
   penalty against a perfectly tuned method and n=5 pays 1.9×.
4. **Signal with impacts, stick–slip, backlash?** Total variation, and accept
   the tuning-by-eye.
5. **Integrating acceleration, acceleration only?** Tikhonov with the corner set
   below your lowest mode and above the drift. Never a bare `cumtrapz`.
6. **Online / control loop?** Levant's differentiator — it is the only causal
   one here, and its accuracy penalty offline is the price of that.
7. Use the FFT method when the record is long, stationary and you can discard
   the ends; it is genuinely the most accurate in the interior.

---

## Tuning rules

Every regularisation parameter below is set from a corner frequency in Hz, not
by a blind sweep. These are derived in the docstrings.

**Whittaker smoother / derivative.** Response is `1/(1 + λ ω^{2p})`, so

    λ = (2π f_c)^(-2p)

where `f_c` is the −3 dB corner. Put it above the highest frequency you
believe in the signal, below where noise dominates.

**Tikhonov integration.** With an identity penalty the result is exact
integration multiplied by a maximally flat high-pass of corner `ω_c = λ^(1/4)`:

    λ = (2π f_c)^(2·order)

**Savitzky–Golay.** `f_c·dt ≈ (polyorder+1)/(3.2M − 4.6)` for half-width `M`
(Schafer 2011); inverted internally. Note that SG's roll-off is gentle, so its
optimum cutoff sits well above the others' — do not reuse the same `f_c`.

**State-space smoother.** The process-noise PSD `q` is fitted by maximising the
Kalman marginal likelihood. Supply `hp` **only** when integrating acceleration
alone.

---

## Two warnings

- **GCV failed on this record.** `scipy.interpolate.make_smoothing_spline`
  selects λ by generalised cross-validation and returned an essentially flat
  fit — 100 % error — on a 6000-point oscillatory decay. The spline itself is
  fine with λ set explicitly (0.908 % at 1 % noise). Do not trust automatic GCV
  on long, densely-sampled oscillatory records without checking the fit.
- **Total variation is only meaningful if its solver converges — and the naive
  ones do not.** Posed in Chartrand's original variables the Hessian
  `AᵀA + αL` is dense and so ill-conditioned that conjugate gradients stalls at
  any iteration cap; IRLS on the smoothed L1 stalls too, at a measured rate of
  0.997 per iteration. In both cases the unconverged iterate acts as *extra
  smoothing* and silently changes the answer — and `scipy.sparse.linalg.cg`
  returns it without a word, where MATLAB's `pcg` at least warns. Successive
  solver generations moved TV's velocity error on the smooth signal 3.77 % →
  4.93 % → **5.07 %**, and near impacts 17.9 % → 16.6 % → **19.2 %**; only the
  last pair, from ADMM, is the actual minimiser. Under-convergence had been
  flattering the method. Both ports now substitute `w = Au` to get L1 trend
  filtering, whose ADMM system is pentadiagonal and constant — it factors once
  and solves the exact L1 objective with no epsilon smoothing.  A closing trap:
  because `alpha` is tied to absolute signal scale, TV is also the only method
  in this library sensitive to *which* standard deviation you normalise by --
  numpy divides by N, MATLAB by N-1, and on a 6000-point record that 83 ppm
  difference moves the answer by 1.5e-6 while every linear method is unaffected.
- **Bias states are weakly identified.** In the acceleration-only run the fitted
  offset was within a factor of ~2 of truth, and in the fused run it had the
  wrong sign. A constant offset and a slow drift are nearly the same thing over
  a 3 s record; treat the bias state as something that absorbs drift, not as a
  calibration measurement.

---

## Cross-validation status

The MATLAB port has been run against the Python reference on MATLAB R2026a:
**12 of 12 checks pass.** The agreement levels are diagnostic of each routine's
conditioning rather than arbitrary:

| routine | agreement | what sets the floor |
|---|---|---|
| `kin_diff_spectral` (both orders) | 5e-16, 9e-16 | exact; FFT is the same arithmetic |
| `kin_int_spectral` | 5e-16 | exact |
| `kin_diff_savgol` | 7e-15 | exact; interior only (edge conventions differ) |
| `kin_diff_tvreg` | 2e-14 | identical ADMM trajectory, 2067 iterations, same rho |
| `kin_int_tikhonov` | 8e-10 | sparse direct solve on a badly scaled normal matrix |
| `kin_diff_whittaker` | 2e-11, 3e-11 | same — `I + lam*D'D` spans many orders of magnitude |
| `kin_smooth` (all outputs) | 5e-9 to 1e-5 | RTS recursion depth |
| `kin_smooth` fitted `q` | 7e-5 | two independent Brent searches over a Kalman likelihood |
| `kin_noisevar` | 7e-4 | Welch estimator reimplemented, not ported line-for-line |

The Whittaker and Tikhonov figures are the sparse-solver accuracy floor, not
error: with `lam = (2*pi*fc)^(-2p)` multiplying `D` scaled by `dt^-p`, the
matrix condition number is large and 1e-10 is what two different direct solvers
(MATLAB's CHOLMOD, scipy's SuperLU) agree to.


## Files

    kinematics.py          the Python library (numpy + scipy only)
    matlab/                the MATLAB port, base MATLAB only, plus a self-test
    bench.py               benchmark harness (ground truth, noise, knob sweeps)
    figs.py                figure code
    benchmark_summary.csv  every number quoted above
    diff_noise_sweep.csv   the noise-level table

### Python

```python
import kinematics as kin

v = kin.diff_whittaker(x, dt, order=1, fc=70)      # velocity from position
a = kin.diff_whittaker(x, dt, order=2, fc=70)      # acceleration from position
d = kin.int_tikhonov(acc, dt, order=2, fc=2.0)     # displacement from acceleration

r = kin.kinsmooth(t, x=x, a=acc, nstate=4, bias=True)   # fuse both
r['x'], r['v'], r['a'], r['std']                        # + posterior std devs

r = kin.kinsmooth(t, x=x, nstate=4)                # differentiate, self-tuned
r = kin.kinsmooth(t, a=acc, bias=True, hp=2.0)     # integrate, needs hp
```

Gaps are `NaN`; a slower channel is just a mostly-`NaN` column; non-uniform `t`
is handled directly.

### MATLAB

```matlab
cd matlab; test_kinematics          % verifies the port against the Python run

v  = kin_diff_whittaker(x, dt, 1, 70);
d  = kin_int_tikhonov(acc, dt, 2, 2.0);
r  = kin_smooth(t, struct('x',x,'a',acc,'nstate',4,'bias',true));
```
