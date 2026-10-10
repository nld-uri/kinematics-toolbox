"""LaTeX text rendering for matplotlib figures.

use_latex_fonts() switches matplotlib to real LaTeX typesetting, so symbols and
equations on a figure match the surrounding document instead of being rendered
by matplotlib's Computer Modern lookalike (mathtext).

Needs a working TeX: latex + dvipng on PATH.  On macOS with MacTeX that is
/Library/TeX/texbin, which this module adds automatically.  If TeX is missing,
it falls back to mathtext's cm fontset -- visually close, never an exception --
and returns False so the caller can tell.

latexify(fig) rewrites every text element of a finished figure so that
characters LaTeX treats specially (%, &, _, #) and common unicode symbols
(sigma, omega, +/-, x, ~, en/em dashes) become valid LaTeX.  Spans already
inside $...$ are left untouched, so hand-written math survives.
"""
import os
import shutil

TEXBIN = "/Library/TeX/texbin"

PREAMBLE = r"\usepackage{amsmath}\usepackage{amssymb}\usepackage{type1cm}"

# unicode -> LaTeX, applied only OUTSIDE existing $...$ spans
UNICODE_MAP = {
    "\u03b1": r"$\alpha$", "\u03b2": r"$\beta$", "\u03b3": r"$\gamma$",
    "\u0394": r"$\Delta$", "\u03b4": r"$\delta$", "\u03b5": r"$\epsilon$",
    "\u03b6": r"$\zeta$",  "\u03b7": r"$\eta$",   "\u03b8": r"$\theta$",
    "\u03bb": r"$\lambda$","\u03bc": r"$\mu$",    "\u03bd": r"$\nu$",
    "\u03c0": r"$\pi$",    "\u03c1": r"$\rho$",   "\u03c3": r"$\sigma$",
    "\u03c4": r"$\tau$",   "\u03c6": r"$\phi$",   "\u03c7": r"$\chi$",
    "\u03c8": r"$\psi$",   "\u03c9": r"$\omega$", "\u03a9": r"$\Omega$",
    "\u00b1": r"$\pm$",    "\u2213": r"$\mp$",    "\u00d7": r"$\times$",
    "\u00b7": r"$\cdot$",  "\u2248": r"$\approx$","\u2260": r"$\neq$",
    "\u2264": r"$\leq$",   "\u2265": r"$\geq$",   "\u221e": r"$\infty$",
    "\u2192": r"$\rightarrow$", "\u2190": r"$\leftarrow$",
    "\u2265": r"$\geq$",   "\u223c": r"$\sim$",   "~": r"$\sim$",
    "\u2014": "---", "\u2013": "--", "\u2212": "$-$",
    "\u00b0": r"$^\circ$", "\u2032": r"$'$", "\u2033": r"$''$",
}
LATEX_ESCAPES = {"%": r"\%", "&": r"\&", "#": r"\#", "_": r"\_"}


def use_latex_fonts(serif=True, preamble=None, size=None):
    """Switch matplotlib to LaTeX text rendering. Returns True if TeX was found."""
    import matplotlib as mpl
    if preamble is None:
        preamble = PREAMBLE
    if os.path.isdir(TEXBIN) and TEXBIN not in os.environ.get("PATH", ""):
        os.environ["PATH"] = TEXBIN + os.pathsep + os.environ.get("PATH", "")
    ok = shutil.which("latex") is not None and shutil.which("dvipng") is not None
    if ok:
        mpl.rcParams.update({
            "text.usetex": True,
            "font.family": "serif" if serif else "sans-serif",
            "font.serif": ["Computer Modern Roman"],
            "text.latex.preamble": preamble,
        })
    else:
        # closest available without a TeX installation
        mpl.rcParams.update({
            "text.usetex": False, "mathtext.fontset": "cm",
            "font.family": "serif" if serif else "sans-serif",
            "font.serif": ["CMU Serif", "DejaVu Serif"],
        })
    if size is not None:
        mpl.rcParams["font.size"] = size
    return ok


def tex_escape(s):
    """Make one string safe for LaTeX, preserving any existing $...$ math spans."""
    out, math = [], False
    for part in str(s).split("$"):
        if math:
            out.append("$" + part + "$")
        else:
            for k, v in LATEX_ESCAPES.items():
                part = part.replace(k, v)
            for k, v in UNICODE_MAP.items():
                part = part.replace(k, v)
            out.append(part)
        math = not math
    joined = "".join(out)
    # a trailing unmatched $ would break the run; drop it rather than fail
    return joined if joined.count("$") % 2 == 0 else joined.replace("$", "")


def escaping_formatter(inner):
    """Wrap a matplotlib Formatter so its output is LaTeX-safe.

    Two traps this avoids, both of which fail SILENTLY:
      * it must subclass Formatter -- set_major_formatter wraps a bare
        callable in a FuncFormatter, which never forwards set_locs, and
        ScalarFormatter then returns an empty string for every tick;
      * it must delegate format_ticks, the API matplotlib uses at draw time,
        so stateful formatters (ScalarFormatter's offset and order of
        magnitude, LogFormatter's minor-tick suppression) keep working.

    Defined inside a function so this module is valid as a skill sidecar.
    """
    from matplotlib.ticker import Formatter

    class _EscapingFormatter(Formatter):
        _escaped = True

        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def __call__(self, x, pos=None):
            return tex_escape(self._inner(x, pos))

        def format_ticks(self, values):
            return [tex_escape(v) for v in self._inner.format_ticks(values)]

        def set_axis(self, axis):
            self._inner.set_axis(axis)

        def get_offset(self):
            return tex_escape(self._inner.get_offset())

    return _EscapingFormatter(inner)


def latexify(fig):
    """Escape every text element of a finished figure. Call just before savefig."""
    import matplotlib as mpl
    if not mpl.rcParams.get("text.usetex", False):
        return fig
    # Tick labels are produced by a Formatter at DRAW time, so escaping the
    # Text objects is not enough.  Delegate through the formatter instead: an
    # unescaped %% makes LaTeX treat the rest of the label as a comment, and the
    # label silently loses its tail rather than raising.
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            for get, set_ in ((axis.get_major_formatter, axis.set_major_formatter),
                              (axis.get_minor_formatter, axis.set_minor_formatter)):
                f = get()
                if not getattr(f, "_escaped", False):
                    set_(escaping_formatter(f))
    for t in fig.findobj(mpl.text.Text):
        s = t.get_text()
        if not s or not s.strip():
            continue
        if "\\mathdefault" in s:     # matplotlib's own auto tick labels
            continue
        e = tex_escape(s)
        if e != s:
            t.set_text(e)
    return fig


# ---------------------------------------------------------------- MATLAB colors
# MATLAB's default axes ColorOrder since R2014b, in order.
MATLAB_ORDER = ["#0072BD", "#D95319", "#EDB120", "#7E2F8E",
                "#77AC30", "#4DBEEE", "#A2142F"]

MATLAB = {"blue": "#0072BD", "orange": "#D95319", "yellow": "#EDB120",
          "purple": "#7E2F8E", "green": "#77AC30", "cyan": "#4DBEEE",
          "darkred": "#A2142F",
          # not part of ColorOrder but MATLAB's usual neutrals
          "black": "#000000", "gray": "#808080", "lightgray": "#BFBFBF",
          "darkyellow": "#9C7A0A"}   # legible text version of the yellow


def use_matlab_colors():
    """Set the matplotlib property cycle to MATLAB's default ColorOrder.

    Applies to line plots, bars and any solid fill that takes its color from
    the cycle.  Colormaps (gradients) are unaffected -- MATLAB's parula has no
    matplotlib equivalent; use 'viridis' for a perceptually uniform ramp.
    """
    import matplotlib as mpl
    from cycler import cycler
    mpl.rcParams["axes.prop_cycle"] = cycler(color=MATLAB_ORDER)
    return MATLAB_ORDER


def apply_preferences(sizes=None, serif=True):
    """LaTeX text + MATLAB colors in one call. Returns True if TeX was found."""
    ok = use_latex_fonts(serif=serif)
    use_matlab_colors()
    if sizes is not None:
        import matplotlib as mpl
        mpl.rcParams.update({"font.size": sizes[0], "axes.titlesize": sizes[0],
                             "axes.labelsize": sizes[0], "legend.fontsize": sizes[1],
                             "xtick.labelsize": sizes[2], "ytick.labelsize": sizes[2]})
    return ok
