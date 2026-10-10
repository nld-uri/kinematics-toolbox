"""Rebuild the differentiation/integration talk in the NLD brand template and
add the October 2026 material (delay reconstruction, causal filter, repaired
defaults, full MATLAB port).

    python build_deck_nld.py OLD.pptx NLD-template.potx FIGDIR ICON.png OUT.pptx

OLD.pptx is the 26-slide deck before the rebrand
(git show 08cfe8b:talk/differentiation_integration_talk.pptx > old.pptx); it is the
source of truth for the 26 original slides' text and notes: titles, bullets, tables, figures and speaker
notes are read from it, so hand edits made there survive.  Content changes and
new slides are written below in EDITS / NEW.
"""
import copy, io, os, shutil, sys, tempfile, zipfile
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from lxml import etree

NAVY = RGBColor(0x13, 0x24, 0x33); PAPER = RGBColor(0xF7, 0xF6, 0xF2)
COPPER = RGBColor(0xB4, 0x62, 0x2A); COPPER_DEEP = RGBColor(0x9A, 0x53, 0x23)
MUTED = RGBColor(0x5B, 0x61, 0x68); HAIR = RGBColor(0xDC, 0xD9, 0xD2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF); ROWALT = RGBColor(0xEF, 0xED, 0xE7)

# slide types of the original deck, in order (from build_deck.py)
TYPES = ["title", "bullets", "bullets", "figure", "figure", "table", "pc", "figure", "pc",
         "pc", "figure", "table", "pc", "figure", "bullets", "pc", "figure", "figure",
         "bullets", "figure", "figure", "table", "bullets", "bullets", "bullets", "bullets"]


# ------------------------------------------------------------ reading old deck
def _paras(tf):
    out = []
    for p in tf.paragraphs:
        t = "".join(r.text for r in p.runs)
        if not t.strip():
            continue
        lvl = 1 if t.startswith("      ") else 0
        t = t.strip()
        for pre in ("—  ", "•  "):
            if t.startswith(pre):
                t = t[len(pre):]
        out.append((lvl, t))
    return out


def read_old(path):
    prs = Presentation(path)
    slides = []
    for s, kind in zip(prs.slides, TYPES):
        texts = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
        d = {"kind": kind, "notes": s.notes_slide.notes_text_frame.text if s.has_notes_slide else "",
             "title": texts[0].text_frame.text.strip()}
        if kind == "title":
            d["sub"] = texts[1].text_frame.text
        elif kind == "bullets":
            d["sub"] = texts[1].text_frame.text.strip() if len(texts) > 2 else None
            d["items"] = _paras(texts[-1].text_frame)
        elif kind == "figure":
            pic = [sh for sh in s.shapes if sh.shape_type == 13][0]
            d["img"] = pic.image.blob
            d["caption"] = texts[1].text_frame.text.strip() if len(texts) > 1 else None
        elif kind == "table":
            tb = [sh for sh in s.shapes if sh.has_table][0].table
            d["sub"] = texts[1].text_frame.text.strip() if len(texts) > 1 else None
            d["rows"] = [[c.text for c in r.cells] for r in tb.rows]
            d["widths"] = [c.width for c in tb.columns]
        elif kind == "pc":
            d["idea"] = texts[1].text_frame.text.strip()
            d["pros"] = [t for _, t in _paras(texts[3].text_frame)]
            d["cons"] = [t for _, t in _paras(texts[5].text_frame)]
            d["verdict"] = texts[6].text_frame.text.replace("USE IT WHEN", "").strip()
        slides.append(d)
    return slides


# ------------------------------------------------------------ template helpers
def open_template(potx):
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "t.pptx")
    with zipfile.ZipFile(potx) as zi, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data = zi.read(it.filename)
            if it.filename == "[Content_Types].xml":
                data = data.replace(b"presentationml.template.main+xml",
                                    b"presentationml.presentation.main+xml")
            zo.writestr(it, data)
    prs = Presentation(out)
    lst = prs.slides._sldIdLst
    for sid in list(lst):
        prs.part.drop_rel(sid.rId)
        lst.remove(sid)
    return prs


def layout(prs, name):
    for l in prs.slide_layouts:
        if l.name == name:
            return l
    raise KeyError(name)


def new_slide(prs, name, notes=""):
    lay = layout(prs, name)
    s = prs.slides.add_slide(lay)
    for ph in lay.placeholders:                 # bring the slide number across
        if ph.placeholder_format.type == 13:
            s.shapes._spTree.append(copy.deepcopy(ph._element))
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    return s


def ph(s, idx):
    for p in s.placeholders:
        if p.placeholder_format.idx == idx:
            return p
    raise KeyError(idx)


def _run(p, text, size=None, bold=False, italic=False, color=NAVY, font=None):
    r = p.add_run(); r.text = text
    if size: r.font.size = Pt(size)
    r.font.bold = bold; r.font.italic = italic
    r.font.color.rgb = color
    if font: r.font.name = font
    return r


def _bullet(p, level=0, char="•", color=COPPER):
    pPr = p._p.get_or_add_pPr()
    marl = 342900 if level == 0 else 685800
    pPr.set("marL", str(marl)); pPr.set("indent", "-285750")
    for tag in ("a:buNone", "a:buChar", "a:buClr", "a:buSzPct"):
        for e in pPr.findall(qn(tag)):
            pPr.remove(e)
    clr = etree.SubElement(pPr, qn("a:buClr"))
    etree.SubElement(clr, qn("a:srgbClr")).set("val", str(color))
    etree.SubElement(pPr, qn("a:buSzPct")).set("val", "100000")
    etree.SubElement(pPr, qn("a:buChar")).set("char", char)


def _nobullet(p):
    pPr = p._p.get_or_add_pPr()
    pPr.set("marL", "0"); pPr.set("indent", "0")
    if pPr.find(qn("a:buNone")) is None:
        etree.SubElement(pPr, qn("a:buNone"))


def set_text(placeholder, text, size=None, bold=None, color=None):
    tf = placeholder.text_frame
    p = tf.paragraphs[0]
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    lines = text.split("\n")
    for i, line in enumerate(lines):
        pp = p if i == 0 else tf.add_paragraph()
        r = pp.add_run(); r.text = line
        if size: r.font.size = Pt(size)
        if bold is not None: r.font.bold = bold
        if color is not None: r.font.color.rgb = color


def tb(s, x, y, w, h):
    box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    return box, tf


def head(s, title, eyebrow):
    set_text(ph(s, 101), eyebrow.upper())
    set_text(ph(s, 102), title)


# ------------------------------------------------------------ slide builders
def b_title(prs, d):
    s = new_slide(prs, "NLD Title", d["notes"])
    set_text(ph(s, 103), d["title"])
    set_text(ph(s, 104), d["sub"], size=15)
    return s


def b_section(prs, num, title, notes=""):
    s = new_slide(prs, "NLD Section", notes)
    set_text(ph(s, 101), num); set_text(ph(s, 102), title)
    return s


def b_bullets(prs, d, eyebrow, icon=None):
    s = new_slide(prs, "NLD Content", d["notes"])
    head(s, d["title"], eyebrow)
    body = ph(s, 103)
    body.left = Inches(0.67); body.top = Inches(2.15)
    body.width = Inches(12.0); body.height = Inches(4.55)
    if icon:
        body.width = Inches(9.9)
        s.shapes.add_picture(icon, Inches(11.05), Inches(2.2), Inches(1.5), Inches(1.5))
    n = len(d["items"]) + (1 if d.get("sub") else 0)
    nchar = sum(len(t) for _, t in d["items"])
    size = 18 if (n <= 7 and nchar < 650) else 16 if (n <= 10 and nchar < 900) else 15
    tf = body.text_frame
    first = True
    if d.get("sub"):
        p = tf.paragraphs[0]; first = False
        for r in list(p.runs): r._r.getparent().remove(r._r)
        _nobullet(p); p.space_after = Pt(14)
        _run(p, d["sub"], size - 1, italic=True, color=MUTED)
    for lvl, t in d["items"]:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        if first:
            for r in list(p.runs): r._r.getparent().remove(r._r)
        first = False
        if lvl == 0:
            _bullet(p, 0); p.space_after = Pt(8)
            _run(p, t, size)
        else:
            _bullet(p, 1, "–", MUTED); p.space_after = Pt(6); p.space_before = Pt(0)
            _run(p, t, size - 3, color=MUTED)
    return s


def b_figure(prs, d, eyebrow):
    s = new_slide(prs, "NLD Title Only", d["notes"])
    head(s, d["title"], eyebrow)
    blob = d["img"]
    from PIL import Image
    iw, ih = Image.open(io.BytesIO(blob)).size
    ar = iw / ih
    maxw, maxh = 11.6, (4.15 if d.get("caption") else 4.6)
    w = maxw; h = w / ar
    if h > maxh:
        h = maxh; w = h * ar
    x = 0.67 + (12.0 - w) / 2
    s.shapes.add_picture(io.BytesIO(blob), Inches(x), Inches(2.1), Inches(w), Inches(h))
    if d.get("caption"):
        _, tf = tb(s, x, 2.1 + h + 0.12, w, 0.55)
        p = tf.paragraphs[0]
        _run(p, d["caption"], 13, italic=True, color=MUTED)
    return s


def b_table(prs, d, eyebrow, fs=14, hfs=13):
    s = new_slide(prs, "NLD Title Only", d["notes"])
    head(s, d["title"], eyebrow)
    top = 2.1
    if d.get("sub"):
        _, tf = tb(s, 0.67, 2.08, 12.0, 0.4)
        _run(tf.paragraphs[0], d["sub"], 15, italic=True, color=MUTED)
        top = 2.6
    rows = d["rows"]
    nr, nc = len(rows), len(rows[0])
    rh = 0.36 if nr > 9 else 0.4
    gt = s.shapes.add_table(nr, nc, Inches(0.67), Inches(top), Inches(12.0),
                            Inches(rh * nr)).table
    tblPr = gt._tbl.tblPr
    for a in ("bandRow", "firstRow"):
        tblPr.set(a, "0")
    sid = tblPr.find(qn("a:tableStyleId"))
    if sid is not None:
        sid.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"   # "No Style, Table Grid"
    tot = sum(d["widths"])
    for j, wdt in enumerate(d["widths"]):
        gt.columns[j].width = Emu(int(Inches(12.0) * wdt / tot))
    for i, row in enumerate(rows):
        gt.rows[i].height = Inches(rh)
        for j, val in enumerate(row):
            c = gt.cell(i, j); c.text = ""
            c.margin_left = c.margin_right = Inches(0.1)
            c.margin_top = c.margin_bottom = Inches(0.03)
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            p = c.text_frame.paragraphs[0]
            if i == 0:
                _run(p, val, hfs, bold=True, color=PAPER)
                c.fill.solid(); c.fill.fore_color.rgb = NAVY
            else:
                new = val.endswith("(new)")
                _run(p, val, fs, bold=(j == 0), color=COPPER_DEEP if new and j == 0 else NAVY)
                c.fill.solid(); c.fill.fore_color.rgb = WHITE if i % 2 else ROWALT
            _cell_borders(c)
    return s


def _cell_borders(c):
    tcPr = c._tc.get_or_add_tcPr()
    for tag in ("a:lnL", "a:lnR", "a:lnT", "a:lnB"):
        ln = etree.SubElement(tcPr, qn(tag)); ln.set("w", "6350")
        sf = etree.SubElement(ln, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", "DCD9D2")
    # schema order: borders must precede the fill
    fill = tcPr.find(qn("a:solidFill"))
    if fill is not None:
        tcPr.remove(fill); tcPr.append(fill)


def b_pc(prs, d, eyebrow):
    s = new_slide(prs, "NLD Two Column", d["notes"])
    head(s, d["title"], eyebrow)
    _, tf = tb(s, 0.67, 2.08, 12.0, 0.65)
    _run(tf.paragraphs[0], d["idea"], 16, italic=True, color=MUTED)
    nmax = max(len(d["pros"]), len(d["cons"]))
    nch = max(sum(len(t) for t in d["pros"]), sum(len(t) for t in d["cons"]))
    bs = 16 if (nmax <= 4 and nch < 260) else 15 if (nmax <= 4 and nch < 380) else 13
    for idx, hdr, items in [(103, "Strengths", d["pros"]), (104, "Limitations", d["cons"])]:
        b = ph(s, idx)
        b.left = Inches(0.67 if idx == 103 else 6.92); b.top = Inches(2.75 if nmax >= 5 else 2.85)
        b.width = Inches(5.75); b.height = Inches(3.2 if nmax >= 5 else 3.0)
        tfx = b.text_frame
        p = tfx.paragraphs[0]
        for r in list(p.runs): r._r.getparent().remove(r._r)
        _nobullet(p); p.space_after = Pt(8)
        _run(p, hdr.upper(), 12, bold=True, color=COPPER_DEEP)
        for t in items:
            q = tfx.add_paragraph(); _bullet(q, 0); q.space_after = Pt(6)
            _run(q, t, bs)
    vy, vh = (6.08, 0.66) if nmax >= 5 else (5.95, 0.78)
    box = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.67), Inches(vy), Inches(12.0), Inches(vh))
    box.fill.solid(); box.fill.fore_color.rgb = WHITE
    box.line.color.rgb = HAIR; box.line.width = Pt(0.75); box.shadow.inherit = False
    tfb = box.text_frame; tfb.word_wrap = True
    tfb.margin_left = Inches(0.22); tfb.margin_right = Inches(0.22)
    tfb.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tfb.paragraphs[0]; p.alignment = PP_ALIGN.LEFT
    _run(p, "USE IT WHEN   ", 12, bold=True, color=COPPER_DEEP)
    _run(p, d["verdict"], 15)
    return s


def b_closing(prs, notes=""):
    s = new_slide(prs, "NLD Closing", notes)
    set_text(ph(s, 104), "Questions\nweb.uri.edu/nld  ·  chelidze@uri.edu")
    return s


# ------------------------------------------------------------ content edits
FIGS = {4: "s_illposed", 5: "s_naive", 8: "s_edges", 11: "s_tuning", 14: "s_impact",
        17: "s_selftune", 18: "s_uncertainty", 20: "s_integration", 21: "s_fusion"}


def edit(old, figdir):
    o = {i + 1: d for i, d in enumerate(old)}
    # figures regenerated in the NLD palette (make_slide_figs.py) replace the
    # embedded ones when present
    for i, name in FIGS.items():
        f = os.path.join(figdir, name + ".png")
        if os.path.exists(f):
            o[i]["img"] = open(f, "rb").read()
    # impact numbers now come from the reproducible generator in bench_delay.py
    o[13]["pros"] = [p.replace("19.2% vs 22\u201327%", "16.9% vs 21\u201325%") for p in o[13]["pros"]]
    o[1]["title"] = "Differentiating and integrating measured motion"
    o[1]["sub"] = ("Model-free kinematics from one sensor or two\n"
                   "Nonlinear Dynamics Laboratory  ·  University of Rhode Island")
    o[1]["notes"] = (
        "[~0.5 min] TIMING. Full deck: 34 content slides plus title, four section dividers and "
        "closing, about 46 min. The October 2026 additions are slides marked [NEW] in their notes "
        "(about 12 min).\n\n"
        "30-minute path: drop the original optional slides (Savitzky-Golay, tuning-rule table, "
        "uncertainty band, validation checklist), the tuning-curve figure, the self-tuning cost "
        "figure, the integration figure, and the new optional slides (defaults that failed "
        "silently, where delay reconstruction helps). Keep the four delay-reconstruction core "
        "slides and the causal-filter slide.\n\n"
        "Open on the two problems; do not spend time on the title.")
    # prior table: delay row is now implemented; Levant bounds the third derivative
    rows = o[6]["rows"]
    for r in rows:
        if r[0].startswith("It lies in a low-rank"):
            r[1] = "Delay SVD (SSA) / SOD — now in the toolbox"
        if r[0].startswith("Its derivative is bounded"):
            r[0] = "Its third derivative is bounded by a known constant"
    o[6]["notes"] += (" [UPDATED] The delay-embedding row is no longer a pointer to elsewhere: "
                      "section 3 implements it and it wins on quasi-periodic records.")
    # comparison table
    rows = o[22]["rows"]
    rows[:] = [r for r in rows if not r[0].startswith("Levant")]
    rows.append(["Delay SVD / SOD (new)", "low-rank delay space", "0", "good", "no", "no",
                 "free decays, ringdowns"])
    rows.append(["Kalman filter, causal (new)", "integrated Wiener", "0", "n/a", "yes", "yes",
                 "online / control loops"])
    rows.append(["Levant sliding mode", "bounded 3rd deriv.", "1", "n/a", "no", "no",
                 "finite-time exactness"])
    o[22]["sub"] = ("Knobs = free parameters you must choose; three methods now set their own")
    o[22]["notes"] += (" [UPDATED] Two new zero-knob rows: delay reconstruction (dimension from the "
                       "Gavish-Donoho threshold) and the causal Kalman filter, which displaces "
                       "Levant as the online recommendation.")
    # decision list
    it = o[23]["items"]
    it.insert(2, (0, "Quasi-periodic record (free decay, ringdown, steady forced response)  →  "
                     "delay SVD, no knob."))
    it[:] = [x for x in it if not x[1].startswith("Online or in a control loop")]
    it.insert(-1, (0, "Online or in a control loop  →  the causal Kalman filter; Levant only "
                      "when you need finite-time exactness with a known bound."))
    o[23]["notes"] += (" [UPDATED] Two changes: the delay line, and the online line now points to "
                       "the causal Kalman filter, which halves Levant's error on the benchmark.")
    # summary
    it = o[25]["items"]
    it.insert(4, (0, "For a quasi-periodic record: project onto its delay-space subspace first. "
                     "Self-tuned, it beat every oracle-tuned method here."))
    # implementation
    o[26]["title"] = "Implementation"
    o[26]["items"] = [
        (0, "Python and MATLAB implementations of every method here, with matching names."),
        (1, "kin_diff_whittaker, kin_diff_spectral, kin_diff_savgol, kin_diff_tvreg, kin_diff_spline, "
            "kin_diff_gp, kin_diff_levant"),
        (1, "kin_int_tikhonov, kin_int_spectral, kin_int_trapz_detrend"),
        (1, "kin_delay_project, kin_diff_delay, kin_int_delay — delay reconstruction, SVD or SOD"),
        (1, "kin_smooth — differentiation, integration, fusion; causal option for online use"),
        (0, "Cross-validated between the two languages: 38 of 38 checks pass, agreement 1e-16 to 1e-4."),
    ]
    o[26]["notes"] = ("[~0.5 min] Hand off the code. Offer to run any of these on somebody's record "
                      "after the talk. [UPDATED] The MATLAB port is now complete (it previously lacked "
                      "the spline, GP, Levant and trapezoid methods) and the delay-reconstruction "
                      "references are added.")
    o["refs"] = {"kind": "bullets", "title": "References", "sub":
        "Primary sources for each family, not a full bibliography", "items": [
        (0, "Chartrand (2011), Numerical differentiation of noisy, nonsmooth data — ISRN Appl. Math."),
        (0, "Eilers (2003), A perfect smoother — Anal. Chem. 75:3631"),
        (0, "Särkkä & Solin, Applied Stochastic Differential Equations, CUP 2019"),
        (0, "Kim, Koh, Boyd & Gorinevsky (2009), ℓ1 trend filtering — SIAM Review 51(2):339"),
        (0, "Levant (1998), Robust exact differentiation via sliding mode technique — Automatica 34:379"),
        (0, "Broomhead & King (1986), Extracting qualitative dynamics from experimental data — Physica D 20"),
        (0, "Golyandina, Nekrutkin & Zhigljavsky (2001), Analysis of Time Series Structure: SSA — CRC"),
        (0, "Gavish & Donoho (2014), The optimal hard threshold for singular values is 4/√3 — IEEE Trans. Inf. Theory"),
        (0, "Chelidze & Zhou (2006), Smooth orthogonal decomposition-based vibration mode identification — J. Sound Vib."),
        ],
        "notes": "[~0.2 min] Primary sources. The last four support the delay-reconstruction section."}
    return o


def new_content(figdir):
    rd = lambda f: open(os.path.join(figdir, f), "rb").read()
    N = {}
    N["defaults"] = {"title": "Two defaults that failed without a warning", "sub":
        "Found while porting to MATLAB; both are fixed in both languages",
        "items": [
        (0, "scipy's make_smoothing_spline picks λ by GCV. On the 6000-point decay it returned a flat fit: 100% error."),
        (1, "The exact GCV score, with an O(N) trace, has a clear minimum: 1.18% velocity error. The failure was the implementation, not GCV."),
        (0, "Levant's default bound L used the (n+1)-th derivative. The three-state form needs the third derivative bound for both outputs."),
        (1, "L was about 100× too small: 119% error. With max|jerk| from the state-space smoother: 7.7%, at the swept optimum."),
        (0, "Neither raised an error. Each returned a plausible-looking array."),
        (0, "Same lesson as the solver slide: check a default against a case where you know the answer."),
        ],
        "notes": "[NEW] [OPTIONAL] [~1 min] Two more instances of the solver lesson, both found by "
                 "cross-checking the MATLAB port against Python. The GCV case matters because the "
                 "earlier version of this talk blamed GCV itself; the corrected statement is that "
                 "scipy's selection failed on this record while the exact score works."}
    N["causal"] = {"title": "Online, the Kalman filter halves Levant's error", "img": rd("s_causal.png"),
        "caption": "Forward pass of the same state-space model, self-tuned: 5.3% velocity error against "
                   "12.0% for Levant at its best bound. Offline, the RTS smoother reaches 0.83%.",
        "notes": "[NEW] [~1.5 min] The causal filter is the forward half of the smoother we already "
                 "have, so it costs nothing to add. It uses only past samples, so it can run in a "
                 "control loop. Fit q once on a calibration record for genuine online use. Levant "
                 "keeps one advantage: finite-time exactness under a known bound."}
    N["how"] = {"title": "Differentiate in the delay space, not on the raw record",
        "sub": "Prior: the signal lies in a low-dimensional subspace of its delay reconstruction",
        "items": [
        (0, "Embed: rows of a Hankel matrix are delay vectors [xₖ, xₖ₊₁, …, xₖ₊ₗ₋₁], window L = N/3."),
        (0, "Decompose: SVD of that matrix; keep directions above the Gavish–Donoho hard threshold."),
        (0, "Guard: drop any kept direction whose mean frequency lies above the band where the PSD clears the noise floor."),
        (0, "Reconstruct: project, then average along anti-diagonals. Several sensors embed side by side."),
        (0, "Differentiate the reconstruction with a fourth-order stencil. It is band-limited, so the stencil error is negligible."),
        (1, "No knob: L from the record length, dimension from the threshold, guard from the spectrum."),
        ],
        "notes": "[NEW] [~1.5 min] This is singular spectrum analysis used as a differentiator. "
                 "Broomhead and King showed that for short windows the principal axes look like "
                 "Legendre polynomials, so the method reduces to a local polynomial fit; with long "
                 "windows the axes become data-adaptive band-pass filters. The guard matters: at "
                 "long windows one noise direction at 637 Hz passed the threshold and cost 90% in "
                 "acceleration until the guard removed it."}
    N["method"] = {"title": "29 of 2000 delay directions carry the decay",
        "img": rd("s_delay_method.png"),
        "caption": "Left: singular spectrum of the trajectory matrix, 1% position noise. Right: acceleration "
                   "error of the self-tuned delay estimate against Whittaker at its oracle cutoff.",
        "notes": "[NEW] [~1.5 min] Left: the decay occupies a few pairs of directions per harmonic; "
                 "everything below the dashed threshold is noise. The orange crosses passed the "
                 "threshold but sit outside the signal band, so the guard drops them. Right: the "
                 "delay estimate's error is a third of the best-tuned quadratic penalty's."}
    N["bench"] = {"title": "Self-tuned delay SVD beats every oracle-tuned method",
        "img": rd("s_delay_bench.png"),
        "caption": "Duffing free decay, same noise realisations as the main benchmark. Oracle = cutoff swept "
                   "against the exact answer. The delay method sees no truth.",
        "notes": "[NEW] [~1.5 min] At 1% noise: 0.32% velocity and 0.94% acceleration, against 0.52% "
                 "and 1.44% for the spectral method with a perfect cutoff. The reason is the prior, "
                 "not cleverness: a lightly damped decay really is low-rank in delay coordinates. "
                 "The next two slides say where that stops being true."}
    N["pc"] = {"title": "Delay reconstruction (SSA)",
        "idea": "Project onto the signal subspace of the trajectory matrix; differentiate or integrate the reconstruction.",
        "pros": ["No knob: window from record length, dimension from the hard threshold",
                 "Best accuracy of any method tested on decays, by 1.4–1.6× at every noise level",
                 "Several sensors share one subspace (multichannel SSA)",
                 "Full-record accuracy: no FFT-style edge damage"],
        "cons": ["The prior is quasi-periodicity: no gain at impacts (23% vs 17% for TV)",
                 "Cost grows as L²N: about 1 s for N = 6000, L = 2000",
                 "Needs uniform sampling and a gap-free record",
                 "No error bars, and integration still needs a corner"],
        "verdict": "The record is a free decay, a ringdown or a steady forced response.",
        "notes": "[NEW] [~1.5 min] Be clear about the scope: the win comes from a prior that "
                 "lightly damped structures satisfy. On the vibro-impact record it is no better "
                 "than the quadratic penalties, and total variation still wins there."}
    N["sod"] = {"title": "SVD for differentiation, SOD for integration", "img": rd("s_delay_sod.png"),
        "caption": "Left: SOD alone ranks directions by smoothness, so long windows admit smooth noise. "
                   "Right: SOD inside the SVD subspace orders it by frequency and isolates the drift.",
        "notes": "[NEW] [~1.5 min] We compared the two bases. Smooth orthogonal decomposition ranks by "
                 "smoothness and ignores energy; with long windows there are noise directions "
                 "smoother than the signal, and they win (left, purple). Used inside the SVD signal "
                 "subspace instead, SOD reorders that subspace by frequency, which is exactly what "
                 "drift removal needs: 0.51% displacement error against 0.72% with SVD ordering."}
    N["where"] = {"title": "Where delay reconstruction helps, and where it does not",
        "sub": "Velocity / acceleration error, % rms; integration rows give displacement / velocity",
        "rows": [["Record", "Best competitor", "Delay method", "Verdict"],
                 ["Duffing decay, 1% noise", "0.52 / 1.44  spectral, oracle", "0.32 / 0.94  SVD", "helps"],
                 ["3-DOF chain, mass 3", "0.95 / 2.21  Whittaker, oracle", "0.38 / 0.64  SVD", "helps"],
                 ["3-DOF chain, 3 sensors jointly", "0.95 / 2.21  Whittaker, oracle", "0.26 / 0.63  MSSA", "small extra gain"],
                 ["Vibro-impact, near impacts", "17.0  total variation", "23.1  SVD", "does not help"],
                 ["Drifting accelerometer", "0.88 / 2.04  Tikhonov, oracle", "0.51 / 1.34  SOD", "helps"],
                 ["Drifting accelerometer", "0.50 / 0.25  spectral, oracle", "0.51 / 1.34  SOD", "spectral wins here"]],
        "widths": [3.2, 3.3, 2.6, 2.2],
        "notes": "[NEW] [OPTIONAL] [~1 min] The honest map. Joint processing of the three chain sensors "
                 "helps the weaker channels and slightly hurts the strongest one, so it is a small "
                 "extra gain, not a second win. On this narrowband record the oracle spectral "
                 "integrator is still best for velocity; with a mode near the drift band that ranking "
                 "changes."}
    return N


import re as _re
_LP = _re.compile(r"\b(L|\u2113)([12])\b")


def subscript_norms(prs):
    """Typeset L1/L2 (and the l1 of 'l1 trend filtering') as L with a
    subscript digit, splitting runs and keeping their formatting."""
    def fix_run(r):
        t = r.find(qn("a:t"))
        if t is None or not t.text or not _LP.search(t.text):
            return
        parts, last = [], 0
        for m in _LP.finditer(t.text):
            parts += [(t.text[last:m.start()], False), (m.group(1), False), (m.group(2), True)]
            last = m.end()
        parts.append((t.text[last:], False))
        parent = r.getparent(); idx = parent.index(r)
        for k, (txt, sub) in enumerate([q for q in parts if q[0]]):
            nr = copy.deepcopy(r)
            nt = nr.find(qn("a:t")); nt.text = txt
            if txt != txt.strip():
                nt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            if sub:
                rpr = nr.find(qn("a:rPr"))
                if rpr is None:
                    rpr = etree.Element(qn("a:rPr")); nr.insert(0, rpr)
                rpr.set("baseline", "-25000")
            parent.insert(idx + 1 + k, nr)
        parent.remove(r)

    for s in prs.slides:
        for r in list(s._element.iter(qn("a:r"))):
            fix_run(r)


# ------------------------------------------------------------ assemble
def build(old_path, potx, figdir, icon, out):
    old = read_old(old_path)
    o = edit(old, figdir)
    N = new_content(figdir)
    prs = open_template(potx)
    P, M, D, I, R = "The problem", "Differentiation", "Delay reconstruction", "Integration", "In practice"

    def put(d, eb):
        k = d["kind"]
        return {"bullets": b_bullets, "figure": b_figure, "table": b_table, "pc": b_pc}[k](prs, d, eb)

    b_title(prs, o[1])
    for i in range(2, 7):
        put(o[i], P)
    b_section(prs, "01", "Differentiation methods",
              "[~0.2 min] Section divider: one family per prior.")
    for i in range(7, 16):
        put(o[i], M)
    b_bullets(prs, N["defaults"], M)
    for i in range(16, 19):
        put(o[i], M)
    b_figure(prs, N["causal"], M)
    b_section(prs, "02", "Delay reconstruction",
              "[NEW] [~0.2 min] Section divider: the delay-embedding prior, now implemented.")
    b_bullets(prs, N["how"], D, icon=icon)
    b_figure(prs, N["method"], D)
    b_figure(prs, N["bench"], D)
    b_pc(prs, N["pc"], D)
    b_figure(prs, N["sod"], D)
    b_table(prs, dict(N["where"], kind="table"), D, fs=13, hfs=12)
    b_section(prs, "03", "Integration and fusion",
              "[~0.2 min] Section divider: the reverse direction and the two-sensor case.")
    for i in range(19, 22):
        put(o[i], I)
    b_section(prs, "04", "In practice", "[~0.2 min] Section divider: what to do on Monday.")
    b_table(prs, o[22], R, fs=13, hfs=12)
    for i in range(23, 27):
        put(o[i], R)
    b_bullets(prs, o["refs"], R)
    b_closing(prs, "[~0.2 min] Leave this up for questions.")
    subscript_norms(prs)
    prs.save(out)
    print("wrote", out, len(prs.slides._sldIdLst), "slides")


if __name__ == "__main__":
    build(*sys.argv[1:6])
