"""Helpers to pack data and build <x-embed> pages (<= 16 KB each)."""
import os, base64, subprocess, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = open(os.path.join(HERE, 'plot.js')).read()
LIMIT = 16000


def e16(x, scale, off=0.0):
    """int16 base64; decode in JS with b64(s, scale, off)."""
    q = np.clip(np.round((np.asarray(x, float) - off)/scale), -32767, 32767).astype('<i2')
    return base64.b64encode(q.tobytes()).decode()


def e8mu(x, amp):
    """mu-law int8 of x/amp (|x| <= amp); decode with mu(b64(s,1,0,8), amp)."""
    y = np.clip(np.asarray(x, float)/amp, -1, 1)
    c = np.sign(y)*np.log1p(255*np.abs(y))/np.log(256)
    q = np.round(127*c).astype('i1')
    return base64.b64encode(q.tobytes()).decode()


def js(v):
    return json.dumps(v, separators=(',', ':'))


def build(name, code, outdir):
    src = LIB + '\n' + code
    tmp = os.path.join(outdir, '_' + name + '.js')
    open(tmp, 'w').write(src)
    mini = subprocess.run(['npx', 'terser', tmp, '-c', '-m', '--toplevel'], capture_output=True, text=True,
                          cwd=os.path.dirname(HERE))
    if mini.returncode:
        raise RuntimeError(mini.stderr)
    os.remove(tmp)
    html = '<!doctype html><html><head><meta charset="utf-8"></head><body><script>' + mini.stdout.strip() + '</script></body></html>'
    path = os.path.join(outdir, name + '.html')
    open(path, 'w').write(html)
    n = len(html.encode())
    print(f'{name}: {n} bytes' + ('  OVER LIMIT' if n > LIMIT else ''))
    return path
