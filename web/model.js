/* Shared two-table validation and routing. No network or DOM dependency. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.ZhouModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const LAND = ['耕地', '休耕地', '可开垦地', '牧地', '林地', '建设用地', '难利用土地'];
  const TERRAINS = ['平原', '河谷', '丘陵', '山地', '湿地'];
  const RESOURCES = ['铜矿', '铅（锡）矿', '铁矿', '金（银）矿', '煤矿', '石料', '陶土', '盐源', '玉石'];
  const F = { a: '县 A 编号', b: '县 B 编号', land: '陆路距离', type: '陆路通行类型', ab: '水路 A→B 距离', ba: '水路 B→A 距离' };
  const positive = v => typeof v === 'number' && Number.isFinite(v) && v > 0;
  const cents = n => Math.round(n * 100);
  function demand(ok, message) { if (!ok) throw new Error(message); }
  function validate(counties, connections) {
    demand(Array.isArray(counties) && counties.length > 0, '县表必须是非空 JSON 数组');
    demand(Array.isArray(connections), '县际距离表必须是 JSON 数组');
    const ids = new Set();
    for (const c of counties) {
      const id = c['县编号'];
      demand(typeof id === 'string' && id.length > 0 && !ids.has(id), `县编号为空或重复：${id}`);
      ids.add(id);
      demand(typeof c['县名'] === 'string' && c['县名'].trim(), `缺少县名：${id}`);
      demand(TERRAINS.includes(c['地形']), `地形枚举错误：${id}`);
      demand(Number.isInteger(c['初始人口']) && c['初始人口'] >= 0, `人口无效：${id}`);
      demand(positive(c['总面积']), `面积无效：${id}`);
      const lu = c['初始土地用途'];
      demand(lu && LAND.every(k => typeof lu[k] === 'number' && Number.isFinite(lu[k]) && lu[k] >= 0), `土地用途缺失或无效：${id}`);
      demand(LAND.reduce((n, k) => n + cents(lu[k]), 0) === cents(c['总面积']), `土地面积合计不等于总面积：${id}`);
      demand(Array.isArray(c['自然资源']) && c['自然资源'].every(r => RESOURCES.includes(r)), `自然资源枚举错误：${id}`);
      demand(c['开局行政归属'] && ['所属国家', '所属郡'].every(k => c['开局行政归属'][k] === null || typeof c['开局行政归属'][k] === 'string'), `行政归属缺失：${id}`);
      const seat = c['治所坐标'];
      demand(Array.isArray(seat) && seat.length === 2 && seat.every(Number.isFinite) && Math.abs(seat[0]) <= 180 && Math.abs(seat[1]) <= 90, `坐标无效：${id}`);
      const g = c['县界'];
      demand(g && ['Polygon', 'MultiPolygon'].includes(g.type) && Array.isArray(g.coordinates) && g.coordinates.length, `县界无效：${id}`);
      const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
      for (const poly of polys) {
        demand(Array.isArray(poly) && poly.length, `多边形无环：${id}`);
        for (const ring of poly) {
          demand(Array.isArray(ring) && ring.length >= 4 && ring.every(p => Array.isArray(p) && p.length >= 2 && p.slice(0, 2).every(Number.isFinite) && Math.abs(p[0]) <= 180 && Math.abs(p[1]) <= 90), `县界坐标无效：${id}`);
          demand(ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1], `县界环未闭合：${id}`);
        }
      }
    }
    const pairs = new Set();
    for (const e of connections) {
      const a = e[F.a], b = e[F.b], key = JSON.stringify([a, b]);
      demand(ids.has(a) && ids.has(b) && a < b && !pairs.has(key), `无效、重复或非规范县对：${a} / ${b}`);
      pairs.add(key);
      const ds = [e[F.land], e[F.ab], e[F.ba]];
      demand(ds.every(v => v === null || positive(v)), `距离只能为正数或 null：${a} / ${b}`);
      demand(ds.some(v => v !== null), `不存在任何通道的县对：${a} / ${b}`);
      demand(e[F.land] === null ? e[F.type] === null : ['能走车', '不能走车'].includes(e[F.type]), `陆路类型与距离不匹配：${a} / ${b}`);
    }
    return true;
  }
  class MinHeap {
    constructor() { this.values = []; }
    push(value) { const a = this.values; a.push(value); let i = a.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (a[p][0] <= value[0]) break; a[i] = a[p]; i = p; } a[i] = value; }
    pop() { const a = this.values, top = a[0], last = a.pop(); if (a.length) { let i = 0; while (i * 2 + 1 < a.length) { let child = i * 2 + 1; if (child + 1 < a.length && a[child + 1][0] < a[child][0]) child++; if (a[child][0] >= last[0]) break; a[i] = a[child]; i = child; } a[i] = last; } return top; }
  }
  function create(counties, connections) {
    validate(counties, connections);
    const byId = new Map(counties.map(c => [c['县编号'], c]));
    const incident = new Map(counties.map(c => [c['县编号'], []]));
    for (const e of connections) { incident.get(e[F.a]).push(e); incident.get(e[F.b]).push(e); }
    function neighbors(id) {
      return (incident.get(id) || []).map(e => {
        const forward = e[F.a] === id;
        return { county: byId.get(forward ? e[F.b] : e[F.a]), land: e[F.land], type: e[F.type], outbound: e[forward ? F.ab : F.ba], inbound: e[forward ? F.ba : F.ab], edge: e };
      });
    }
    const graphs = new Map();
    function graph(mode) {
      demand(['land', 'cart', 'water'].includes(mode), '未知通行模式');
      if (graphs.has(mode)) return graphs.get(mode);
      const g = new Map(counties.map(c => [c['县编号'], []]));
      for (const e of connections) {
        const a = e[F.a], b = e[F.b];
        if (mode === 'water') {
          if (e[F.ab] !== null) g.get(a).push({ to: b, distance: e[F.ab], edge: e });
          if (e[F.ba] !== null) g.get(b).push({ to: a, distance: e[F.ba], edge: e });
        } else if (e[F.land] !== null && (mode === 'land' || e[F.type] === '能走车')) {
          g.get(a).push({ to: b, distance: e[F.land], edge: e });
          g.get(b).push({ to: a, distance: e[F.land], edge: e });
        }
      }
      graphs.set(mode, g); return g;
    }
    function route(from, to, mode) {
      demand(byId.has(from) && byId.has(to), '起点或终点县编号不存在');
      const g = graph(mode), distances = new Map([[from, 0]]), prev = new Map(), heap = new MinHeap();
      heap.push([0, from]);
      while (heap.values.length) {
        const [d, id] = heap.pop();
        if (d !== distances.get(id)) continue;
        if (id === to) break;
        for (const next of g.get(id)) {
          const nd = d + next.distance;
          if (!distances.has(next.to) || nd < distances.get(next.to)) {
            distances.set(next.to, nd); prev.set(next.to, { from: id, ...next }); heap.push([nd, next.to]);
          }
        }
      }
      if (!distances.has(to)) return null;
      const ids = [to], steps = []; let current = to;
      while (current !== from) { const p = prev.get(current); steps.unshift(p); ids.unshift(p.from); current = p.from; }
      return { ids, steps, distance: distances.get(to), mode };
    }
    function search(query, owner = '', terrain = '', resource = '') {
      const q = query.trim().toLocaleLowerCase();
      return counties.filter(c => {
        const country = c['开局行政归属']['所属国家'];
        if (owner && (owner === '__none' ? country !== null : country !== owner)) return false;
        if (terrain && c['地形'] !== terrain) return false;
        if (resource && (resource === '__none' ? c['自然资源'].length !== 0 : !c['自然资源'].includes(resource))) return false;
        const modern = c['资料依据']?.['地名考证']?.['现代参考名'] || '';
        const aliases = (c['资料依据']?.['历史地点'] || []).map(x => x.name);
        const original = c['资料依据']?.['边界依据']?.['来源名称'] || '';
        return !q || [c['县编号'], c['县名'], modern, original, ...aliases].some(v => v.toLocaleLowerCase().includes(q));
      });
    }
    return { counties, connections, byId, incident, neighbors, graph, route, search };
  }
  // Display projection only. All movement distances come from the input table.
  function project([lon, lat]) { const l = Math.max(-85, Math.min(85, lat)); return [(lon - 112) * Math.PI / 180 * 6371, -(Math.log(Math.tan(Math.PI / 4 + l * Math.PI / 360)) - Math.log(Math.tan(Math.PI / 4 + 35 * Math.PI / 360))) * 6371]; }
  function unproject([x, y]) { const baseline = Math.log(Math.tan(Math.PI / 4 + 35 * Math.PI / 360)); return [x / 6371 * 180 / Math.PI + 112, (2 * Math.atan(Math.exp(baseline - y / 6371)) - Math.PI / 2) * 180 / Math.PI]; }
  return { LAND, TERRAINS, RESOURCES, F, validate, create, project, unproject };
});
