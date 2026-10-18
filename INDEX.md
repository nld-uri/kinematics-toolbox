# kinematics_toolbox

Model-free differentiation and integration of measured motion: velocity and
acceleration from a noisy displacement record, velocity and displacement from a
drifting accelerometer, and fusion of both channels. No model of the system is
used anywhere -- only a regularity prior on the signal.

Full methods note, benchmark tables, tuning rules and decision guide: `README.md`.

## Layout

    README.md          methods note -- read this first
    python/            kinematics.py (the library), bench.py / bench_delay.py (ground truth + sweeps),
                       figs.py / figs_slides.py / figs_delay.py (figures),
                       build_deck_nld.py (current talk, NLD template; deck_lib.py / build_deck.py
                       built the earlier version and are kept for its figures' history)
    matlab/            MATLAB port of every routine; base MATLAB except Levant default L
                       and trapz-detrend (Signal Processing Toolbox); same names as Python
                       (one exception: kin_noisevar here, kin_noise_var in Python)
    figures/           s_*.{pdf,png} talk figures, fig1/fig2 paper figures
                       PDFs are vector with fonttype=42 -- editable in Illustrator/Affinity
    data/              benchmark_summary.csv, diff_noise_sweep.csv, delay_benchmark.csv
    talk/              differentiation_integration_talk.pdf (54 slides, export of the live HTML deck);
                       differentiation_integration_talk.pptx (earlier PowerPoint version); live/ (animation pages + builder)

## Validating the MATLAB port

    >> cd matlab
    >> test_kinematics

Prints a pass/fail table against reference vectors in kin_reference.mat, which
were produced by the Python library. Cross-validation status and the per-routine
agreement levels are recorded in README.md.

## Also available as a skill

`kinematics-from-signals` ships these helpers preloaded into the kernel, so a new
record can be processed without rebuilding anything from this folder.
