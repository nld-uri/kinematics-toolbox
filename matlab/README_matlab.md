# MATLAB kinematics toolbox (base MATLAB only, no toolboxes required)

    kin_diffmat.m          sparse finite-difference operator (helper)
    kin_noisevar.m         measurement-noise variance from the PSD plateau (helper)

    kin_diff_spectral.m    FFT differentiation with a low-pass cutoff
    kin_diff_savgol.m      Savitzky-Golay derivative (own coefficients, no sgolay)
    kin_diff_whittaker.m   penalised-smoothing derivative -- the recommended default
    kin_diff_tvreg.m       total-variation derivative, for signals with real corners

    kin_int_spectral.m     FFT integration with a high-pass corner
    kin_int_tikhonov.m     regularised integration as one banded least-squares solve

    kin_smooth.m           state-space smoother: differentiate, integrate, or FUSE
                           displacement + acceleration.  Self-tuning.

    test_kinematics.m      run this first -- checks every function against
                           reference vectors produced by the verified Python code

Validate with:

    >> cd <this folder>
    >> test_kinematics

Not ported (Python only): the smoothing spline (MATLAB's equivalent, csaps,
needs the Curve Fitting Toolbox), the Gaussian-process differentiator, and
Levant's sliding-mode differentiator.
