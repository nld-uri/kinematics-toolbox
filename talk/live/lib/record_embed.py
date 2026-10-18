"""Record a browser-native embed page to H.264 MP4 (one full cycle, 30 fps).

    python record_embed.py <embed.html> <period_s> <out.mp4> [width height]
"""
import sys, os, asyncio, subprocess, tempfile
from playwright.async_api import async_playwright

FF = ['-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-profile:v', 'main', '-level:v', '4.0', '-crf', '18', '-g', '30',
      '-tag:v', 'avc1', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-brand', 'mp42',
      '-movflags', '+faststart']


async def main(page_path, T, out, W=1600, H=700, fps=30):
    tmp = tempfile.mkdtemp()
    n = int(round(T*fps))
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        for k in range(n):
            await pg.goto('about:blank')
            await pg.goto('file://' + os.path.abspath(page_path) + f'#p={k/n:.5f}')
            await pg.wait_for_timeout(30)
            await pg.screenshot(path=os.path.join(tmp, f'{k:05d}.png'))
        await b.close()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-i', os.path.join(tmp, '%05d.png'),
                    '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2'] + FF + [out], check=True)
    print(out, n, 'frames')


if __name__ == '__main__':
    a = sys.argv[1:]
    asyncio.run(main(a[0], float(a[1]), a[2], *(int(x) for x in a[3:])))
