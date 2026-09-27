#!/usr/bin/env python3
"""Checked, idempotent migration of the existing atlas to real source polygons.
This patches presentation/tests only; it never edits a coordinate or invents a county.
"""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
MARKER=ROOT/'sources/real_boundaries/viewer_migration.json'

def patch_file(path,replacements):
 p=ROOT/path;s=p.read_text(encoding='utf-8')
 for a,b in replacements:
  if a not in s:
   if b in s:continue
   raise ValueError(f'Expected baseline text not found in {path}: {a[:70]}')
  s=s.replace(a,b)
 p.write_text(s,encoding='utf-8')

def main():
 if MARKER.exists():
  print('Real-boundary viewer migration already applied.');return
 patch_file('index.html',[
  ('<span class="version">v0.2 <i></i> 游戏模型</span>','<span class="version">v0.3 <i></i> 真实县界</span>'),
  ('<button class="layer active" data-layer="terrain" aria-pressed="true">','<button class="layer active boundary-layer" data-layer="boundary" aria-pressed="true"><span>▱</span>真实行政边界</button><button class="layer" data-layer="terrain" aria-pressed="false">'),
  ('id="mapTitle">东周全域','id="mapTitle">东周游戏范围'),
  ('游戏分区 · 非考证疆界','现代行政边界 · 非770年县界'),
  ('<span>连线仅示意连接，非实际道路或河道</span>','<span class="source-attribution"><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap · ODbL</a> · <a href="https://www.geoboundaries.org/" target="_blank" rel="noopener">geoBoundaries</a> · WFP/OCHA</span>'),
  ('id="countyId">EZ000001','id="countyId">—'),
  ('id="countyName">洛邑','id="countyName">县详情'),
  ('id="layerTitle">地形视图','id="layerTitle">真实县界'),
  ('id="showWater" checked','id="showWater"'),
  ('读取县表与县际距离表…','读取完整县界 JSON，准备原始多边形…'),
  ('href="web/style.css"','href="web/style.css?v=0.3"'),
  ('src="web/model.js"','src="web/model.js?v=0.3"'),
  ('src="web/app.js"','src="web/app.js?v=0.3"')])
 patch_file('web/model.js',[(
  "return !q || [c['县编号'], c['县名'], modern].some(v => v.toLocaleLowerCase().includes(q));",
  "const aliases = (c['资料依据']?.['历史地点'] || []).map(x => x.name);\n        const original = c['资料依据']?.['边界依据']?.['来源名称'] || '';\n        return !q || [c['县编号'], c['县名'], modern, original, ...aliases].some(v => v.toLocaleLowerCase().includes(q));")])
 patch_file('web/app.js',[
  ("const state = { layer: 'terrain'", "const state = { layer: 'boundary'"),
  ("const layerNames = { terrain: '地形视图'", "const layerNames = { boundary: '真实县界', terrain: '游戏地形'"),
  ("function nameType(c) { return evidence(c)['名称类型']?.includes('古名') ? '有据古名' : '现代回退名'; }", "function nameType(c) { return '现代县界 · ' + (c['资料依据']?.['边界依据']?.['边界年代'] || '年份未录'); }"),
  ("if (state.layer === 'terrain') return TERRAIN[c['地形']];", "if (state.layer === 'boundary') return c['资料依据']?.['边界依据']?.['来源层级'] === 'PRK_ADM2' ? '#d2dfdb' : '#dbe4cf';\n    if (state.layer === 'terrain') return TERRAIN[c['地形']];"),
  ("Number(b.id.startsWith('EZ000')) - Number(a.id.startsWith('EZ000'))", "Number(!!b.c['资料依据']?.['历史地点']?.length) - Number(!!a.c['资料依据']?.['历史地点']?.length)"),
  ("anchor = f.id.startsWith('EZ000')", "anchor = !!f.c['资料依据']?.['历史地点']?.length"),
  ("if (state.layer === 'terrain') items = M.TERRAINS.map", "if (state.layer === 'boundary') { items = [['#dbe4cf', '中国县级 · 2017'], ['#d2dfdb', '朝鲜县级 · 2019']]; note = '原始行政边界资料 · 未生成网格 · 非前770年县界'; }\n    if (state.layer === 'terrain') items = M.TERRAINS.map"),
  ('县界、人口、土地及归属沿用游戏模型。现代参考地名不是古代治所的证明。','县界来自注明年份的真实行政资料，未生成网格。人口、土地、地形、归属与道路仍为游戏模型，不能视为前770年实测数据。'),
  ('body.innerHTML = `<div class="metric-duo">','body.innerHTML = `<section class="source-card boundary-card"><h3>边界资料 · ${esc(c[\'资料依据\'][\'边界依据\'][\'边界年代\'])}</h3><p>${esc(c[\'资料依据\'][\'边界依据\'][\'来源名称\'])} · 原始多边形</p><p>保留源轮廓，不裁切、不改成网格。不是前770年县界。</p></section><div class="metric-duo">'),
  ('公元前 770 年 · v0.2-named 数据','游戏开局前770年 · v0.3 真实现代县界资料'),
  ('县界为游戏分区，不是古县界。','县界直接取自 geoBoundaries 整理的真实现代行政区资料：中国部分代表2017年，朝鲜部分代表2019年。未生成六边形、未随机扰动、未裁切县域。它们不是前770年县界，也不是官方勘界认证。'),
  ('海岸与设计外框不应视为已经考定的东周疆域。','保留与旧地图范围相交的完整县域，因此边缘不会再被旧外框切成直线。来源之间存在12对跨境重叠，合计约13.595平方公里，已单独记录；未用虚构边界填平误差。原设计范围与这些现代资料也并不完全重合。'),
  ('县界沿用的 Natural Earth 低分辨率陆地参考为公有领域，具体处理说明保存在仓库 NOTICE.md。','中国边界来自 OpenStreetMap，经 geoBoundaries 整理，适用 ODbL 1.0；朝鲜边界来源为 WFP/OCHA，适用 CC BY 3.0 IGO。边界数据库的署名、许可及来源版本保存在每县资料依据与 NOTICE.md。新县ID不能直接代替旧六边形ID，迁移表只提供空间对应参考。'),
  ('下载包含 GeoNames 派生地名时，应保留来源署名与 CC BY 4.0 许可说明。县内已有逐条溯源网址。','边界派生数据库按 ODbL 1.0 提供；保留 OpenStreetMap / geoBoundaries 署名及 WFP/OCHA、GeoNames 各自来源许可。县内有逐条溯源网址；不是前770年真实县界。'),
  ("fetch('data/' + name + '.json',", "fetch('data/' + name + '.json?v=0.3',"),
  ('controller.abort(), 30000)', 'controller.abort(), 120000)'),
  (" : model.counties[0]['县编号']; state.layer", " : (model.counties.find(c => (c['资料依据']?.['历史地点'] || []).some(x => x.name === '洛邑')) || model.counties[0])['县编号']; state.layer"),
  ("params.get('layer') : 'terrain';", "params.get('layer') : 'boundary';"),
  ("'东周全域'", "'东周游戏范围'"),
  ("if (embedded) data = JSON.parse(embedded.textContent);", """if (embedded) {
        if (embedded.dataset.compression === 'gzip') {
          if (!window.DecompressionStream) throw new Error('离线文件使用无损压缩。请使用支持 DecompressionStream 的现代浏览器，或使用在线版。');
          const binary = atob(embedded.textContent.trim()), bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          embedded.textContent = '';
          const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
          data = JSON.parse(await new Response(stream).text());
        } else data = JSON.parse(embedded.textContent);
      }""")])
 css=ROOT/'web/style.css';s=css.read_text(encoding='utf-8')
 if 'REAL BOUNDARY PROVENANCE' not in s:
  s+='\n/* REAL BOUNDARY PROVENANCE */\n.boundary-layer{grid-column:1/-1}.boundary-card{border-left:3px solid #687e63;margin-top:0;background:#edf2e6}.source-attribution a{color:inherit;text-decoration:underline;text-underline-offset:2px}.map-bottom .source-attribution{font-size:10px;white-space:normal;text-align:right}.county-meta>span{font-size:10px}.version{white-space:nowrap}\n'
 css.write_text(s,encoding='utf-8')
 patch_file('scripts/build_viewer.py',[
  ('import argparse','import base64\nimport gzip\nimport argparse'),
  ('<link rel="stylesheet" href="web/style.css">','<link rel="stylesheet" href="web/style.css?v=0.3">'),
  ('<script defer src="web/{name}.js"></script>','<script defer src="web/{name}.js?v=0.3"></script>'),
  ("scripts = '<script id=\"zhou-inline-data\" type=\"application/json\">' + raw + '</script>'", "compressed = base64.b64encode(gzip.compress(raw.encode('utf-8'), compresslevel=6, mtime=0)).decode('ascii')\n    scripts = '<script id=\"zhou-inline-data\" type=\"application/octet-stream\" data-compression=\"gzip\">' + compressed + '</script>'")])
 patch_file('tests/web-model.test.cjs',[("model.search('洛阳').some(c => c['县名'] === '洛邑')", "model.search('洛邑').some(c => (c['资料依据']['历史地点'] || []).some(x => x.name === '洛邑'))")])
 # Explicitly migrate UI assertions to source IDs rather than preserving fictitious grid IDs.
 patch_file('tests/web_ui_test.py',[
  ('timeout=30000','timeout=120000'),
  ("'args': ['--no-sandbox']", "'args': ['--no-sandbox', '--disable-dev-shm-usage']"),
  ("check('Loads 1195 source counties', page.locator('#statCount').inner_text() == '1,195')", "check('Loads source-backed counties', page.locator('#statCount').inner_text() == format(len(COUNTIES), ','))"),
  ("check('Loads 3413 source county pairs', page.locator('#statEdges').inner_text() == '3,413')", "check('Loads rebuilt county pairs', page.locator('#statEdges').inner_text() == format(len(EDGES), ','))"),
  ("check('Default selects Luoyi', page.locator('#countyName').inner_text() == '洛邑')", "check('Default selects the real county containing the Luoyi anchor', page.locator('#countyName').inner_text() == '西工区')"),
  ("page.locator('#search').fill('洛阳')", "page.locator('#search').fill('洛邑')"),
  ("check('Modern alias finds Luoyi', page.locator('#countyList').inner_text().find('洛邑') >= 0)", "check('Historical place alias resolves to a real modern county', page.locator('#countyList').inner_text().find('西工区') >= 0)"),
  ("check('Country filter matches data', page.locator('#matchCount').inner_text() == '8')", "check('Country filter matches the data', int(page.locator('#matchCount').inner_text().replace(',', '')) == sum(c['开局行政归属']['所属国家'] == '周' for c in COUNTIES))"),
  ("['country', 'population', 'resource', 'terrain']", "['country', 'population', 'resource', 'terrain', 'boundary']"),
  ('EZ000001','RCHN-8f5c29b1867a'),('EZ000005','RCHN-e8c96c155de6'),('EZ000006','RCHN-a519c47e0d35'),
  ("== '临淄'", "== '临淄区'"),("== '曲阜'", "== '曲阜市'"),
  ("'不是古县界' in page.locator('#modalBody').inner_text()", "'不是前770年县界' in page.locator('#modalBody').inner_text()"),
  ("page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)", "page.screenshot(path=str(OUT / 'desktop.png'), full_page=True)\n    page.locator('#focusSelected').click(); page.locator('#zoomOut').click(); page.locator('#zoomOut').click()\n    page.screenshot(path=str(OUT / 'detail-boundaries.png'), full_page=True); page.locator('#fitMap').click()\n    check('Visible boundary epoch and provenance', '2017' in page.locator('#nameBadge').inner_text() and '不是前770年县界' in page.locator('#detailBody').inner_text())")])
 legacy=ROOT/'scripts/build_map.py';s=legacy.read_text(encoding='utf-8');marker="if __name__=='__main__':"
 if 'Legacy grid build retired' not in s:
  a=s.index(marker);s=s[:a]+marker+"\n    # Legacy grid build retired; shared numerical helpers remain importable.\n    from rebuild_real_boundaries import build\n    build()\n";legacy.write_text(s,encoding='utf-8')
 patch_file('scripts/validate.py',[("if __name__=='__main__':\n    try:", "if __name__=='__main__':\n    if read('data/manifest.json').get('version')=='v0.3-real-boundaries':\n        from validate_real_boundaries import main\n        main();sys.exit(0)\n    try:")])
 paths=['index.html','web/app.js','web/model.js','web/style.css','scripts/build_viewer.py','scripts/build_map.py','scripts/validate.py','tests/web_ui_test.py','tests/web-model.test.cjs']
 MARKER.parent.mkdir(parents=True,exist_ok=True)
 MARKER.write_text(json.dumps({'version':'v0.3','output_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')
 (ROOT/'.nojekyll').touch()
 print('Updated existing viewer and retired hex-grid CLI without changing source polygons.')

if __name__=='__main__':main()
