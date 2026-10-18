"""Render a Slides-type deck (project/deck.json + project/slides/*.html) to a vector PDF with Chromium.

    python export_pdf.py <deck_dir> <blobmap.json> <out.pdf> [wait_ms]

blobmap maps blob ids to local files. <x-embed> pages run in an iframe; the PDF keeps the frame
reached after wait_ms (default 4000 ms). Text and SVG stay vector.
"""
import sys, os, re, json, html, asyncio, tempfile
from playwright.async_api import async_playwright
from pypdf import PdfWriter, PdfReader

CSS = ('*{margin:0;box-sizing:border-box}html,body{width:1920px;height:1080px;overflow:hidden}'
       'section{width:1920px;height:1080px;position:relative;overflow:hidden}ul,ol{padding-left:1.15em}'
       '@page{size:1920px 1080px;margin:0}')


def page_html(sec, bmap):
    sec = re.sub(r'<aside>.*?</aside>', '', sec, flags=re.S)
    sec = re.sub(r'/_blob/([0-9a-f]{32})', lambda m: 'file://' + bmap[m.group(1)], sec)
    def emb(m):
        return f'<iframe style="{m.group(1)};border:0" srcdoc="{html.escape(m.group(2), quote=True)}"></iframe>'
    sec = re.sub(r'<x-embed style="([^"]*)">(.*?)</x-embed>', emb, sec, flags=re.S)
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>{sec}</body></html>'


async def main(deck, bmap, out, wait):
    order = json.load(open(os.path.join(deck, 'project/deck.json')))['order']
    tmp = tempfile.mkdtemp()
    parts = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1920, 'height': 1080})
        for i, sid in enumerate(order):
            sec = open(os.path.join(deck, 'project/slides', sid + '.html')).read()
            f = os.path.join(tmp, f'{i:03d}.html'); open(f, 'w').write(page_html(sec, bmap))
            await pg.goto('file://' + f)
            await pg.wait_for_timeout(wait if 'x-embed' in sec else 400)
            pdf = os.path.join(tmp, f'{i:03d}.pdf')
            await pg.pdf(path=pdf, width='1920px', height='1080px', print_background=True, page_ranges='1')
            parts.append(pdf)
        await b.close()
    w = PdfWriter()
    for f in parts:
        w.append(PdfReader(f))
    w.write(out)
    print(out, len(parts), 'pages')


if __name__ == '__main__':
    a = sys.argv[1:]
    asyncio.run(main(a[0], json.load(open(a[1])), a[2], int(a[3]) if len(a) > 3 else 4000))
