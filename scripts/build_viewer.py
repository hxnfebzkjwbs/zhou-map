#!/usr/bin/env python3
"""Package the static viewer; the data distribution contains JSON only.

Run: python scripts/build_viewer.py --output dist
No third-party Python packages, network access, or generated JS data are needed.
"""
from __future__ import annotations
import base64
import gzip
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ['index.html', 'web/style.css', 'web/model.js', 'web/app.js']
TABLES = ['counties.json', 'connections.json']


def build(output: Path) -> dict:
    output = output.resolve()
    if output == ROOT or ROOT in output.parents and output.name in {'data', 'web', 'scripts', 'sources'}:
        raise ValueError('Choose a separate output directory, not a source directory.')
    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS + ['data/' + n for n in TABLES]:
        dest = output / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    data = {name.removesuffix('.json'): json.loads((ROOT / 'data' / name).read_text(encoding='utf-8')) for name in TABLES}
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    html = html.replace('<link rel="stylesheet" href="web/style.css?v=0.3">', '<style>' + (ROOT / 'web/style.css').read_text(encoding='utf-8') + '</style>')
    for name in ['model', 'app']:
        html = html.replace(f'<script defer src="web/{name}.js?v=0.3"></script>', '')
    # Escape HTML delimiters in untrusted data so an embedded name cannot close a script.
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    for old, new in [('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'), ('\u2028', '\\u2028'), ('\u2029', '\\u2029')]:
        raw = raw.replace(old, new)
    compressed = base64.b64encode(gzip.compress(raw.encode('utf-8'), compresslevel=6, mtime=0)).decode('ascii')
    scripts = '<script id="zhou-inline-data" type="application/octet-stream" data-compression="gzip">' + compressed + '</script>'
    for name in ['model', 'app']:
        source = (ROOT / f'web/{name}.js').read_text(encoding='utf-8')
        if '</script' in source.lower():
            raise ValueError('Unexpected closing script delimiter in JavaScript source.')
        scripts += '<script>' + source + '</script>'
    html = html.replace('</body>', scripts + '</body>')
    (output / 'zhou-atlas-offline.html').write_text(html, encoding='utf-8')
    if (ROOT / 'NOTICE.md').exists():
        shutil.copyfile(ROOT / 'NOTICE.md', output / 'NOTICE.md')
    (output / '.nojekyll').touch()
    report = {'data_tables': TABLES, 'county_count': len(data['counties']), 'connection_count': len(data['connections']),
              'sha256': {n: hashlib.sha256((output / 'data' / n).read_bytes()).hexdigest() for n in TABLES},
              'note': 'JSON tables copied byte-for-byte. Offline HTML embeds the same parsed values; no Excel or CSV in viewer bundle.'}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT / 'dist')
    build(p.parse_args().output)
