/* East Zhou atlas: a static, dependency-free viewer of the two canonical JSON tables. */
(function () {
  'use strict';
  const M = window.ZhouModel, $ = id => document.getElementById(id);
  const nf = new Intl.NumberFormat('zh-CN'), fmt = (n, digits = 0) => new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
  const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
  const TERRAIN = { '平原': '#dce0bf', '河谷': '#b3cac0', '丘陵': '#c3cea9', '山地': '#98b09a', '湿地': '#aecdd0' };
  const TERRAIN_MARK = { '平原': '―', '河谷': '≈', '丘陵': '⌁', '山地': '△', '湿地': '≋' };
  const LAND_COLORS = ['#acb782', '#d6c59d', '#c6d3a4', '#96b69b', '#577b62', '#9e9b8a', '#d0d8c4'];
  const COUNTRY_COLORS = ['#e1c698', '#95b9b9', '#c3b59a', '#a5b396', '#cbaaa0', '#adc4d0', '#c6c5a2', '#b3b4cb', '#8fac99', '#d5c197', '#b1c0a0', '#acc2bb'];
  const POP_COLORS = ['#e1e5cd', '#c3d7c2', '#8dbab0', '#5f9d9e', '#356f81'];
  const state = { layer: 'terrain', selected: null, hovered: null, detail: 'overview', route: null, routeView: false, matches: [], matched: new Set(), listLimit: 60, transform: { k: .2, x: 0, y: 0 }, initialK: .2, drawing: false, width: 0, height: 0, dpr: 1 };
  let model, features = [], byFeature = new Map(), countryColors = new Map(), selectedEdges = [], allBounds;
  const canvas = $('map'), ctx = canvas.getContext('2d'), hitCtx = document.createElement('canvas').getContext('2d');
  const modeNames = { land: '陆路', cart: '车行', water: '水路' };
  const layerNames = { terrain: '地形视图', country: '开局国家', population: '人口密度', resource: '资源分布' };
  let toastTimer;
  function toast(text) { $('toast').textContent = text; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => { $('toast').hidden = true; }, 3200); }
  function safeUrl(value) { try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : null; } catch { return null; } }
  function coords(c) { return c['治所坐标'].map(v => fmt(v, 4)).join('° E / ') + '° N'; }
  function displayName(c) { return c['县名'] + ' · ' + c['县编号']; }
  function selectedCounty() { return model?.byId.get(state.selected); }
  function evidence(c) { return c['资料依据']?.['地名考证'] || {}; }
  function nameType(c) { return evidence(c)['名称类型']?.includes('古名') ? '有据古名' : '现代回退名'; }
  function ownerName(c) { return c['开局行政归属']['所属国家'] ?? '未分配'; }
  function density(c) { return c['初始人口'] / (c['总面积'] / 100); }
  function popBin(c) { const d = density(c); return d < 1 ? 0 : d < 3 ? 1 : d < 6 ? 2 : d < 10 ? 3 : 4; }
  function resourceCategory(c) { const r = c['自然资源']; return r.some(x => !['石料', '陶土'].includes(x)) ? 3 : r.includes('陶土') ? 2 : r.includes('石料') ? 1 : 0; }
  function fill(c) {
    if (state.layer === 'terrain') return TERRAIN[c['地形']];
    if (state.layer === 'country') return countryColors.get(c['开局行政归属']['所属国家']) || '#d5dccb';
    if (state.layer === 'population') return POP_COLORS[popBin(c)];
    return ['#dbe2d2', '#a9baa8', '#c5bb91', '#ab985e'][resourceCategory(c)];
  }
  function prepareGeometry() {
    features = model.counties.map(c => {
      const path = new Path2D(), bbox = [Infinity, Infinity, -Infinity, -Infinity];
      const polygons = c['县界'].type === 'Polygon' ? [c['县界'].coordinates] : c['县界'].coordinates;
      for (const polygon of polygons) for (const ring of polygon) {
        ring.forEach((coord, i) => { const p = M.project(coord); bbox[0] = Math.min(bbox[0], p[0]); bbox[1] = Math.min(bbox[1], p[1]); bbox[2] = Math.max(bbox[2], p[0]); bbox[3] = Math.max(bbox[3], p[1]); if (!i) path.moveTo(...p); else path.lineTo(...p); }); path.closePath();
      }
      return { c, path, bbox, point: M.project(c['治所坐标']), id: c['县编号'] };
    });
    byFeature = new Map(features.map(f => [f.id, f]));
    allBounds = features.reduce((a, f) => [Math.min(a[0], f.bbox[0]), Math.min(a[1], f.bbox[1]), Math.max(a[2], f.bbox[2]), Math.max(a[3], f.bbox[3])], [Infinity, Infinity, -Infinity, -Infinity]);
  }
  function screen(p) { const t = state.transform; return [p[0] * t.k + t.x, p[1] * t.k + t.y]; }
  function world(p) { const t = state.transform; return [(p[0] - t.x) / t.k, (p[1] - t.y) / t.k]; }
  function drawSoon() { if (!state.drawing) { state.drawing = true; requestAnimationFrame(() => { state.drawing = false; draw(); }); } }
  function fitBounds(bounds, full = false) {
    if (!bounds || !state.width) return;
    const top = state.width < 500 ? 174 : 180, bottom = state.width < 500 ? 178 : 144;
    const availableH = Math.max(120, state.height - top - bottom), availableW = Math.max(140, state.width - 86);
    const k = Math.min(availableW / (bounds[2] - bounds[0]), availableH / (bounds[3] - bounds[1]));
    state.transform = { k, x: state.width / 2 - k * (bounds[0] + bounds[2]) / 2, y: top + availableH / 2 - k * (bounds[1] + bounds[3]) / 2 };
    if (full) state.initialK = k;
    drawSoon();
  }
  function focus(id) {
    const f = byFeature.get(id); if (!f) return;
    const k = state.initialK * 6.5, p = f.point;
    state.transform = { k, x: state.width * .48 - p[0] * k, y: state.height * .49 - p[1] * k }; drawSoon();
  }
  function zoom(factor, pivot = [state.width / 2, state.height / 2]) {
    const p = world(pivot), k = Math.max(state.initialK * .55, Math.min(state.initialK * 35, state.transform.k * factor));
    state.transform = { k, x: pivot[0] - p[0] * k, y: pivot[1] - p[1] * k }; drawSoon();
  }
  function visible(f) { const a = screen([f.bbox[0], f.bbox[1]]), b = screen([f.bbox[2], f.bbox[3]]); return b[0] > -30 && a[0] < state.width + 30 && b[1] > -30 && a[1] < state.height + 30; }
  function graticule() {
    const k = state.transform.k; ctx.strokeStyle = '#879e7b1b'; ctx.lineWidth = .65 / k; ctx.setLineDash([2 / k, 5 / k]);
    for (let lon = 90; lon <= 135; lon += 5) { const a = M.project([lon, 18]), b = M.project([lon, 50]); ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke(); }
    for (let lat = 20; lat <= 50; lat += 5) { const a = M.project([90, lat]), b = M.project([135, lat]); ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.stroke(); }
    ctx.setLineDash([]);
  }
  function segment(a, b, color, width, dashed, directed, reverse = false) {
    const k = state.transform.k; ctx.beginPath(); ctx.moveTo(...a); ctx.lineTo(...b); ctx.strokeStyle = color; ctx.lineWidth = width / k; ctx.setLineDash(dashed ? [4 / k, 4 / k] : []); ctx.stroke(); ctx.setLineDash([]);
    if (directed) {
      const from = reverse ? b : a, to = reverse ? a : b, dx = to[0] - from[0], dy = to[1] - from[1], len = Math.hypot(dx, dy);
      if (len * k < 20) return;
      const x = from[0] + dx * .62, y = from[1] + dy * .62, ux = dx / len, uy = dy / len, s = 4 / k;
      ctx.beginPath(); ctx.moveTo(x - ux * s - uy * s * .65, y - uy * s + ux * s * .65); ctx.lineTo(x, y); ctx.lineTo(x - ux * s + uy * s * .65, y - uy * s - ux * s * .65); ctx.stroke();
    }
  }
  function drawEdges(edges, highlight) {
    for (const e of edges) {
      const fa = byFeature.get(e[M.F.a]), fb = byFeature.get(e[M.F.b]);
      if (!visible(fa) && !visible(fb)) continue;
      const a = fa.point, b = fb.point;
      if (!highlight && (!state.matched.has(fa.id) || !state.matched.has(fb.id))) continue;
      if (e[M.F.land] !== null && (highlight || $('showLand').checked)) segment(a, b, highlight ? '#a7854cb0' : '#8d87514f', highlight ? 1.5 : .8, true, false);
      if ((highlight || $('showWater').checked) && (e[M.F.ab] !== null || e[M.F.ba] !== null)) {
        segment(a, b, highlight ? '#46798fcc' : '#6b9aa888', highlight ? 2.2 : 1.2, false, e[M.F.ab] !== null);
        if (e[M.F.ba] !== null) segment(a, b, highlight ? '#46798faa' : '#6b9aa866', 0, false, true, true);
      }
    }
  }
  function drawLabels() {
    if (!$('showNames').checked) return;
    const occupied = [], k = state.transform.k;
    const list = features.filter(f => visible(f) && state.matched.has(f.id)).sort((a, b) => (b.id === state.selected) - (a.id === state.selected) || Number(b.id.startsWith('EZ000')) - Number(a.id.startsWith('EZ000')) || b.c['初始人口'] - a.c['初始人口']);
    for (const f of list) {
      const sel = f.id === state.selected, anchor = f.id.startsWith('EZ000');
      const width = (f.bbox[2] - f.bbox[0]) * k;
      if (!sel && width < (anchor ? 12 : 50)) continue;
      const [x, y] = screen(f.point);
      if (x < 20 || x > state.width - 18 || y < 194 || y > state.height - 135) { if (!sel) continue; }
      const size = sel ? 14 : anchor ? 11 : 10;
      ctx.font = `${sel ? 600 : 400} ${size}px "Noto Sans CJK SC", "Microsoft YaHei", sans-serif`;
      const name = f.c['县名'], full = sel || name.length < 8 || k > state.initialK * 3;
      const text = full ? name : name.slice(0, 6) + '…', tw = ctx.measureText(text).width;
      const box = [x - tw / 2 - 4, y - 24, x + tw / 2 + 4, y + 4];
      if (!sel && occupied.some(o => o[0] < box[2] && o[2] > box[0] && o[1] < box[3] && o[3] > box[1])) continue;
      occupied.push(box); ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
      ctx.lineWidth = 3; ctx.strokeStyle = sel ? '#f7f0d8' : '#eef1e0d9'; ctx.strokeText(text, x, y - 7); ctx.fillStyle = sel ? '#69532e' : '#4b6347'; ctx.fillText(text, x, y - 7);
      ctx.beginPath(); ctx.arc(x, y, sel ? 4 : 2, 0, Math.PI * 2); ctx.fillStyle = sel ? '#bb914a' : '#788f67'; ctx.fill();
      if (sel) { ctx.beginPath(); ctx.arc(x, y, 7, 0, Math.PI * 2); ctx.strokeStyle = '#9f7e4580'; ctx.lineWidth = 1; ctx.stroke(); }
    }
  }
  function draw() {
    if (!model || !state.width) return;
    const d = state.dpr, t = state.transform;
    ctx.setTransform(d, 0, 0, d, 0, 0); ctx.clearRect(0, 0, state.width, state.height);
    ctx.fillStyle = '#e4ebe6'; ctx.fillRect(0, 0, state.width, state.height);
    const glow = ctx.createRadialGradient(state.width * .45, state.height * .48, 20, state.width * .5, state.height * .5, Math.max(state.width, state.height) * .75);
    glow.addColorStop(0, '#f7f4e238'); glow.addColorStop(1, '#afc4b422'); ctx.fillStyle = glow; ctx.fillRect(0, 0, state.width, state.height);
    ctx.setTransform(d * t.k, 0, 0, d * t.k, d * t.x, d * t.y); graticule();
    const inView = features.filter(visible);
    for (const f of inView) {
      const matched = state.matched.has(f.id); ctx.globalAlpha = matched ? 1 : .23; ctx.fillStyle = fill(f.c); ctx.fill(f.path, 'evenodd'); ctx.strokeStyle = '#71826473'; ctx.lineWidth = .55 / t.k; ctx.stroke(f.path);
    }
    ctx.globalAlpha = 1;
    if ($('showLand').checked || $('showWater').checked) drawEdges(model.connections, false);
    drawEdges(selectedEdges, true);
    if (state.route) for (const step of state.route.steps) segment(byFeature.get(step.from).point, byFeature.get(step.to).point, state.route.mode === 'water' ? '#1c6f90' : '#916325', 3.1, false, true);
    for (const id of [state.hovered, state.selected]) {
      const f = byFeature.get(id); if (!f) continue;
      ctx.fillStyle = id === state.selected ? '#e3c78b79' : '#ffffed4d'; ctx.fill(f.path, 'evenodd'); ctx.strokeStyle = id === state.selected ? '#a88038' : '#879c70'; ctx.lineWidth = (id === state.selected ? 2 : 1.5) / t.k; ctx.stroke(f.path);
    }
    ctx.setTransform(d, 0, 0, d, 0, 0); drawLabels();
    if (state.route?.ids.length) for (const [index, label] of [[0, '起'], [state.route.ids.length - 1, '终']]) {
      const [x, y] = screen(byFeature.get(state.route.ids[index]).point); ctx.beginPath(); ctx.arc(x, y, 10, 0, 7); ctx.fillStyle = label === '起' ? '#345c45' : '#9a733b'; ctx.fill(); ctx.font = '10px "Noto Sans CJK SC",sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#fffae9'; ctx.fillText(label, x, y);
    }
    const lat = M.unproject(world([state.width / 2, state.height / 2]))[1], kmPerPx = Math.cos(lat * Math.PI / 180) / t.k;
    const desired = kmPerPx * 68, choices = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000], distance = choices.reduce((a, b) => Math.abs(b - desired) < Math.abs(a - desired) ? b : a);
    $('scaleBar').style.width = `${distance / kmPerPx}px`; $('scaleText').textContent = `约 ${distance} 公里`;
  }
  function hit(point) {
    const p = world(point); hitCtx.setTransform(1, 0, 0, 1, 0, 0);
    return features.find(f => state.matched.has(f.id) && p[0] >= f.bbox[0] && p[0] <= f.bbox[2] && p[1] >= f.bbox[1] && p[1] <= f.bbox[3] && hitCtx.isPointInPath(f.path, ...p, 'evenodd'));
  }
  function legend() {
    let items, title = layerNames[state.layer], note = '';
    if (state.layer === 'terrain') items = M.TERRAINS.map(t => [TERRAIN[t], `${TERRAIN_MARK[t]} ${t}`]);
    if (state.layer === 'population') { items = POP_COLORS.map((c, i) => [c, ['< 1', '1–<3', '3–<6', '6–<10', '≥ 10'][i]]); note = '单位：人 / 平方公里 · 模型人口'; }
    if (state.layer === 'resource') { items = ['未配置', '石料', '陶土', '其他矿源'].map((t, i) => [['#dbe2d2', '#a9baa8', '#c5bb91', '#ab985e'][i], t]); note = '多资源按矿源优先着色，完整资源见详情'; }
    if (state.layer === 'country') { const owner = $('countryFilter').value; const names = owner && owner !== '__none' ? [owner] : ['周', '秦', '晋', '齐', '楚', '燕']; items = names.map(n => [countryColors.get(n), n]).concat([['#d5dccb', '未分配']]); note = '其余国家点选查看 · 归属为剧本设定'; }
    $('legend').innerHTML = `<div class="legend-title">${title}</div><div class="legend-items">${items.map(([color, name]) => `<span class="legend-item"><i class="swatch" style="background:${color}"></i>${esc(name)}</span>`).join('')}</div>${note ? `<div class="legend-note">${note}</div>` : ''}`;
    $('layerTitle').textContent = title;
  }
  function syncHash() { const p = new URLSearchParams({ county: state.selected, layer: state.layer }); try { history.replaceState(null, '', '#' + p); } catch { /* file viewers may restrict history; selection still works */ } }
  function select(id, center = false, open = false) {
    if (!model.byId.has(id)) return;
    state.selected = id; selectedEdges = model.incident.get(id); const c = selectedCounty();
    $('countyName').textContent = c['县名']; $('countyId').textContent = id; $('nameBadge').textContent = nameType(c);
    $('neighborCount').textContent = selectedEdges.length; $('mobileName').textContent = c['县名'];
    renderDetail(); renderList(); drawSoon(); syncHash();
    if (center) focus(id);
    if (open && innerWidth <= 1020) openDrawer('inspector');
  }
  function renderList() {
    const list = state.matches.slice(0, state.listLimit);
    $('countyList').innerHTML = list.length ? list.map(c => `<button class="county-row ${c['县编号'] === state.selected ? 'selected' : ''}" data-select="${esc(c['县编号'])}" title="${esc(c['县名'])} · ${esc(c['县编号'])}" aria-label="查看 ${esc(c['县名'])} ${esc(c['县编号'])}" ${c['县编号'] === state.selected ? 'aria-current="true"' : ''}><span class="tiny-marker">${esc(TERRAIN_MARK[c['地形']])}</span><span><strong>${esc(c['县名'])}</strong><small>${esc(ownerName(c))} · ${esc(c['县编号'])}</small></span><span class="row-arrow">›</span></button>`).join('') : '<div class="empty-state">没有匹配的分区。尝试现代参考名、县编号，或重置筛选。</div>';
    $('moreCounties').hidden = state.matches.length <= state.listLimit;
  }
  function filter(reset = true) {
    if (reset) state.listLimit = 60;
    state.matches = model.search($('search').value, $('countryFilter').value, $('terrainFilter').value, $('resourceFilter').value);
    state.matched = new Set(state.matches.map(c => c['县编号']));
    $('matchCount').textContent = nf.format(state.matches.length); $('visibleCount').textContent = nf.format(state.matches.length);
    const own = $('countryFilter').value; $('mapTitle').textContent = own ? own === '__none' ? '未分配地区' : own + ' · 剧本地区' : '东周全域';
    renderList(); legend(); drawSoon();
  }
  function renderDetail() {
    const c = selectedCounty(); if (!c) return;
    document.querySelectorAll('[data-detail]').forEach(b => { const active = b.dataset.detail === state.detail; b.classList.toggle('active', active); b.setAttribute('aria-selected', active); b.tabIndex = active ? 0 : -1; });
    const body = $('detailBody');
    if (state.detail === 'overview') {
      const land = c['初始土地用途'], total = c['总面积'];
      body.innerHTML = `<div class="metric-duo"><div><span class="metric-label">初始人口 · 模型</span><b class="metric-value">${fmt(c['初始人口'])}<span class="metric-unit">人</span></b></div><div><span class="metric-label">总面积</span><b class="metric-value area">${fmt(total, 2)}</b><div class="metric-unit" style="margin:5px 0 0">公顷</div></div></div>
        <dl class="facts"><div><dt>开局国家</dt><dd>${esc(ownerName(c))}</dd></div><div><dt>所属郡</dt><dd>${esc(c['开局行政归属']['所属郡'] ?? '未设置')}</dd></div><div><dt>主要地形</dt><dd>${esc(TERRAIN_MARK[c['地形']])} ${esc(c['地形'])}</dd></div><div><dt>模型人口密度</dt><dd>${fmt(density(c), 1)} <span class="metric-unit">人/km²</span></dd></div></dl>
        <div class="coordinates-card">${icon('pin')}<div><span>游戏治所坐标 · WGS84</span><b>${coords(c)}</b></div></div>
        <section class="detail-section"><h3>初始土地用途 <small>单位 / 公顷</small></h3><div class="land-stack" aria-hidden="true">${M.LAND.map((key, i) => `<span style="width:${land[key] / total * 100}%;background:${LAND_COLORS[i]}"></span>`).join('')}</div>${M.LAND.map((key, i) => `<div class="land-row"><span class="land-label"><i class="swatch" style="background:${LAND_COLORS[i]}"></i>${key}</span><strong>${fmt(land[key], 2)}</strong><small>${fmt(land[key] / total * 100, 1)}%</small></div>`).join('')}<div class="balanced">七类面积合计 ${fmt(total, 2)} 公顷</div></section>
        <section class="detail-section"><h3>自然资源 <small>不记录储量</small></h3><div class="resource-pills">${c['自然资源'].length ? c['自然资源'].map(r => `<span>◇ ${esc(r)}</span>`).join('') : '<span>未配置资源</span>'}</div></section><div class="model-callout">县界、人口、土地及归属沿用游戏模型。现代参考地名不是古代治所的证明。</div>`;
    } else if (state.detail === 'connections') {
      const ns = model.neighbors(state.selected), outbound = ns.filter(n => n.outbound !== null).length;
      body.innerHTML = `<div class="connection-count">${ns.length} 个直接相连的县 · ${outbound} 条出向水路<br>所有方向均以「${esc(c['县名'])}」为当前县。空值显示为无通道。</div>${ns.map(n => `<button class="connection-card" data-select="${esc(n.county['县编号'])}"><header><h3>${esc(n.county['县名'])}</h3><span>↗</span></header><div class="edge-id">${esc(n.county['县编号'])}</div><div class="edge-values"><span>陆路 · ${n.land === null ? '无通道' : fmt(n.land, 3) + ' km · ' + esc(n.type)}</span><span class="water">水路 出 → ${n.outbound === null ? '无通道' : fmt(n.outbound, 3) + ' km'}</span><span class="water">水路 入 ← ${n.inbound === null ? '无通道' : fmt(n.inbound, 3) + ' km'}</span></div></button>`).join('')}`;
    } else {
      const source = c['资料依据'], ev = evidence(c), entries = typeof source === 'object' ? Object.entries(source) : [['资料依据', source]];
      body.innerHTML = `<div class="source-card"><h3>${esc(nameType(c))}</h3><p>现代参考名：${esc(ev['现代参考名'] || '未记录')}</p><p>命名参考点${ev['命名参考点在县内'] === true ? '位于县内' : ev['命名参考点在县内'] === false ? '不在县内' : '位置未记录'}。与游戏治所是不同的点。</p>${ev['距游戏治所公里'] === undefined ? '' : `<p>参考点距游戏治所：${fmt(ev['距游戏治所公里'], 3)} km</p>`}</div>` + entries.filter(([k]) => !['参考资料', '地名考证', '版本'].includes(k)).map(([k, v]) => `<section class="source-card"><h3>${esc(k)}</h3><p>${esc(typeof v === 'string' ? v : JSON.stringify(v))}</p></section>`).join('');
      const links = [...new Set([...(source['参考资料'] || []), ev['现代地名来源'], ...(ev['古名依据']?.sources || [])].filter(Boolean))];
      body.innerHTML += `<section class="source-card"><h3>来源链接与索引</h3>${links.map(link => { const url = safeUrl(link); return url ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(new URL(url).hostname)} ↗<br>${esc(url)}</a>` : `<p>${esc(link)} · 来源索引</p>`; }).join('')}<p>现代地名：GeoNames / CC BY 4.0。网页不把来源链接视为对模型数值的证明。</p></section>`;
    }
  }
  function setRouteView(active) {
    state.routeView = active; $('routePanel').hidden = !active; $('exploreControls').hidden = active;
    $('navRoute').classList.toggle('active', active); $('navMap').classList.toggle('active', !active);
    if (active && !$('routeFrom').value && selectedCounty()) $('routeFrom').value = displayName(selectedCounty());
    if (active && innerWidth <= 700) openDrawer('sidebar');
  }
  function routeValue(input) {
    const value = input.value.trim();
    const exact = model.counties.find(c => displayName(c) === value || c['县编号'] === value); if (exact) return exact['县编号'];
    const names = model.counties.filter(c => c['县名'] === value); if (names.length === 1) return names[0]['县编号'];
    throw new Error(names.length > 1 ? `「${value}」有重名，请从建议中选择带县编号的一项。` : '请选择有效的起点和终点，也可直接输入县编号。');
  }
  function calculateRoute() {
    state.route = null;
    try {
      const from = routeValue($('routeFrom')), to = routeValue($('routeTo')), mode = $('routeMode').value;
      const r = model.route(from, to, mode);
      if (!r) { $('routeResult').innerHTML = `<p class="warning-message">没有可达的${modeNames[mode]}路线。${mode === 'water' ? '已按单向水路检查，不以陆路或缺失通道补连。' : mode === 'cart' ? '不能走车的陆路未纳入计算。' : '未将空值视为零公里连接。'}</p>`; drawSoon(); return; }
      state.route = r;
      $('routeResult').innerHTML = `<div class="route-summary"><span class="number">${fmt(r.distance, 3)}<small>km</small></span><p>${modeNames[mode]}最短路程 · ${r.steps.length} 段连接 · ${r.ids.length} 个县</p></div><ol class="route-steps">${r.ids.map((id, i) => `<li><button data-select="${esc(id)}">${esc(model.byId.get(id)['县名'])}</button><small>${esc(id)}${i < r.steps.length ? '<br>下一段 ' + fmt(r.steps[i].distance, 3) + ' km' : '<br>到达终点'}</small></li>`).join('')}</ol>`;
      const bounds = r.ids.reduce((b, id) => { const f = byFeature.get(id); return [Math.min(b[0], f.bbox[0]), Math.min(b[1], f.bbox[1]), Math.max(b[2], f.bbox[2]), Math.max(b[3], f.bbox[3])]; }, [Infinity, Infinity, -Infinity, -Infinity]);
      if (r.ids.length > 1) fitBounds(bounds); else focus(from);
      if (innerWidth <= 700) closeDrawers();
      drawSoon();
    } catch (error) { $('routeResult').innerHTML = `<p class="warning-message">${esc(error.message)}</p>`; drawSoon(); }
  }
  function syncDrawers() {
    for (const [id, narrow] of [['sidebar', innerWidth <= 700], ['inspector', innerWidth <= 1020]]) {
      const hidden = narrow && !$(id).classList.contains('open'); $(id).inert = hidden; $(id).setAttribute('aria-hidden', hidden ? 'true' : 'false');
    }
  }
  function openDrawer(id) { closeDrawers(); $(id).classList.add('open'); syncDrawers(); $('drawerShade').hidden = false; }
  function closeDrawers() { $('sidebar').classList.remove('open'); $('inspector').classList.remove('open'); $('drawerShade').hidden = true; syncDrawers(); }
  function showModal(title, html, eyebrow = 'ZHOU ATLAS · DATA') { $('modalTitle').textContent = title; $('modalEyebrow').textContent = eyebrow; $('modalBody').innerHTML = html; $('modal').showModal(); }
  function about() {
    showModal('一张可检查的游戏地图', `<span class="badge-subtle">公元前 770 年 · v0.2-named 数据</span><p>地图展示当前两张基础表中的 ${fmt(model.counties.length)} 个游戏分区和 ${fmt(model.connections.length)} 对直接连接。底层不依赖在线底图，也不请求地图平台或外部字体。</p><h3>读图之前</h3><p>县界为游戏分区，不是古县界。开局国家、人口、土地、粗略地形及交通仍是模型配置；未分配国家不表示无人居住。现代地名仅作为查不到古名时的回退标签。海岸与设计外框不应视为已经考定的东周疆域。</p><h3>连接与路程</h3><p>实线水路、虚线陆路，选中县的连接会加深。地图连线仅连接游戏治所，不是古代路线几何。距离始终读取 JSON：陆路双向共用，水路按方向分别读取。最短路径只在所选通行模式内计算，不自动换乘。</p><p><code>null</code> 意味着没有通道，不是零公里。起终点为同一个县时，寻路总程可以为零；这不在距离表中创造零距离边。</p><h3>两张表直接驱动</h3><p><code>data/counties.json</code>：完整县记录及资料依据。<br><code>data/connections.json</code>：直接相连县对、陆路类型和方向性水路距离。</p><p>网页只读，不修改源数据。筛选只影响显示，不改变全图最短路的计算网络。人口密度以人口除以县面积计算；面积单位为公顷，密度单位为人 / 平方公里。</p><h3>资料与使用</h3><p>每县「资料依据」保留地名来源和游戏假设。现代地名来自 <a href="https://www.geonames.org/" target="_blank" rel="noopener noreferrer">GeoNames</a>，遵循 <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a>。县界沿用的 Natural Earth 低分辨率陆地参考为公有领域，具体处理说明保存在仓库 NOTICE.md。</p><p><a href="https://github.com/hxnfebzkjwbs/zhou-map" target="_blank" rel="noopener noreferrer">查看 GitHub 源代码与数据 ↗</a></p><h3>操作</h3><p>拖动平移，滚轮或双指缩放。点击县，或用左侧地名索引选择。键盘 / 聚焦搜索，地图获得焦点后方向键平移、+ / − 缩放、Home 回全图。窄屏使用底部按钮打开筛选与详情。</p>`);
  }
  function download(name, value) {
    const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json;charset=utf-8' }), url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function exportDialog() {
    showModal('JSON 数据', `<p>完整数据只提供两张 JSON 表。下载不会应用地图筛选，不改写县编号或 <code>null</code>。</p><div class="export-row"><div><h3>县表</h3><p>${fmt(model.counties.length)} 条 · 完整字段、县界与资料依据</p></div><button class="button primary" data-download="counties">${icon('download')} counties.json</button></div><div class="export-row"><div><h3>县际距离表</h3><p>${fmt(model.connections.length)} 对 · 包含方向性水路</p></div><button class="button outline" data-download="connections">${icon('download')} connections.json</button></div><div class="export-row"><div><h3>当前县 · ${esc(selectedCounty()['县名'])}</h3><p>${esc(state.selected)} · 单个完整 JSON 对象</p></div><button class="button outline" data-download="selected">下载本县</button></div><p>下载包含 GeoNames 派生地名时，应保留来源署名与 CC BY 4.0 许可说明。县内已有逐条溯源网址。</p>`);
  }
  function countyJSON() {
    showModal(selectedCounty()['县名'] + ' · 原始记录', '<p>以下为县表中的完整对象，不是经过截断的展示字段。</p><button class="button outline" data-download="selected">下载本县 JSON</button><pre id="jsonView"></pre>', 'JSON · ' + state.selected);
    $('jsonView').textContent = JSON.stringify(selectedCounty(), null, 2);
  }
  function bind() {
    const pointerPos = e => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
    let drag = null, pointers = new Map(), pinch = null;
    canvas.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      const p = pointerPos(e); pointers.set(e.pointerId, p); canvas.setPointerCapture(e.pointerId); $('tooltip').hidden = true;
      if (pointers.size === 1) drag = { id: e.pointerId, start: p, last: p, moved: false };
      else if (pointers.size === 2) { const [a, b] = [...pointers.values()]; const midpoint = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]; pinch = { distance: Math.hypot(a[0] - b[0], a[1] - b[1]), center: world(midpoint), k: state.transform.k }; if (drag) drag.moved = true; }
    });
    canvas.addEventListener('pointermove', e => {
      const p = pointerPos(e); if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);
      if (pointers.size === 2 && pinch) { const [a, b] = [...pointers.values()], mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2], d = Math.hypot(a[0] - b[0], a[1] - b[1]), k = Math.max(state.initialK * .55, Math.min(state.initialK * 35, pinch.k * d / Math.max(1, pinch.distance))); state.transform = { k, x: mid[0] - pinch.center[0] * k, y: mid[1] - pinch.center[1] * k }; drawSoon(); return; }
      if (drag && pointers.size) { if (Math.hypot(p[0] - drag.start[0], p[1] - drag.start[1]) > 3) drag.moved = true; if (drag.moved) { state.transform.x += p[0] - drag.last[0]; state.transform.y += p[1] - drag.last[1]; drawSoon(); } drag.last = p; return; }
      const f = hit(p); if (state.hovered !== f?.id) { state.hovered = f?.id ?? null; drawSoon(); }
      const ll = M.unproject(world(p)); $('coordinates').textContent = `${ll[0].toFixed(3)}° E / ${ll[1].toFixed(3)}° N · WGS84`;
      if (f) { canvas.style.cursor = 'pointer'; const c = f.c; $('tooltip').innerHTML = `<strong>${esc(c['县名'])}</strong><small>${esc(c['县编号'])} · ${esc(nameType(c))}</small><p>${esc(ownerName(c))} / ${esc(c['地形'])} · ${fmt(c['初始人口'])} 人</p>`; $('tooltip').hidden = false; $('tooltip').style.left = Math.max(8, Math.min(p[0] + 16, state.width - 228)) + 'px'; $('tooltip').style.top = Math.max(8, Math.min(p[1] + 18, state.height - 105)) + 'px'; }
      else { canvas.style.cursor = 'grab'; $('tooltip').hidden = true; }
    });
    function pointerEnd(e, cancel = false) {
      if (drag && !drag.moved && pointers.size === 1 && !cancel) { const f = hit(pointerPos(e)); if (f) select(f.id, false, true); }
      pointers.delete(e.pointerId); pinch = null;
      if (pointers.size) { const [id, p] = [...pointers][0]; drag = { id, start: p, last: p, moved: true }; } else drag = null;
    }
    canvas.addEventListener('pointerup', e => pointerEnd(e)); canvas.addEventListener('pointercancel', e => pointerEnd(e, true));
    canvas.addEventListener('pointerleave', () => { $('tooltip').hidden = true; state.hovered = null; drawSoon(); });
    canvas.addEventListener('wheel', e => { e.preventDefault(); zoom(Math.exp(-e.deltaY * .0015), pointerPos(e)); $('tooltip').hidden = true; }, { passive: false });
    canvas.addEventListener('keydown', e => { if (['+', '=', '-', 'Home', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) e.preventDefault(); if (['+', '='].includes(e.key)) zoom(1.35); if (e.key === '-') zoom(1 / 1.35); if (e.key === 'Home') fitBounds(allBounds, true); if (e.key === 'ArrowUp') state.transform.y += 45; if (e.key === 'ArrowDown') state.transform.y -= 45; if (e.key === 'ArrowLeft') state.transform.x += 45; if (e.key === 'ArrowRight') state.transform.x -= 45; drawSoon(); });
    document.addEventListener('keydown', e => { if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName) && !$('modal').open) { e.preventDefault(); if (innerWidth <= 700) openDrawer('sidebar'); $('search').focus(); } if (e.key === 'Escape') closeDrawers(); });
    $('search').addEventListener('input', () => filter());
    ['countryFilter', 'terrainFilter', 'resourceFilter'].forEach(id => $(id).addEventListener('change', () => filter()));
    ['showLand', 'showWater', 'showNames'].forEach(id => $(id).addEventListener('change', drawSoon));
    $('resetFilters').onclick = () => { ['search', 'countryFilter', 'terrainFilter', 'resourceFilter'].forEach(id => $(id).value = ''); filter(); };
    $('moreCounties').onclick = () => { state.listLimit += 80; renderList(); };
    document.querySelectorAll('[data-layer]').forEach(b => b.onclick = () => { state.layer = b.dataset.layer; document.querySelectorAll('[data-layer]').forEach(x => { x.classList.toggle('active', x === b); x.setAttribute('aria-pressed', x === b); }); legend(); drawSoon(); syncHash(); });
    document.querySelector('.detail-tabs').addEventListener('keydown', e => { if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return; e.preventDefault(); const tabs = [...document.querySelectorAll('[data-detail]')], i = tabs.indexOf(document.activeElement); const next = tabs[(i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]; next.click(); next.focus(); });
    document.querySelectorAll('[data-detail]').forEach(b => b.onclick = () => { state.detail = b.dataset.detail; renderDetail(); $('detailBody').scrollTop = 0; });
    document.addEventListener('click', e => {
      const choose = e.target.closest('[data-select]'); if (choose) select(choose.dataset.select, true, true);
      const dl = e.target.closest('[data-download]'); if (dl) { const type = dl.dataset.download; download(type === 'selected' ? state.selected + '.json' : type + '.json', type === 'selected' ? selectedCounty() : model[type]); }
    });
    $('zoomIn').onclick = () => zoom(1.45); $('zoomOut').onclick = () => zoom(1 / 1.45); $('fitMap').onclick = () => fitBounds(allBounds, true); $('focusSelected').onclick = () => focus(state.selected);
    $('brandHome').onclick = e => { e.preventDefault(); fitBounds(allBounds, true); setRouteView(false); };
    $('navMap').onclick = () => setRouteView(false); $('navRoute').onclick = () => setRouteView(true);
    ['navAbout', 'modelNote', 'aboutFooter'].forEach(id => $(id).onclick = about);
    $('calculateRoute').onclick = calculateRoute;
    $('swapRoute').onclick = () => { const a = $('routeFrom').value; $('routeFrom').value = $('routeTo').value; $('routeTo').value = a; clearRouteResult(); };
    function clearRouteResult() { state.route = null; $('routeResult').innerHTML = ''; drawSoon(); }
    $('clearRoute').onclick = () => { clearRouteResult(); $('routeTo').value = ''; };
    ['routeFrom', 'routeTo', 'routeMode'].forEach(id => $(id).addEventListener('input', clearRouteResult));
    $('setStart').onclick = () => { setRouteView(true); $('routeFrom').value = displayName(selectedCounty()); clearRouteResult(); toast('已将 ' + selectedCounty()['县名'] + ' 设为起点'); };
    $('setEnd').onclick = () => { setRouteView(true); $('routeTo').value = displayName(selectedCounty()); clearRouteResult(); toast('已将 ' + selectedCounty()['县名'] + ' 设为终点'); };
    $('openExport').onclick = exportDialog; $('viewCountyJSON').onclick = countyJSON; $('closeModal').onclick = () => $('modal').close();
    $('modal').addEventListener('click', e => { if (e.target === $('modal')) { const r = $('modal').getBoundingClientRect(); if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) $('modal').close(); } });
    $('mobileFilters').onclick = () => openDrawer('sidebar'); $('mobileDetails').onclick = () => openDrawer('inspector'); $('drawerShade').onclick = closeDrawers;
    document.querySelectorAll('[data-close]').forEach(b => b.onclick = closeDrawers);
  }
  function resize() {
    const r = $('mapPanel').getBoundingClientRect(), prev = [state.width, state.height]; state.width = r.width; state.height = r.height; state.dpr = Math.min(devicePixelRatio || 1, 2);
    canvas.width = Math.round(r.width * state.dpr); canvas.height = Math.round(r.height * state.dpr);
    if (prev[0]) { state.transform.x += (state.width - prev[0]) / 2; state.transform.y += (state.height - prev[1]) / 2; } else if (allBounds) fitBounds(allBounds, true);
    if (innerWidth > 1020) closeDrawers(); else syncDrawers(); drawSoon();
  }
  async function init() {
    try {
      const embedded = $('zhou-inline-data'); let data;
      if (embedded) data = JSON.parse(embedded.textContent);
      else {
        if (location.protocol === 'file:') throw new Error('这是源代码版。请用本地 HTTP 服务打开（在目录执行 python -m http.server 8000），或打开另附的离线单文件网页。');
        const get = async name => { const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 30000); try { const res = await fetch('data/' + name + '.json', { signal: controller.signal }); if (!res.ok) throw new Error(`${name}.json 加载失败，HTTP ${res.status}`); return await res.json(); } finally { clearTimeout(timer); } };
        const [counties, connections] = await Promise.all([get('counties'), get('connections')]); data = { counties, connections };
      }
      model = M.create(data.counties, data.connections); prepareGeometry();
      const owners = [...new Set(model.counties.map(c => c['开局行政归属']['所属国家']).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
      countryColors = new Map(owners.map((n, i) => [n, COUNTRY_COLORS[i % COUNTRY_COLORS.length]]));
      $('countryFilter').insertAdjacentHTML('beforeend', owners.map(o => `<option value="${esc(o)}">${esc(o)}</option>`).join('') + '<option value="__none">未分配国家</option>');
      $('terrainFilter').insertAdjacentHTML('beforeend', M.TERRAINS.map(t => `<option>${t}</option>`).join(''));
      $('resourceFilter').insertAdjacentHTML('beforeend', M.RESOURCES.map(r => `<option>${r}</option>`).join('') + '<option value="__none">未配置资源</option>');
      $('countyOptions').innerHTML = model.counties.map(c => `<option value="${esc(displayName(c))}"></option>`).join('');
      $('statCount').textContent = fmt(model.counties.length); $('statEdges').textContent = fmt(model.connections.length); $('statPop').textContent = fmt(model.counties.reduce((n, c) => n + c['初始人口'], 0) / 10000, 1) + '万';
      const params = new URLSearchParams(location.hash.slice(1)); state.selected = model.byId.has(params.get('county')) ? params.get('county') : model.counties[0]['县编号']; state.layer = Object.keys(layerNames).includes(params.get('layer')) ? params.get('layer') : 'terrain';
      bind(); document.querySelector(`[data-layer="${state.layer}"]`).click(); filter(); select(state.selected); resize(); new ResizeObserver(resize).observe($('mapPanel'));
      $('routeFrom').value = displayName(selectedCounty());
      $('loading').hidden = true; document.body.dataset.ready = 'true';
      // Small read-only diagnostics surface for automated regression tests.
      window.ZhouAtlas = { get model() { return model; }, get state() { return state; }, projectToScreen: id => screen(byFeature.get(id).point), select: id => select(id), fit: () => fitBounds(allBounds, true) };
    } catch (error) {
      console.error(error); $('loading').innerHTML = `<div class="loading-mark">!</div><h2>地图未能载入</h2><p>${esc(error.name === 'AbortError' ? '读取 JSON 超时，请检查网络后重试。' : error.message)}</p><button class="button outline" id="retryLoad">重新加载</button>`; $('retryLoad').onclick = () => location.reload();
    }
  }
  init();
})();
