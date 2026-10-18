# Live slides and browser-native animations

The current talk is an HTML slide deck with live animations:
[Differentiating and integrating measured motion](https://claude.ai/artifact/6q12emHxX6Jy6DTFMuwNYC)
(54 slides, NLD slide rules of October 2026: body text 36–44 px, tables 32 px, symbols typeset in LaTeX).
A vector export of the same deck is `../differentiation_integration_talk.pdf`; animations appear there as
one frame each. `../differentiation_integration_talk.pptx` is the PowerPoint version of the same deck: slide images, the
animations as MP4 movies, and the speaker notes.

`embeds/*.html` are the five animations as standalone pages. Open one in a browser to watch it.
Append `#p=0.4` to the URL to freeze it at 40 % of its cycle.

| File | Shows |
|---|---|
| `illposed.html` | noise gain ωⁿ as the order sweeps from two integrals to two derivatives |
| `knob.html` | Whittaker acceleration as the cutoff sweeps, with the U-shaped error curve |
| `edges.html` | the FFT's periodic extension and the error it causes at the record ends |
| `impact.html` | velocity at an impact: spectral, Whittaker and total variation |
| `fusion.html` | forward Kalman filter, then backward RTS smoother, fusing two sensors |

Rebuild: `python make_embeds.py` (needs `../../python`, numpy, scipy, and `npx terser`). Every page stays
under 16 KB. `lib/plot.js` is the canvas plotting kit; `lib/latexblock.py` typesets slide text blocks
with XeLaTeX (IBM Plex Sans, Latin Modern Math); `latex_spec.py` holds the typeset blocks used in the
deck; `lib/export_pdf.py` renders a deck to PDF.
`lib/record_embed.py` records an embed to MP4; `lib/export_pptx.py` builds the PowerPoint file from the
deck PDF, the MP4s and the speaker notes.
