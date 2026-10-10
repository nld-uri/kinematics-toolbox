
import importlib, deck_lib as DL
importlib.reload(DL)
from pptx import Presentation
from pptx.util import Inches

def make(path):
    prs = Presentation()
    prs.slide_width = Inches(DL.W); prs.slide_height = Inches(DL.H)

    DL.title_slide(prs,
        "Differentiating and Integrating\nMeasured Motion",
        "Model-free estimation of velocity and acceleration from displacement,\nand of velocity and displacement from acceleration",
        "Nonlinear Dynamics Laboratory  \u00b7  Mechanical, Industrial and Systems Engineering",
        "University of Rhode Island")

    DL.bullets(prs, "Two problems every vibration lab has",
        [ "You measured displacement (laser vibrometer, DIC, encoder) and you need velocity and acceleration.",
          (1, "Restoring-force surfaces, NNM energy balance, damping identification, model updating."),
          "You measured acceleration (the cheap, rugged, ubiquitous sensor) and you need velocity and displacement.",
          (1, "Mode shapes in physical units, drift-free response, base-excitation compensation, fatigue cycles."),
          "Both are routine requests. Both are harder than they look.",
          "The naive answers \u2014 finite differences one way, cumulative trapezoid the other \u2014 fail, and fail differently." ],
        sub="The setting: one sensor type, and you need the other kinematic quantities",
        notes="[~1.5 min] Open by asking who in the room has done each of these. Frame the talk: "
              "this is not a survey of filters, it is one idea \u2014 that both tasks are the same inverse "
              "problem \u2014 plus the practical consequences. Everything shown is measured on a benchmark "
              "with exact ground truth, so every error quoted is a true error, not a comparison between "
              "two estimates.")

    DL.bullets(prs, "They are the same problem, run in opposite directions",
        [ "Write the measurement as  y = A u + e,  with A the integration operator.",
          (1, "Differentiation: u is the derivative you want, A integrates it back to what you measured."),
          (1, "Integration: u is the displacement, A integrates the acceleration twice."),
          "A is compact. Its inverse is unbounded. This is the definition of an ill-posed inverse problem.",
          "Noise is amplified without limit \u2014 by \u03c9 per derivative going up, by 1/\u03c9 per integration going down.",
          "No amount of cleverness removes this. It is a property of the operator, not of your algorithm.",
          "Every usable method therefore adds a regularity prior. That is the only thing that distinguishes them." ],
        sub="One framing that organises the whole landscape",
        notes="[~2.5 min] This is the conceptual spine of the talk \u2014 spend time here. The key move "
              "is recognising that differentiating and integrating are not opposites to be treated with "
              "different toolkits; they are the same compact operator inverted in two directions. "
              "Emphasise the last line: when someone asks 'which filter should I use', the honest "
              "reformulation is 'what do you believe about your signal?'")

    DL.figure(prs, "Why it is ill-posed", "s_illposed.png",
        caption="Left: the amplification factor is unbounded at both ends. Right: the same effect on a real record \u2014 "
                "a 1% noise floor on position dominates the acceleration estimate above about 30 Hz.",
        notes="[~2 min] Left panel is the theory in one picture: differentiation multiplies by \u03c9, "
              "integration divides by it, and both diverge. Right panel makes it concrete. The gold "
              "curve is the true acceleration spectrum \u2014 it rolls off. The red curve is what you get "
              "from differentiating a 1% noisy position twice: it RISES with frequency. Where they "
              "separate, around 30 Hz, everything to the right is amplified noise. "
              "Point out that the only information about the third and fourth modes is already buried.")

    DL.figure(prs, "What happens if you ignore it", "s_naive.png",
        caption="Left: second central difference of a 1% noisy position \u2014 209% rms error. "
                "Right: plain cumulative trapezoid of an accelerometer with a 0.5% offset \u2014 64x off scale in 3 s.",
        notes="[~1.5 min] Two failure modes, deliberately shown side by side because they look nothing "
              "alike. Differentiation fails by adding high-frequency noise you can see. Integration fails "
              "by adding a low-frequency drift that looks smooth and plausible \u2014 which is far more "
              "dangerous, because a drifting displacement record can survive review. "
              "Note the asymmetry: the differentiated signal is obviously wrong; the integrated one is quietly wrong.")

    DL.table(prs, "The only cure: state a prior",
        ["What you are willing to assume", "The method it gives you"],
        [["The signal is bandlimited and periodic",         "Spectral / FFT differentiation"],
         ["It is locally a low-order polynomial",           "Savitzky\u2013Golay, Lanczos"],
         ["It lies in a low-rank delay-embedding subspace", "SVD / SSA"],
         ["Its p-th derivative is small in L2",             "Whittaker\u2013Henderson, Tikhonov, smoothing spline"],
         ["Its derivative is piecewise constant (L1)",      "Total variation (Chartrand)"],
         ["It is an integrated Wiener process",             "Kalman / RTS smoother  \u2261  Gaussian process"],
         ["Its derivative is bounded by a known constant",  "Levant sliding-mode (causal, online)"]],
        [1.15, 1.0],
        sub="Methods differ only in which regularity prior they impose \u2014 pick the row you actually believe",
        notes="[~2 min] This table is the map for the rest of the talk. Walk down it once. "
              "Stress that these are not seven unrelated tricks: they are seven answers to one question. "
              "The two most people already know are the first and third rows. "
              "Rows 4\u20137 are the ones that repay attention. Say explicitly: if you cannot state which "
              "row you believe, you are not choosing a method, you are accepting a default.")

    DL.proscons(prs, "Spectral (FFT) differentiation",
        "Multiply the spectrum by (i\u03c9)\u207f, roll off above a cutoff, transform back.",
        ["Exact for a bandlimited periodic signal \u2014 no discretisation error at all",
         "Most accurate of any method in the interior of a long record (0.54% velocity error here)",
         "Trivial to implement, O(N log N), and the cutoff has an obvious physical meaning",
         "The natural choice when you already work in the frequency domain"],
        ["Enforces periodicity \u2014 catastrophic at the record ends (next slide)",
         "Needs uniform sampling and a gap-free record",
         "Cutoff must be chosen; too high amplifies noise, too low removes signal",
         "Leakage if the record is not an integer number of periods (taper, then divide it out)"],
        "The record is long, uniformly sampled, and you only care about the middle of it.",
        notes="[~1.5 min] Most people in a vibrations group already use this. Give it full credit: "
              "in the interior it genuinely wins. The point of the next slide is that 'in the interior' "
              "is doing a lot of work in that sentence.")

    DL.figure(prs, "The FFT caveat that costs people real results", "s_edges.png",
        caption="Velocity over the last 0.2 s of a 3 s free decay. Interior error 0.54%; over the full record, 8.4% \u2014 a 15x degradation.",
        notes="[~2 min] This is the single most practically important slide for anyone doing free-decay "
              "testing. The FFT must make the signal periodic, so it splices the end of the record to "
              "the beginning \u2014 and a decay has a large amplitude at the start and a small one at the end. "
              "The estimate rings to bridge that discontinuity. "
              "Say the consequence out loud: in free-decay work the information you want \u2014 the "
              "high-amplitude, strongly nonlinear cycles \u2014 is exactly at the start of the record, "
              "in the region the method corrupts. Whittaker and the state-space smoother are flat across "
              "the whole record; that is why they are the defaults later in the talk.")

    DL.proscons(prs, "Savitzky\u2013Golay",
        "Fit a low-order polynomial in a sliding window; differentiate the polynomial analytically.",
        ["Simple, fast, and available in every toolbox",
         "No periodicity assumption \u2014 much better behaved at the ends than the FFT",
         "Preserves peak heights and widths better than a plain moving average",
         "Window length maps to a cutoff via Schafer's rule, so it can be set from physics"],
        ["Two knobs (window, polynomial order) that interact",
         "Implicitly assumes the signal is polynomial over the window \u2014 poor for lightly damped resonance",
         "Noticeably worse than an L2 penalty for second derivatives (2.4% vs 0.9% here)",
         "Edge behaviour depends on the padding convention, which differs between implementations"],
        "You want something defensible in ten lines with no linear solve, and first derivatives are enough.",
        notes="[~1.5 min] Worth including because it is the most widely used method in experimental "
              "practice and it is not a bad one. The honest summary: fine for velocity, mediocre for "
              "acceleration. Mention the implementation detail \u2014 MATLAB and scipy pad differently at "
              "the ends, which is a real reproducibility trap when moving code between them.")

    DL.proscons(prs, "Whittaker\u2013Henderson and Tikhonov",
        "Penalise the p-th derivative in L2: min \u2016s \u2212 x\u2016\u00b2 + \u03bb\u2016D\u1d56s\u2016\u00b2. One banded solve.",
        ["One sparse banded solve \u2014 O(N), no iteration, no convergence to check",
         "Flat accuracy across the whole record, ends included",
         "\u03bb has a closed-form map to a cutoff frequency, so no blind parameter sweep",
         "Same machinery runs the integration direction (Tikhonov) \u2014 one implementation, both tasks"],
        ["Still one knob, and the optimum is sharp for second derivatives",
         "Quadratic penalty rounds off genuine corners \u2014 wrong prior for impacting systems",
         "The normal matrix is badly scaled; use a sparse direct solver, not an iterative one",
         "No uncertainty estimate comes out of it"],
        "This is the sensible default for smooth vibration data. Start here.",
        vcolor=DL.GOOD,
        notes="[~2 min] This is the recommendation for most of the audience's work. Emphasise the "
              "tuning rule \u2014 the response is 1/(1 + \u03bb\u03c9^2p), so \u03bb = (2\u03c0fc)^\u22122p converts a cutoff in hertz "
              "into the penalty weight. That single fact removes most of the folklore around 'choosing "
              "the smoothing parameter'. Note that Tikhonov integration is the same equation read "
              "right to left.")

    DL.figure(prs, "Every method has an optimum you have to find", "s_tuning.png",
        caption="Error against exact ground truth as the cutoff is swept, 1% position noise. "
                "The dashed line is the self-tuned state-space smoother, which has no knob at all.",
        notes="[~2 min] The U-shape is the bias\u2013variance trade-off made visible: too much smoothing on "
              "the left, too much noise on the right. Two things to point out. First, the minima are "
              "sharp \u2014 a factor of three error in the cutoff costs an order of magnitude in the "
              "acceleration estimate. Second, and this is the uncomfortable part, these curves were "
              "computed WITH knowledge of the true answer. On a real record you cannot draw them. "
              "That is the argument for the method on the dashed line.")

    DL.table(prs, "Setting the knob from physics, not from a sweep",
        ["Method", "Parameter", "Rule", "Set it from"],
        [["Whittaker\u2013Henderson (order p)", "\u03bb", "\u03bb = (2\u03c0 f\u1d9c)\u207b\u00b2\u1d56", "Highest mode you care about"],
         ["Tikhonov integration (order n)", "\u03bb", "\u03bb = (2\u03c0 f\u1d9c)\u00b2\u207f", "Lowest frequency you trust"],
         ["Savitzky\u2013Golay", "window 2M+1", "f\u1d9c\u0394t \u2248 (k+1)/(3.2M \u2212 4.6)", "Schafer's \u22123 dB rule"],
         ["Spectral", "cutoff", "direct", "Where the PSD meets the noise floor"],
         ["Total variation", "\u03b1", "no closed form", "Sweep; scale-sensitive, normalise first"],
         ["State-space smoother", "q", "fitted automatically", "Marginal likelihood \u2014 nothing to set"]],
        [1.35, 0.55, 1.15, 1.25],
        sub="Every L2 method has a closed-form map from a corner frequency in Hz to its penalty weight",
        notes="[~1.5 min] Practical slide \u2014 tell the audience to photograph it. The message is that "
              "'tune lambda by cross-validation' is usually unnecessary: for the quadratic-penalty "
              "family the map from a physically meaningful cutoff to the penalty weight is exact. "
              "Start the cutoff at two to three times the highest mode of interest and move it only if "
              "the residual shows structure.")

    DL.proscons(prs, "Total variation (L1)",
        "Penalise \u2016Du\u2016\u2081 instead of \u2016Du\u2016\u2082. The L1 norm does not punish a single large jump.",
        ["The only family that preserves a genuine discontinuity in the derivative",
         "Best method tested at an impact: 19.2% vs 22\u201327% for every quadratic penalty",
         "Physically the right prior for impacts, stick\u2013slip, backlash, dry friction reversal",
         "Recovers a piecewise-constant derivative exactly in the noise-free limit"],
        ["Several times worse than an L2 penalty on smooth signals \u2014 5.1% vs 0.5% here",
         "Iterative, no closed form, and the objective is non-smooth",
         "\u03b1 is tied to absolute signal scale \u2014 normalise before, rescale after",
         "The naive solver silently fails to converge (next slide)"],
        "Your derivative genuinely jumps. Otherwise do not \u2014 it is the wrong prior for smooth data.",
        vcolor=DL.WARN,
        notes="[~1.5 min] Be balanced here. TV is fashionable and it is often applied where it does not "
              "belong. The honest position: it wins decisively at a corner and loses decisively on "
              "smooth data, and both results are correct because they reflect the prior. "
              "For this audience the relevant application is vibro-impact and friction-damped systems.")

    DL.figure(prs, "Where the L1 penalty earns its place", "s_impact.png",
        caption="Vibro-impact oscillator, restitution 0.85. Left: one impact, velocity jumps. "
                "Right: velocity error within \u00b14 ms of contact, best setting per method.",
        notes="[~1.5 min] The left panel shows the mechanism: the quadratic penalties round the corner "
              "because a large second difference is expensive under L2; L1 lets one jump through. "
              "The right panel quantifies it \u2014 a 14% reduction against the best quadratic method. "
              "Be honest that this is a real but modest margin, and say why it matters anyway: if you "
              "are measuring restitution coefficients, the impact velocity IS the measurement.")

    DL.bullets(prs, "A cautionary tale: the solver was the result",
        [ "Chartrand's formulation has a dense, severely ill-conditioned Hessian A\u1d40A + \u03b1L.",
          "Conjugate gradients stalls at any iteration cap. IRLS on the smoothed L1 stalls too \u2014 measured rate 0.997 per iteration.",
          "The unconverged iterate acts as extra smoothing and silently changes the answer.",
          (1, "MATLAB's pcg warns. scipy's cg returns the same unconverged vector with no warning at all."),
          "Three successive solvers moved the same benchmark:",
          (1, "smooth signal  3.77%  \u2192  4.93%  \u2192  5.07%      near impacts  17.9%  \u2192  16.6%  \u2192  19.2%"),
          "Under-convergence had been flattering the method in both directions. Only the last pair is the true minimiser.",
          "Fix: substitute w = Au to get L1 trend filtering \u2014 the ADMM system is pentadiagonal and constant, so it factors once." ],
        sub="Reported numbers for an iterative method are claims about the solver as much as the estimator",
        size=17,
        notes="[~2 min] This slide is here because it generalises far beyond total variation. The "
              "specific lesson: whenever you report a result from an iterative method, the convergence "
              "status is part of the result. The general lesson: a silent solver is worse than a noisy "
              "one \u2014 scipy's cg returning an unconverged answer without complaint is how this went "
              "unnoticed through several rounds. "
              "If the audience takes one methodological point from the talk, make it this one.")

    DL.proscons(prs, "State-space: the Kalman / RTS kinematic smoother",
        "Model the signal as an integrated random walk; state = [x, v, a, jerk, ...]. Smooth, do not filter.",
        ["Self-tuning \u2014 the single parameter q is fitted by marginal likelihood, no sweep",
         "Handles gaps, non-uniform sampling and multirate channels natively (NaN = missing)",
         "Returns a posterior standard deviation \u2014 error bars, not just an estimate",
         "Does differentiation, integration AND sensor fusion with one implementation",
         "O(N), and equivalent to a Gaussian process without the O(N\u00b3)"],
        ["Costs something against a perfectly tuned method on very clean data (up to 3.7x)",
         "The prior is smoothness \u2014 it rounds corners just as the L2 penalties do",
         "More code than a banded solve; the likelihood optimisation needs a sane bracket",
         "Bias states are weakly identified over short records \u2014 a drift absorber, not a calibration"],
        "You want one tool that covers every case, or you have two sensors, or you need uncertainty.",
        vcolor=DL.GOOD,
        notes="[~2.5 min] This is the recommendation to end on. Explain the equivalence chain briefly: "
              "an integrated-Wiener state-space model IS a smoothing spline IS a Gaussian process with "
              "a particular kernel \u2014 but the recursive form is linear time instead of cubic. "
              "The self-tuning is the practical selling point: the marginal likelihood of the data under "
              "the model is a function of q alone, so you maximise it and you are done. No held-out set, "
              "no L-curve, no eyeballing.")

    DL.figure(prs, "What does self-tuning actually cost?", "s_selftune.png",
        caption="Ratio of the self-tuned error to the best error achieved by ANY method in this study "
                "with its knob tuned against ground truth.",
        notes="[~1.5 min] An honest accounting, and the shape is favourable. On very clean data the "
              "self-tuned smoother pays up to 3.7x \u2014 but there the absolute errors are a fraction of a "
              "percent and the choice does not matter. At 5% noise, where tuning actually decides the "
              "answer, it reaches parity. "
              "Practical note: raise the state dimension from 4 to 5 for clean records if you want "
              "acceleration \u2014 it roughly halves the low-noise penalty. "
              "Remember the comparison is against an oracle you do not have on real data.")

    DL.figure(prs, "It tells you how much to trust it", "s_uncertainty.png",
        caption="Acceleration from a noisy position record with its \u00b12\u03c3 posterior band. "
                "No other method in this comparison produces one.",
        notes="[~1 min] Short slide but an important one. Every other method returns a curve; this one "
              "returns a distribution. The practical rule: if the feature you are about to interpret is "
              "narrower than the band, it is not there. "
              "Mention that the band widens automatically over gaps and at the record ends, which is "
              "exactly the behaviour you want and exactly what the FFT does not do.")

    DL.bullets(prs, "Integration has an extra problem: the constants",
        [ "Acceleration determines displacement only up to  x\u2080 + v\u2080t.  Those two constants are not in the data.",
          "A DC offset of 0.5% integrates twice into a parabola that swamps the signal within seconds.",
          "Every working method therefore imposes a high-pass \u2014 the question is whether it admits to it.",
          (1, "Detrend + high-pass filter: fast, but the corner is chosen by eye and distorts the low modes."),
          (1, "Tikhonov: the corner appears explicitly as \u03bb = (2\u03c0f\u1d9c)\u00b2\u207f. One banded solve."),
          (1, "State-space with a bias state: the corner becomes a prior on the unobservable directions."),
          "Choose the corner below your lowest mode of interest and above the drift band \u2014 and say what you chose.",
          "If you also have a displacement channel, you do not need the corner at all. That is the next slide." ],
        sub="Two integration constants are unobservable \u2014 every method makes an assumption, so make yours explicit",
        size=18,
        notes="[~2 min] The conceptual point: this is not a numerical difficulty, it is a genuine "
              "identifiability gap. No algorithm can recover what the sensor did not measure. "
              "What distinguishes good practice from bad is whether the assumption is stated. "
              "A detrend-and-filter pipeline makes exactly the same assumption as the Tikhonov solve, "
              "but hides it in a filter design step. Encourage the audience to report their high-pass "
              "corner in papers the way they report a sampling rate.")

    DL.figure(prs, "Integration done three ways", "s_integration.png",
        caption="Displacement recovered from an accelerometer with 1% noise, 0.5% drift and a 0.5% offset. "
                "Regularised methods overlay the truth; the plain trapezoid needs its own axis.",
        notes="[~1 min] Quick slide. The two regularised curves are indistinguishable from truth at this "
              "scale \u2014 0.9% and 1.7% rms. The grey curve is on a separate axis because it is 64 times "
              "larger. Point at the grey curve and note that it is smooth and monotone: it looks like a "
              "physical drift, not like an error, which is what makes it dangerous.")

    DL.figure(prs, "If you have both sensors, use both at once", "s_fusion.png",
        caption="One state-space smoother, 200 Hz displacement at 3% noise fused with 2 kHz acceleration at 1% noise plus drift.",
        notes="[~2 min] The strongest practical result in the talk. Fusion beats either channel alone on "
              "all three kinematics, and the reason is structural, not numerical: displacement observes "
              "the low frequencies where the accelerometer has nothing, and acceleration observes the "
              "high frequencies where the displacement sensor is noise-limited. "
              "Critically, fusing removes the high-pass corner entirely \u2014 the displacement channel makes "
              "the two integration constants identifiable, so there is no longer an arbitrary choice to "
              "defend. Note the sampling rates differ by 10x and the smoother does not care.")

    DL.table(prs, "The comparison on one slide",
        ["Method", "Prior", "Knobs", "Ends", "Gaps", "Error bars", "Best at"],
        [["Spectral (FFT)", "bandlimited", "1", "poor", "no", "no", "long uniform records"],
         ["Savitzky\u2013Golay", "local polynomial", "2", "fair", "no", "no", "quick first derivatives"],
         ["Whittaker / Tikhonov", "small p-th deriv.", "1", "good", "no", "no", "smooth data, both directions"],
         ["Smoothing spline", "small p-th deriv.", "1", "good", "yes", "no", "non-uniform sampling"],
         ["Total variation", "piecewise-const.", "1", "good", "no", "no", "impacts, stick\u2013slip"],
         ["State-space smoother", "integrated Wiener", "0", "good", "yes", "yes", "everything else, and fusion"],
         ["Levant sliding mode", "bounded deriv.", "2", "n/a", "no", "no", "online / control loops"]],
        [1.5, 1.2, 0.5, 0.5, 0.45, 0.6, 1.6],
        fs=13, hfs=12,
        sub="Knobs = free parameters you must choose; the state-space smoother fits its one parameter itself",
        notes="[~2 min] The summary slide \u2014 leave it up while you talk. Read down the 'knobs' column: "
              "that is the column that determines how reproducible somebody else's result will be. "
              "Read down 'error bars': only one method gives you any. "
              "Invite questions here if you are running to time; the remaining slides are practical advice.")

    DL.bullets(prs, "What to actually do",
        [ "Smooth data, one sensor, want it simple  \u2192  Whittaker\u2013Henderson, cutoff from physics.",
          "Smooth data, want no knob or need uncertainty  \u2192  state-space smoother, nstate = 4 (5 if very clean).",
          "Two sensors  \u2192  always fuse them in one smoother. Never process them separately and reconcile after.",
          "Impacts, backlash, stick\u2013slip  \u2192  total variation, and check that the solver converged.",
          "Integrating acceleration alone  \u2192  Tikhonov or a bias-state smoother; report the high-pass corner.",
          "Online or in a control loop  \u2192  Levant's differentiator; everything else here is offline and zero-phase.",
          "Never: a bare finite difference, or a bare cumulative trapezoid." ],
        sub="A decision list, in the order the questions actually arise",
        size=18,
        notes="[~1.5 min] The takeaway slide. Read it as a sequence of questions rather than a ranking. "
              "The third line is the one most often violated in practice \u2014 people process displacement "
              "and acceleration separately, get two different answers, and then argue about which to "
              "trust. Fusing them is not an advanced technique; it is one function call.")

    DL.bullets(prs, "Validating on a record with no ground truth",
        [ "Everything shown here was measured against an exact solution. On your data you have none \u2014 so:",
          "Cross-check. Differentiate the estimated displacement twice; compare with the measured acceleration in the band you trust.",
          "Read the posterior band. If the feature you are interpreting is narrower than \u00b12\u03c3, it is not there.",
          "Move the knob. Change the cutoff by a factor of two either way; if the answer moves more than the band, report that.",
          "Hold out a channel. With two sensors, fit on one and predict the other \u2014 the honest test.",
          "State your choices. Method, cutoff or high-pass corner, and solver convergence, alongside the sampling rate." ],
        sub="Four checks that cost minutes and one habit that costs nothing",
        size=18,
        notes="[~1.5 min] Close the methods content here. The last bullet is a plea: these choices are "
              "as consequential as the sampling rate and are almost never reported. "
              "If a result depends on the cutoff, that dependence belongs in the paper.")

    DL.bullets(prs, "Summary",
        [ "Differentiating displacement and integrating acceleration are one ill-posed problem, not two.",
          "Noise amplification is a property of the operator. Every method you can choose adds a prior instead.",
          "So the real question is never 'which filter' \u2014 it is 'what do I believe about this signal?'",
          "For smooth vibration data: a quadratic penalty, tuned from a cutoff in hertz.",
          "For a genuine corner: an L1 penalty, with the solver's convergence checked.",
          "For anything else \u2014 gaps, two sensors, no time to tune, or a need for error bars: the state-space smoother.",
          "And if you have displacement and acceleration, fuse them. It is strictly better and it removes a knob." ],
        size=19,
        notes="[~1.5 min] Close on the third bullet \u2014 it is the reframing that makes the rest follow. "
              "Then offer the code. Total elapsed should be about 30 minutes with a little room for "
              "questions during the comparison table.")

    DL.bullets(prs, "Implementation and references",
        [ "Python and base-MATLAB implementations of every method here, with identical function names.",
          (1, "kin_diff_whittaker, kin_diff_spectral, kin_diff_savgol, kin_diff_tvreg"),
          (1, "kin_int_tikhonov, kin_int_spectral, kin_noise_var"),
          (1, "kin_smooth \u2014 differentiation, integration and fusion in one self-tuning routine"),
          "Cross-validated between the two languages: 12 of 12 checks pass, agreement 1e-16 to 1e-5.",
          "Key references:",
          (1, "Chartrand (2011), Numerical differentiation of noisy, nonsmooth data \u2014 ISRN Appl. Math."),
          (1, "Eilers (2003), A perfect smoother \u2014 Anal. Chem. 75:3631 (Whittaker\u2013Henderson)"),
          (1, "S\u00e4rkk\u00e4 & Solin, Applied Stochastic Differential Equations, CUP 2019 (state-space / GP equivalence)"),
          (1, "Schafer (2011), What is a Savitzky\u2013Golay filter? \u2014 IEEE Signal Process. Mag. 28(4):111"),
          (1, "Kim, Koh, Boyd & Gorinevsky (2009), l1 trend filtering \u2014 SIAM Review 51(2):339"),
          (1, "Levant (1998), Robust exact differentiation via sliding mode technique \u2014 Automatica 34:379") ],
        size=17,
        notes="[~1 min] Hand off the code. Offer to run any of these on somebody's record after the talk "
              "\u2014 that is usually the most productive follow-up. The references are the primary sources "
              "for each family, not a full bibliography.")

    prs.save(path)
    return len(prs.slides.__iter__.__self__._sldIdLst)
