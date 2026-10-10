# MATLAB kinematics toolbox

Core routines are base MATLAB. Two later ports call the Signal Processing
Toolbox (marked SPT below); the self-test also uses the Curve Fitting Toolbox
(csaps) for an independent check when it is installed.

    kin_diffmat.m          sparse finite-difference operator (helper)
    kin_noisevar.m         measurement-noise variance from the PSD plateau (helper)

    kin_diff_spectral.m    FFT differentiation with a low-pass cutoff
    kin_diff_savgol.m      Savitzky-Golay derivative (own coefficients, no sgolay)
    kin_diff_whittaker.m   penalised-smoothing derivative -- the recommended default
    kin_diff_tvreg.m       total-variation derivative, for signals with real corners
    kin_diff_spline.m      cubic smoothing spline (Reinsch, O(N)); lambda by exact GCV,
                           by corner fc, or given.  Uniform or non-uniform times.
    kin_diff_levant.m      Levant sliding-mode differentiator, causal or zero-phase
                           (SPT sgolayfilt only for the default L, which is unreliable)
    kin_diff_gp.m          Gaussian-process derivative + posterior std, dense O(N^3)

    kin_int_spectral.m     FFT integration with a high-pass corner
    kin_int_tikhonov.m     regularised integration as one banded least-squares solve
    kin_delay_project.m    delay-reconstruction projection: SVD (SSA) or SOD, Gavish-Donoho
                           rank, noise-band guard, multichannel
    kin_diff_delay.m       differentiate through the delay reconstruction (no knob)
    kin_int_delay.m        integrate after dropping slow components in delay space
    kin_signal_band.m      highest frequency where the PSD clears the noise floor
    kin_int_trapz_detrend.m  trapezoid + polynomial detrend + Butterworth HP (SPT butter);
                           the classical baseline, scipy-compatible filtfilt padding

    kin_smooth.m           state-space smoother: differentiate, integrate, or FUSE
                           displacement + acceleration.  Self-tuning.
                           opt.causal = true returns the forward Kalman filter
                           (online use); beats Levant by 2x on the benchmark.

    test_kinematics.m      run this first -- checks every function against
                           reference vectors produced by the verified Python code
    kin_reference.mat      reference vectors, original routines
    kin_reference_ext.mat  reference vectors for every routine added after the first port

Validate with:

    >> cd <this folder>
    >> test_kinematics

All Python routines are ported (38 of 38 checks pass on R2026b).

Notes from the port:

- kin_diff_spline: the GCV here computes tr(A) exactly and picks
  lambda = 8.4e-9 (fc = 111 Hz) on the benchmark record, velocity error 1.18 %.
  scipy's make_smoothing_spline GCV returns a flat fit on the same record, so
  the README's "GCV failed" warning is about scipy's implementation.
  Tuning rule: lam = (2*pi*fc)^(-4)/dt (oracle 3.16e-8 is fc = 80 Hz).
- kin_diff_levant: L bounds the THIRD derivative for both outputs. The default
  is now max|jerk| from kin_smooth (7.7 % error; the old default gave 119 %).
- kin_diff_delay: 0.32 % / 0.94 % velocity / acceleration error on the 1 %
  benchmark, self-tuned; best on quasi-periodic records, no gain at impacts.
- kin_diff_gp: tests run on the first 2000 samples to keep memory and time low.
