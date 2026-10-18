"""Typeset slide text blocks with XeLaTeX (IBM Plex Sans text, Latin Modern Math) to SVG.

1 SVG unit = 1 slide px: font size S px -> \\fontsize{S}{...} in pt, text width W px -> W pt.
"""
import os, re, subprocess, tempfile, shutil

PRE = r"""\documentclass[border=0pt]{standalone}
\usepackage{fontspec,unicode-math,xcolor,enumitem,array,colortbl}
\setmainfont{IBMPlexSans-Regular.ttf}[Path=/root/.fonts/,BoldFont=IBMPlexSans-SemiBold.ttf,ItalicFont=IBMPlexSans-Italic.ttf,BoldItalicFont=IBMPlexSans-SemiBoldItalic.ttf]
\setmathfont{Latin Modern Math}
\definecolor{ink}{HTML}{132433}\definecolor{copper}{HTML}{B4622A}\definecolor{cdeep}{HTML}{9A5323}
\definecolor{muted}{HTML}{5B6168}\definecolor{hair}{HTML}{DCD9D2}\definecolor{stone}{HTML}{D9D3C7}
\definecolor{slatebg}{HTML}{E7ECEF}\definecolor{sage}{HTML}{588A75}
\newcommand{\bigO}{\mathcal{O}}
\setlist[itemize]{leftmargin=1.05em,label={\color{copper}\textbullet},itemsep=%(isep)s,topsep=0pt,parsep=0pt,partopsep=0pt}
\begin{document}\fontsize{%(s)s}{%(b)s}\selectfont\color{%(c)s}%%
\begin{minipage}{%(w)spt}\raggedright %(body)s\end{minipage}\end{document}
"""


def render(out_svg, body, width, size, lh=1.38, color='ink', isep=None):
    isep = isep or f'{0.36*size:.1f}pt'
    tex = PRE % dict(s=size, b=f'{size*lh:.2f}', c=color, w=width, body=body, isep=isep)
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'b.tex'), 'w').write(tex)
    r = subprocess.run(['xelatex', '-interaction=nonstopmode', '-halt-on-error', 'b.tex'], cwd=d, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(out_svg + '\n' + r.stdout[-1500:])
    subprocess.run(['pdftocairo', '-svg', os.path.join(d, 'b.pdf'), out_svg], check=True)
    if os.environ.get('PREVIEW'):
        subprocess.run(['pdftocairo', '-png', '-r', '72', '-singlefile', os.path.join(d, 'b.pdf'), os.path.join(os.environ['PREVIEW'], os.path.basename(out_svg)[:-4])], check=True)
    shutil.rmtree(d)
    vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', open(out_svg).read())
    return float(vb.group(1)), float(vb.group(2))


def items(lines):
    return r'\begin{itemize}' + ''.join(r'\item ' + l + '\n' for l in lines) + r'\end{itemize}'


def table(widths, aligns, header, rows, width, size, shade=None, pad=0.45, stretch=1.55):
    """widths: fractions; aligns: 'l'|'c'. Returns LaTeX body."""
    tc = pad*size
    cols = []
    for f, a in zip(widths, aligns):
        w = f*width - 2*tc - 0.8
        al = r'\raggedright' if a == 'l' else r'\centering'
        cols.append(r'>{%s\arraybackslash}p{%.1fpt}' % (al, w))
    spec = '!{\\color{hair}\\vrule}' + ''.join(cols) + '!{\\color{hair}\\vrule}'
    hdr = r'\rowcolor{stone}' + ' & '.join(r'\textbf{%s}' % h for h in header) + r'\\\arrayrulecolor{hair}\hline' + '\n'
    body = ''
    for i, r in enumerate(rows):
        pre = r'\rowcolor{slatebg}' if shade is not None and i == shade else ''
        body += pre + ' & '.join(r) + r'\\\hline' + '\n'
    return (r'\setlength{\tabcolsep}{%.1fpt}\renewcommand{\arraystretch}{%.2f}\arrayrulecolor{hair}'
            r'\begin{tabular}{%s}\hline ' % (tc, stretch, spec) + hdr + body + r'\end{tabular}')
