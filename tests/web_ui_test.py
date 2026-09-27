#!/usr/bin/env python3
"""Exercise the real Chromium DOM and Canvas using the self-contained HTML.

python -m pip install playwright
python -m playwright install chromium
python scripts/build_viewer.py
python tests/web_ui_test.py

set_content deliberately avoids browser access to localhost/file URLs: every byte
(including both JSON tables) is the exact offline release document. No mock map,
mock route calculation, or remote service is used.
"""
from __future__ import annotations
import heapq
import json
import math
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get('WEB_TEST_OUTPUT', ROOT / 'test-results'))
OUT.mkdir(parents=True, exist_ok=True)
HTML = (ROOT / 'dist/zhou-atlas-offline.html').read_text(encoding='utf-8')
COUNTIES = json.loads((ROOT / 'data/counties.json').read_text(encoding='utf-8'))
EDGES = json.loads((ROOT / 'data/connections.json').read_text(encoding='utf-8'))
CHECKS = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    CHECKS.append(name)


def expected_distance(source, target, mode):
    """Independent Python shortest-path oracle using raw table distances."""
    adj = {c['县编号']: [] for c in COUNTIES}
    for e in EDGES:
        a, b = e['县 A 编号'], e['县 B 编号']
        if mode == 'water':
            for u, v, k in [(a, b, '水路 A→B 距离'), (b, a, '水路 B→A 距离')]:
                if e[k] is not None: adj[u].append((v, e[k]))
        elif e['陆路距离'] is not None and (mode == 'land' or e['陆路通行类型'] == '能走车'):
            adj[a].append((b, e['陆路距离'])); adj[b].append((a, e['陆路距离']))
    dist = {source: 0}; queue = [(0, source)]
    while queue:
        d, u = heapq.heappop(queue)
        if d != dist[u]: continue
        if u == target: return d
        for v, w in adj[u]:
            if d + w < dist.get(v, math.inf):
                dist[v] = d + w; heapq.heappush(queue, (d + w, v))
    return None


def load(page):
    page.set_content(HTML, wait_until='load', timeout=120000)
    page.wait_for_function("document.body.dataset.ready === 'true'", timeout=120000)
    page.wait_for_timeout(100)


with sync_playwright() as p:
    executable = os.environ.get('CHROMIUM_EXECUTABLE') or shutil.which('chromium')
    args = {'headless': True, 'args': ['--no-sandbox', '--disable-dev-shm-usage']}
    if executable: args['executable_path'] = executable
    browser = p.chromium.launch(**args)
    page = browser.new_page(viewport={'width': 1512, 'height': 982}, device_scale_factor=1)
    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
    load(page)
    check('Loads source-backed counties', page.locator('#statCount').inner_text() == format(len(COUNTIES), ','))
    check('Loads rebuilt county pairs', page.locator('#statEdges').inner_text() == format(len(EDGES), ','))
    check('Default selects the real county containing the Luoyi anchor', page.locator('#countyName').inner_text() == '西工区')
    check('No desktop horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    check('All seven land use categories displayed', page.locator('.land-row').count() == 7)
    page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)
    page.locator('#focusSelected').click(); page.locator('#zoomOut').click(); page.locator('#zoomOut').click()
    page.screenshot(path=str(OUT / 'detail-boundaries.png'), full_page=True); page.locator('#fitMap').click()
    check('Visible boundary epoch and provenance', '2017' in page.locator('#nameBadge').inner_text() and '不是前770年县界' in page.locator('#detailBody').inner_text())
    page.locator('#search').fill('洛邑')
    check('Historical place alias resolves to a real modern county', page.locator('#countyList').inner_text().find('西工区') >= 0)
    page.locator('#resetFilters').click()
    page.locator('#countryFilter').select_option('周')
    check('Country filter matches the data', int(page.locator('#matchCount').inner_text().replace(',', '')) == sum(c['开局行政归属']['所属国家'] == '周' for c in COUNTIES))
    page.locator('#resetFilters').click()
    page.locator('#resourceFilter').select_option('铜矿')
    check('Resource filter uses source records', int(page.locator('#matchCount').inner_text().replace(',', '')) == sum('铜矿' in c['自然资源'] for c in COUNTIES))
    page.locator('#resetFilters').click()
    page.locator('#search').fill('DOES_NOT_EXIST')
    check('No-result state is visible', '没有匹配的分区' in page.locator('#countyList').inner_text())
    page.locator('#resetFilters').click()
    for layer in ['country', 'population', 'resource', 'terrain', 'boundary']:
        page.locator(f'[data-layer={layer}]').click()
        check(f'Layer {layer} updates canvas state', page.evaluate('ZhouAtlas.state.layer') == layer)
    k = page.evaluate('ZhouAtlas.state.transform.k')
    page.locator('#zoomIn').click()
    check('Zoom changes projection scale', page.evaluate('ZhouAtlas.state.transform.k') > k)
    page.locator('#fitMap').click()
    b = page.locator('#map').bounding_box()
    page.mouse.move(b['x'] + 200, b['y'] + 250)
    oldx = page.evaluate('ZhouAtlas.state.transform.x')
    page.mouse.down(); page.mouse.move(b['x'] + 260, b['y'] + 280, steps=8); page.mouse.up()
    check('Drag pans the actual map', page.evaluate('ZhouAtlas.state.transform.x') > oldx + 40)
    page.locator('#fitMap').click()
    xy = page.evaluate("ZhouAtlas.projectToScreen('RCHN-e8c96c155de6')")
    page.mouse.click(b['x'] + xy[0], b['y'] + xy[1])
    check('Canvas polygon hit testing selects Linzi', page.locator('#countyName').inner_text() == '临淄区')
    page.locator('[data-detail=connections]').click()
    check('Connection inspector lists neighbors', page.locator('.connection-card').count() > 0)
    check('Null directions displayed as no channel', '无通道' in page.locator('#detailBody').inner_text())
    page.locator('[data-detail=sources]').click()
    check('Provenance URLs are clickable and protected', page.locator('#detailBody a[rel="noopener noreferrer"]').count() > 0)
    page.locator('#viewCountyJSON').click()
    raw = json.loads(page.locator('#jsonView').inner_text())
    check('Raw county JSON retains complete geometry', raw['县编号'] == 'RCHN-e8c96c155de6' and raw['县界']['type'] in ('Polygon', 'MultiPolygon'))
    page.locator('#closeModal').click()
    page.locator('#navRoute').click()
    for mode in ['land', 'cart']:
        page.locator('#routeFrom').fill('RCHN-8f5c29b1867a'); page.locator('#routeTo').fill('RCHN-e8c96c155de6'); page.locator('#routeMode').select_option(mode)
        page.locator('#calculateRoute').click()
        actual = page.evaluate('ZhouAtlas.state.route?.distance ?? null')
        expected = expected_distance('RCHN-8f5c29b1867a', 'RCHN-e8c96c155de6', mode)
        check(f'{mode} route equals independent Python oracle', actual is not None and abs(actual - expected) < 1e-8)
    page.screenshot(path=str(OUT / 'route.png'), full_page=True)
    water = next(e for e in EDGES if e['水路 A→B 距离'] is not None)
    for a, b_ in [(water['县 A 编号'], water['县 B 编号']), (water['县 B 编号'], water['县 A 编号'])]:
        page.locator('#routeFrom').fill(a); page.locator('#routeTo').fill(b_); page.locator('#routeMode').select_option('water'); page.locator('#calculateRoute').click()
        expected = expected_distance(a, b_, 'water'); actual = page.evaluate('ZhouAtlas.state.route?.distance ?? null')
        check('Water route direction checked against Python oracle '+a, expected is not None and abs(expected - actual) < 1e-8)
    no_source = next(c['县编号'] for c in COUNTIES if not any((e['县 A 编号'] == c['县编号'] and e['水路 A→B 距离'] is not None) or (e['县 B 编号'] == c['县编号'] and e['水路 B→A 距离'] is not None) for e in EDGES))
    target = next(c['县编号'] for c in COUNTIES if c['县编号'] != no_source)
    page.locator('#routeFrom').fill(no_source); page.locator('#routeTo').fill(target); page.locator('#calculateRoute').click()
    check('Disconnected water route does not invent connections', '没有可达' in page.locator('#routeResult').inner_text() and page.evaluate('ZhouAtlas.state.route') is None)
    page.locator('#routeFrom').fill('BAD-ID'); page.locator('#calculateRoute').click()
    check('Invalid route input reports a clear error', '请选择有效' in page.locator('#routeResult').inner_text())
    page.locator('#openExport').click()
    with page.expect_download() as dl:
        page.locator('[data-download=connections]').click()
    downloaded = json.loads(Path(dl.value.path()).read_text())
    check('JSON download preserves every connection and null', downloaded == EDGES)
    page.locator('#closeModal').click()
    page.locator('#navAbout').click()
    check('About dialog labels the historical limits', '不是前770年县界' in page.locator('#modalBody').inner_text())
    page.keyboard.press('Escape')
    check('Escape closes the accessible dialog', not page.locator('#modal').is_visible())
    check('No desktop JS exceptions', not errors)
    mobile = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    mp = mobile.new_page(); mobile_errors=[]; mp.on('pageerror', lambda e: mobile_errors.append(str(e))); load(mp)
    check('No mobile horizontal overflow', mp.evaluate('document.documentElement.scrollWidth <= innerWidth'))
    check('Closed drawers are not keyboard-focusable', mp.locator('#sidebar').evaluate('(e)=>e.inert') and mp.locator('#inspector').evaluate('(e)=>e.inert'))
    mp.screenshot(path=str(OUT / 'mobile.png'), full_page=True)
    mp.locator('#mobileDetails').tap(); check('Mobile county drawer opens', mp.locator('#inspector').evaluate("e=>e.classList.contains('open') && !e.inert"))
    mp.locator('[data-detail=connections]').tap(); check('Mobile connections remain usable', mp.locator('.connection-card').count() > 0)
    mp.screenshot(path=str(OUT / 'mobile-detail.png'), full_page=True)
    mp.locator('[data-close=inspector]').tap()
    mp.locator('#mobileFilters').tap(); mp.locator('#search').fill('曲阜'); mp.locator('#countyList [data-select=RCHN-a519c47e0d35]').tap()
    check('Mobile search selects county and opens details', mp.locator('#countyName').inner_text() == '曲阜市' and mp.locator('#inspector').evaluate("e=>e.classList.contains('open')"))
    mp.locator('#setStart').tap(); check('Mobile route tool accessible from detail action', mp.locator('#routePanel').is_visible() and '曲阜' in mp.locator('#routeFrom').input_value())
    check('No mobile JS exceptions', not mobile_errors)
    browser.close()

report = {'status': 'PASS', 'checks_passed': len(CHECKS), 'checks': CHECKS,
          'browser': 'Chromium', 'loading_method': 'exact offline release HTML via set_content; localhost and file navigation restricted in authoring browser',
          'viewport_sizes': ['1512x982', '390x844'], 'routing_oracle': 'independent Python Dijkstra over original JSON',
          'exceptions': errors + mobile_errors}
(OUT / 'web_ui_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
