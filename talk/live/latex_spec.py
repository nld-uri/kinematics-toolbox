"""LaTeX-typeset versions of every kinematics slide block that contains symbols or equations.

Each entry: (slide id, tag, needle, svg name, width px, size px, line-height, LaTeX body, alt text)
The needle locates the HTML element (first <tag ...> whose content contains it).
"""
import sys
sys.path.insert(0, __import__('os').path.join(__import__('os').path.dirname(__file__), 'lib'))
from latexblock import items, table

CW = 782    # inner width of a half-width card
LEAD = r'\itshape\color{muted}'

B = []
def add(*a):
    B.append(a)

# ---- same-problem
add('same-problem', 'ul', 'Write the measurement as', 'kin_same', 1700, 30, 1.4, items([
    r'Write the measurement as $y = Au + e$, with $A$ the integration operator.',
    r'Differentiation: $u$ is the derivative you want, $A$ integrates it back to what you measured.',
    r'Integration: $u$ is the displacement, $A$ integrates the acceleration twice.',
    r'\textbf{$\symbfit{A}$ is compact. Its inverse is unbounded.} This is the definition of an ill-posed inverse problem.',
    r'Noise is amplified without limit — by $\omega$ per derivative going up, by $1/\omega$ per integration going down.',
    r'No amount of cleverness removes this. It is a property of the operator, not of your algorithm.',
    r'{\color{cdeep}Every usable method therefore adds a regularity prior. That is the only thing that distinguishes them.}']),
    'Write the measurement as y = Au + e, with A the integration operator. Differentiation: u is the derivative you want; integration: u is the displacement. A is compact; its inverse is unbounded. Noise is amplified by omega per derivative and by 1/omega per integration. Every usable method therefore adds a regularity prior.')

# ---- spectral
add('spectral', 'p', 'Multiply the spectrum by', 'kin_spectral_lead', 1728, 30, 1.35,
    LEAD + r' Multiply the spectrum by $(\mathrm{i}\omega)^{n}$, roll off above a cutoff, transform back.',
    'Multiply the spectrum by (i omega)^n, roll off above a cutoff, transform back.')
add('spectral', 'ul', 'Exact for a bandlimited', 'kin_spectral_str', CW, 26, 1.35, items([
    r'Exact for a bandlimited periodic signal — no discretisation error at all',
    r'Most accurate of any method in the interior of a long record (0.54\% velocity error here)',
    r'Trivial to implement, $\bigO(N\log N)$, and the cutoff has an obvious physical meaning',
    r'The natural choice when you already work in the frequency domain']),
    'Strengths: exact for a bandlimited periodic signal; most accurate in the interior of a long record (0.54% velocity error here); trivial to implement, O(N log N); natural in the frequency domain.')

# ---- savgol
add('savgol', 'ul', 'Two knobs (window', 'kin_savgol_lim', CW, 26, 1.35, items([
    r'Two knobs (window, polynomial order) that interact',
    r'Implicitly assumes the signal is polynomial over the window — poor for lightly damped resonance',
    r'Noticeably worse than an $L_2$ penalty for second derivatives (2.4\% vs 0.9\% here)',
    r'Edge behaviour depends on the padding convention, which differs between implementations']),
    'Limitations: two interacting knobs; assumes a polynomial over the window; worse than an L2 penalty for second derivatives (2.4% vs 0.9% here); edge behaviour depends on padding.')

# ---- whittaker
add('whittaker', 'p', 'Penalise the', 'kin_whit_lead', 1728, 30, 1.35,
    LEAD + r' Penalise the $p$-th derivative in $L_2$:\enspace $\min_{s}\ \lVert s-x\rVert^{2}+\lambda\,\lVert D^{p}s\rVert^{2}$. One banded solve.',
    'Penalise the p-th derivative in L2: minimise ||s - x||^2 + lambda ||D^p s||^2. One banded solve.')
add('whittaker', 'ul', 'One sparse banded solve', 'kin_whit_str', CW, 26, 1.35, items([
    r'One sparse banded solve — $\bigO(N)$, no iteration, no convergence to check',
    r'Flat accuracy across the whole record, ends included',
    r'$\lambda$ has a closed-form map to a cutoff frequency, so no blind parameter sweep',
    r'Same machinery runs the integration direction (Tikhonov) — one implementation, both tasks']),
    'Strengths: one sparse banded solve, O(N); flat accuracy including the ends; lambda maps in closed form to a cutoff; the same machinery integrates (Tikhonov).')

# ---- knob-physics
add('knob-physics', 'p', 'closed-form map from a corner', 'kin_knob_lead', 1728, 30, 1.35,
    LEAD + r' Every $L_2$ method has a closed-form map from a corner frequency in Hz to its penalty weight',
    'Every L2 method has a closed-form map from a corner frequency in Hz to its penalty weight')
add('knob-physics', 'table', 'Whittaker–Henderson (order', 'kin_knob_table', 1728, 27, 1.3, table(
    [.30, .15, .27, .28], 'llll', ['Method', 'Parameter', 'Rule', 'Set it from'], [
        [r'\textbf{Whittaker–Henderson (order $\symbfit{p}$)}', r'$\lambda$', r'$\lambda=(2\pi f_{c})^{-2p}$', 'Highest mode you care about'],
        [r'\textbf{Tikhonov integration (order $\symbfit{n}$)}', r'$\lambda$', r'$\lambda=(2\pi f_{c})^{2n}$', 'Lowest frequency you trust'],
        [r'\textbf{Savitzky–Golay}', r'window $2M+1$', r'$f_{c}\,\Delta t\approx\dfrac{k+1}{3.2M-4.6}$', r'Schafer’s $-3$ dB rule'],
        [r'\textbf{Spectral}', 'cutoff', 'direct', 'Where the PSD meets the noise floor'],
        [r'\textbf{Total variation}', r'$\alpha$', 'no closed form', 'Sweep; scale-sensitive, normalise first'],
        [r'\textbf{State-space smoother}', r'$q$', 'fitted automatically', 'Marginal likelihood — nothing to set']], 1728, 27),
    'Tuning rules. Whittaker–Henderson (order p): lambda = (2 pi fc)^(-2p), set from the highest mode you care about. Tikhonov integration (order n): lambda = (2 pi fc)^(2n), from the lowest frequency you trust. Savitzky–Golay: window 2M+1, fc dt ≈ (k+1)/(3.2M − 4.6), Schafer’s −3 dB rule. Spectral: cutoff, direct, where the PSD meets the noise floor. Total variation: alpha, no closed form, sweep after normalising. State-space smoother: q, fitted automatically by marginal likelihood.')

# ---- tv
add('tv', 'p', 'instead of', 'kin_tv_lead', 1728, 30, 1.35,
    LEAD + r' Penalise $\lVert Du\rVert_{1}$ instead of $\lVert Du\rVert_{2}$. The $L_1$ norm does not punish a single large jump.',
    'Penalise ||Du||_1 instead of ||Du||_2. The L1 norm does not punish a single large jump.')
add('tv', 'ul', 'Several times worse than', 'kin_tv_lim', CW, 26, 1.35, items([
    r'Several times worse than an $L_2$ penalty on smooth signals — 5.1\% vs 0.5\% here',
    r'Iterative, no closed form, and the objective is non-smooth',
    r'$\alpha$ is tied to absolute signal scale — normalize before, rescale after',
    r'The naive solver silently fails to converge (next slide)']),
    'Limitations: several times worse than an L2 penalty on smooth signals (5.1% vs 0.5% here); iterative and non-smooth; alpha is tied to signal scale; the naive solver silently fails to converge.')

# ---- solver-tale
add('solver-tale', 'ul', 'Chartrand’s formulation', 'kin_solver_a', 1700, 28, 1.38, items([
    r'Chartrand’s formulation has a dense, severely ill-conditioned Hessian $A^{\mathsf{T}}A+\alpha L$.',
    r'Conjugate gradients stalls at any iteration cap. IRLS on the smoothed $L_1$ stalls too — measured rate 0.997 per iteration.',
    r'The unconverged iterate acts as extra smoothing and silently changes the answer.',
    r'MATLAB’s pcg warns. scipy’s cg returns the same unconverged vector with no warning at all.',
    r'Three successive solvers moved the same benchmark:']),
    'Chartrand’s formulation has a dense, ill-conditioned Hessian A^T A + alpha L. Conjugate gradients and IRLS stall (rate 0.997 per iteration). The unconverged iterate silently changes the answer; MATLAB pcg warns, scipy cg does not. Three successive solvers moved the same benchmark:')
add('solver-tale', 'ul', 'Under-convergence had been', 'kin_solver_b', 1700, 28, 1.38, items([
    r'Under-convergence had been flattering the method in both directions. Only the last pair is the true minimizer.',
    r'{\color{cdeep}Fix: substitute $w=Au$ to get $L_1$ trend filtering — the ADMM system is pentadiagonal and constant, so it factors once.}']),
    'Under-convergence had been flattering the method in both directions. Fix: substitute w = Au to get L1 trend filtering; the ADMM system is pentadiagonal and constant, so it factors once.')

# ---- two-defaults
add('two-defaults', 'ul', 'make_smoothing_spline', 'kin_defaults_a', CW, 27, 1.38, items([
    r'scipy’s make\_smoothing\_spline picks $\lambda$ by GCV. On the 6000-point decay it returned a flat fit: 100\% error.',
    r'The exact GCV score, with an $\bigO(N)$ trace, has a clear minimum: 1.18\% velocity error. The failure was the implementation, not GCV.']),
    'scipy make_smoothing_spline picks lambda by GCV and returned a flat fit (100% error). The exact GCV score with an O(N) trace has a clear minimum: 1.18% velocity error.')
add('two-defaults', 'ul', 'default bound', 'kin_defaults_b', CW, 27, 1.38, items([
    r'Levant’s default bound $L$ used the $(n+1)$-th derivative. The three-state form needs the third derivative bound for both outputs.',
    r'$L$ was about 100× too small: 119\% error. With $\max\lvert\text{jerk}\rvert$ from the state-space smoother: 7.7\%, at the swept optimum.']),
    'Levant’s default bound L used the (n+1)-th derivative; the three-state form needs the third-derivative bound. L was about 100 times too small (119% error); with max|jerk| from the smoother, 7.7%.')

# ---- state-space
add('state-space', 'p', 'integrated random walk', 'kin_ss_lead', 1728, 30, 1.35,
    LEAD + r' Model the signal as an integrated random walk; state $=(x,\,v,\,a,\,\text{jerk},\,\dots)$. Smooth, do not filter.',
    'Model the signal as an integrated random walk; state = (x, v, a, jerk, ...). Smooth, do not filter.')
add('state-space', 'ul', 'Self-tuning', 'kin_ss_str', CW, 25, 1.33, items([
    r'Self-tuning — the single parameter $q$ is fitted by marginal likelihood, no sweep',
    r'Handles gaps, non-uniform sampling and multirate channels natively (NaN = missing)',
    r'Returns a posterior standard deviation — error bars, not just an estimate',
    r'Does differentiation, integration AND sensor fusion with one implementation',
    r'$\bigO(N)$, and equivalent to a Gaussian process without the $\bigO(N^{3})$']),
    'Strengths: self-tuning, q fitted by marginal likelihood; handles gaps and multirate channels; returns a posterior standard deviation; differentiation, integration and fusion in one implementation; O(N), a Gaussian process without the O(N^3).')
add('state-space', 'ul', 'Costs something against', 'kin_ss_lim', CW, 25, 1.33, items([
    r'Costs something against a perfectly tuned method on very clean data (up to 3.7×)',
    r'The prior is smoothness — it rounds corners just as the $L_2$ penalties do',
    r'More code than a banded solve; the likelihood optimisation needs a sane bracket',
    r'Bias states are weakly identified over short records — a drift absorber, not a calibration']),
    'Limitations: up to 3.7 times worse than a perfectly tuned method on very clean data; rounds corners like the L2 penalties; more code; bias states weakly identified over short records.')

# ---- trust
add('trust', 'p', 'posterior band', 'kin_trust_cap', 1400, 26, 1.35,
    r'\color{muted}Acceleration from a noisy position record with its $\pm2\sigma$ posterior band. No other method in this comparison produces one.',
    'Acceleration from a noisy position record with its ±2 sigma posterior band. No other method in this comparison produces one.')

# ---- delay-space
add('delay-space', 'ul', 'Embed:', 'kin_delay_space', 1460, 28, 1.38, items([
    r'\textbf{Embed:} rows of a Hankel matrix are delay vectors $(x_{k},x_{k+1},\dots,x_{k+L-1})$, window $L=N/3$.',
    r'\textbf{Decompose:} SVD of that matrix; keep directions above the Gavish–Donoho hard threshold.',
    r'\textbf{Guard:} drop any kept direction whose mean frequency lies above the band where the PSD clears the noise floor.',
    r'\textbf{Reconstruct:} project, then average along anti-diagonals. Several sensors embed side by side.',
    r'\textbf{Differentiate} the reconstruction with a fourth-order stencil. It is band-limited, so the stencil error is negligible.',
    r'{\color{cdeep}No knob: $L$ from the record length, dimension from the threshold, guard from the spectrum.}']),
    'Embed: rows of a Hankel matrix are delay vectors (x_k, ..., x_{k+L-1}), window L = N/3. Decompose: SVD, keep directions above the Gavish–Donoho threshold. Guard: drop directions above the band where the PSD clears the noise floor. Reconstruct by anti-diagonal averaging. Differentiate with a fourth-order stencil. No knob.')

# ---- delay-ssa
add('delay-ssa', 'ul', 'quasi-periodicity', 'kin_ssa_lim', CW, 26, 1.35, items([
    r'The prior is quasi-periodicity: no gain at impacts (23\% vs 17\% for TV)',
    r'Cost grows as $L^{2}N$: about 1 s for $N=6000$, $L=2000$',
    r'Needs uniform sampling and a gap-free record',
    r'No error bars, and integration still needs a corner']),
    'Limitations: quasi-periodic prior, no gain at impacts (23% vs 17% for TV); cost grows as L^2 N, about 1 s for N = 6000, L = 2000; needs uniform gap-free sampling; no error bars.')

# ---- constants
add('constants', 'ul', 'Acceleration determines displacement', 'kin_constants', 1720, 27, 1.36, items([
    r'Acceleration determines displacement only up to $x_{0}+v_{0}t$. Those two constants are not in the data.',
    r'A DC offset of 0.5\% integrates twice into a parabola that swamps the signal within seconds.',
    r'Every working method therefore imposes a high-pass — the question is whether it admits to it.',
    r'\textbf{Detrend + high-pass filter:} fast, but the corner is chosen by eye and distorts the low modes.',
    r'\textbf{Tikhonov:} the corner appears explicitly as $\lambda=(2\pi f_{c})^{2n}$. One banded solve.',
    r'\textbf{State-space with a bias state:} the corner becomes a prior on the unobservable directions.',
    r'Choose the corner below your lowest mode of interest and above the drift band — and say what you chose.',
    r'{\color{cdeep}If you also have a displacement channel, you do not need the corner at all. That is the next slide.}']),
    'Acceleration determines displacement only up to x0 + v0 t. A 0.5% DC offset integrates into a parabola. Every method imposes a high-pass. Detrend and filter: corner chosen by eye. Tikhonov: lambda = (2 pi fc)^(2n). State-space with a bias state: a prior on the unobservable directions. With a displacement channel you need no corner.')

# ---- validating
add('validating', 'ul', 'Cross-check.', 'kin_validating', 1720, 28, 1.38, items([
    r'\textbf{Cross-check.} Differentiate the estimated displacement twice; compare with the measured acceleration in the band you trust.',
    r'\textbf{Read the posterior band.} If the feature you are interpreting is narrower than $\pm2\sigma$, it is not there.',
    r'\textbf{Move the knob.} Change the cutoff by a factor of two either way; if the answer moves more than the band, report that.',
    r'\textbf{Hold out a channel.} With two sensors, fit on one and predict the other — the honest test.',
    r'{\color{cdeep}\textbf{State your choices.} Method, cutoff or high-pass corner, and solver convergence, alongside the sampling rate.}']),
    'Cross-check the estimates against each other; read the posterior band (narrower than ±2 sigma means not there); move the knob by a factor of two; hold out a channel; state your choices.')

# ---- summary
add('summary', 'ul', 'one ill-posed problem', 'kin_summary', 1720, 28, 1.38, items([
    r'Differentiating displacement and integrating acceleration are one ill-posed problem, not two.',
    r'Noise amplification is a property of the operator. Every method you can choose adds a prior instead.',
    r'{\color{cdeep}So the real question is never ‘which filter’ — it is ‘what do I believe about this signal?’}',
    r'For smooth vibration data: a quadratic penalty, tuned from a cutoff in hertz.',
    r'For a quasi-periodic record: project onto its delay-space subspace first. Self-tuned, it beat every oracle-tuned method here.',
    r'For a genuine corner: an $L_1$ penalty, with the solver’s convergence checked.',
    r'For anything else — gaps, two sensors, no time to tune, or a need for error bars: the state-space smoother.',
    r'And if you have displacement and acceleration, fuse them. It is strictly better and it removes a knob.']),
    'Summary: one ill-posed problem; noise amplification belongs to the operator; the question is what you believe about the signal; quadratic penalty for smooth data; delay subspace for quasi-periodic records; L1 penalty for corners; state-space smoother for everything else; fuse two sensors.')

# ---- references
add('references', 'ul', 'Chartrand (2011)', 'kin_refs', 1720, 25, 1.36, items([
    r'Chartrand (2011), Numerical differentiation of noisy, nonsmooth data — \textit{ISRN Appl.\ Math.}',
    r'Eilers (2003), A perfect smoother — \textit{Anal.\ Chem.} 75:3631',
    r'Särkkä \& Solin, \textit{Applied Stochastic Differential Equations}, CUP 2019',
    r'Kim, Koh, Boyd \& Gorinevsky (2009), $\ell_{1}$ trend filtering — \textit{SIAM Review} 51(2):339',
    r'Levant (1998), Robust exact differentiation via sliding mode technique — \textit{Automatica} 34:379',
    r'Broomhead \& King (1986), Extracting qualitative dynamics from experimental data — \textit{Physica D} 20',
    r'Golyandina, Nekrutkin \& Zhigljavsky (2001), \textit{Analysis of Time Series Structure: SSA} — CRC',
    r'Gavish \& Donoho (2014), The optimal hard threshold for singular values is $4/\sqrt{3}$ — \textit{IEEE Trans.\ Inf.\ Theory}',
    r'Chelidze \& Zhou (2006), Smooth orthogonal decomposition-based vibration mode identification — \textit{J.\ Sound Vib.}']),
    'References: Chartrand 2011; Eilers 2003; Särkkä and Solin 2019; Kim, Koh, Boyd and Gorinevsky 2009; Levant 1998; Broomhead and King 1986; Golyandina, Nekrutkin and Zhigljavsky 2001; Gavish and Donoho 2014; Chelidze and Zhou 2006.')

# ---- state-a-prior
add('state-a-prior', 'table', 'bandlimited and periodic', 'kin_prior_table', 1728, 28, 1.3, table(
    [.52, .48], 'll', ['What you are willing to assume', 'The method it gives you'], [
        [r'\textbf{The signal is bandlimited and periodic}', 'Spectral / FFT differentiation'],
        [r'\textbf{It is locally a low-order polynomial}', 'Savitzky–Golay, Lanczos'],
        [r'\textbf{It lies in a low-rank delay-embedding subspace}', 'Delay SVD (SSA) / SOD — now in the toolbox'],
        [r'\textbf{Its $\symbfit{p}$-th derivative is small in $\symbfit{L}_{\symbf{2}}$}', 'Whittaker–Henderson, Tikhonov, smoothing spline'],
        [r'\textbf{Its derivative is piecewise constant ($\symbfit{L}_{\symbf{1}}$)}', 'Total variation (Chartrand)'],
        [r'\textbf{It is an integrated Wiener process}', r'Kalman / RTS smoother $\equiv$ Gaussian process'],
        [r'\textbf{Its third derivative is bounded by a known constant}', 'Levant sliding-mode (causal, online)']], 1728, 28),
    'Priors and methods: bandlimited and periodic, spectral; local polynomial, Savitzky–Golay; low-rank delay subspace, delay SVD/SOD; small p-th derivative in L2, Whittaker–Henderson, Tikhonov, smoothing spline; piecewise-constant derivative (L1), total variation; integrated Wiener process, Kalman/RTS smoother; bounded third derivative, Levant.')

# ---- comparison
add('comparison', 'table', 'Spectral (FFT)', 'kin_comparison', 1728, 24, 1.25, table(
    [.24, .17, .08, .08, .08, .10, .25], 'llccccl', ['Method', 'Prior', 'Knobs*', 'Ends', 'Gaps', 'Error bars', 'Best at'], [
        [r'\textbf{Spectral (FFT)}', 'bandlimited', '1', 'poor', 'no', 'no', 'long uniform records'],
        [r'\textbf{Savitzky–Golay}', 'local polynomial', '2', 'fair', 'no', 'no', 'quick first derivatives'],
        [r'\textbf{Whittaker / Tikhonov}', r'small $p$-th deriv.', '1', 'good', 'no', 'no', 'smooth data, both directions'],
        [r'\textbf{Smoothing spline}', r'small $p$-th deriv.', '1', 'good', 'yes', 'no', 'non-uniform sampling'],
        [r'\textbf{Total variation}', 'piecewise-const.', '1', 'good', 'no', 'no', 'impacts, stick–slip'],
        [r'\textbf{State-space smoother}', 'integrated Wiener', '0', 'good', 'yes', 'yes', 'everything else, and fusion'],
        [r'\textbf{Delay SVD / SOD (new)}', 'low-rank delay space', '0', 'good', 'no', 'no', 'free decays, ringdowns'],
        [r'\textbf{Kalman filter, causal (new)}', 'integrated Wiener', '0', 'n/a', 'yes', 'yes', 'online / control loops'],
        [r'\textbf{Levant sliding mode}', 'bounded 3rd deriv.', '1', 'n/a', 'no', 'no', 'finite-time exactness']], 1728, 24, shade=5),
    'Comparison of nine methods by prior, number of knobs, behaviour at the record ends, gap handling, error bars and best use. Only the state-space smoother and the causal Kalman filter give error bars; the state-space smoother, delay SVD/SOD and the causal Kalman filter have no knobs.')
