#!/usr/bin/env python3
"""Build an explicitly synthetic BCE 770 whole-theatre map for engine testing.

No generated polygon, population, polity radius, terrain class or route is a
historical reconstruction. Run from the repository root. Inputs are frozen.
"""
from __future__ import annotations
import csv, hashlib, json, math, sys
from collections import Counter
from pathlib import Path
from decimal import Decimal
import networkx as nx
from pyproj import Geod, Transformer
from shapely import voronoi_polygons, STRtree
from shapely.geometry import Point, Polygon, MultiPoint, LineString, shape, mapping
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union, nearest_points

ROOT = Path(__file__).resolve().parents[1]
GEOD = Geod(ellps='WGS84')
CRS = '+proj=aea +lat_1=25 +lat_2=47 +lat_0=35 +lon_0=110 +datum=WGS84 +units=m +no_defs'
TO_XY = Transformer.from_crs('EPSG:4326', CRS, always_xy=True).transform
TO_LL = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True).transform
LAND_KEYS = ['耕地','休耕地','可开垦地','牧地','林地','建设用地','难利用土地']
COUNTY_KEYS = ['县编号','县名','县界','治所坐标','总面积','地形','初始人口','初始土地用途','自然资源','开局行政归属','资料依据']
EDGE_KEYS = ['县 A 编号','县 B 编号','陆路距离','陆路通行类型','水路 A→B 距离','水路 B→A 距离']
# Fractions are an exclusive land-use partition, NOT estimated ancient statistics.
FRACTIONS = {
 '平原':[.100,.070,.230,.140,.400,.003,.057],
 '河谷':[.080,.060,.160,.100,.530,.003,.067],
 '丘陵':[.030,.030,.120,.120,.620,.001,.079],
 '山地':[.007,.008,.035,.100,.700,.001,.149],
 '湿地':[.015,.015,.070,.080,.410,.001,.409],
}
DENSITY = {'平原':12., '河谷':8., '丘陵':3., '山地':.8, '湿地':2.}
J = lambda x: json.dumps(x, ensure_ascii=False, separators=(',',':'), allow_nan=False)

def read(path):
    p=ROOT/path
    if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
    bundle=json.loads((ROOT/'sources/scenario_bundle.json').read_text(encoding='utf-8'))
    return bundle[path]

def write(path, value):
    p=ROOT/path; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def parts(g, types=('Polygon',)):
    if g.is_empty: return []
    if g.geom_type in types: return [g]
    return [p for child in getattr(g,'geoms',[]) for p in parts(child,types)]

def geod_area(g):
    return sum(abs(GEOD.geometry_area_perimeter(orient(p,1))[0]) for p in parts(g))/10000

def km(coords):
    return sum(GEOD.inv(a[0],a[1],b[0],b[1])[2] for a,b in zip(coords,coords[1:]))/1000

def region(lon,lat):
    if lon>119 and lat>39: return '辽西辽东'
    if lat>39: return '北部边地'
    if lon<106: return '陇蜀'
    if lon<111 and lat>34: return '关中河东'
    if lat>36: return '燕赵齐北'
    if lon<110 and lat<33: return '巴蜀汉中'
    if lon>118 and lat<33: return '江东'
    if lat<30: return '江南'
    if lat<33: return '江汉淮南'
    return '中原齐鲁'

def terrain(lon,lat,point,rivers):
    # Coarse designer masks, deliberately not advertised as a DEM classification.
    if (111.7<lon<113.4 and 28.6<lat<30.2) or (115.5<lon<116.6 and 28.8<lat<30.0) or (119.4<lon<121.3 and 30.5<lat<32.2):
        return '湿地'
    if rivers.distance(point)<13000: return '河谷'
    if (103.2<lon<104.9 and 29.8<lat<31.6) or (106.8<lon<110.6 and 33.9<lat<34.8) or (113.6<lon<118.3 and 33<lat<40):
        return '平原'
    if lon<103.5 or (32.4<lat<34.0 and lon<112) or (111<lon<114.1 and lat>35.2) or (lat>40 and lon<119):
        return '山地'
    return '丘陵'

def normalise_edge(row):
    """Normalise pair identity without losing directional water semantics."""
    row=dict(row)
    if row['县 A 编号']>row['县 B 编号']:
        row['县 A 编号'],row['县 B 编号']=row['县 B 编号'],row['县 A 编号']
        row['水路 A→B 距离'],row['水路 B→A 距离']=row['水路 B→A 距离'],row['水路 A→B 距离']
    return row

def allocate_area(area):
    return int((Decimal(str(area))*100).to_integral_value())

def build():
    config=read('sources/scenario.json')
    domain_ll=shape(read('sources/playable_land.geojson')['geometry'])
    domain=transform(TO_XY,domain_ll)
    sites=read('sources/sites.json')
    river_input=read('sources/rivers.json')
    river_net=unary_union([transform(TO_XY,LineString(r['coordinates'])) for r in river_input])
    # Stable coordinate-addressed generic IDs; historical-site IDs are frozen in input.
    seeds=[]
    for s in sites:
        p=Point(TO_XY(*s['coordinates']))
        if not domain.covers(p): raise ValueError(f"Site outside extent: {s['id']}")
        seeds.append((s['id'],p,s))
    spacing=config['grid_spacing_m']; minx,miny,maxx,maxy=domain.bounds
    for iy in range(math.floor(miny/spacing)-1,math.ceil(maxy/spacing)+2):
        for ix in range(math.floor(minx/spacing)-1,math.ceil(maxx/spacing)+2):
            p=Point(ix*spacing+(iy%2)*spacing/2,iy*spacing*math.sqrt(3)/2)
            if domain.contains(p) and all(p.distance(t[1])>spacing*.58 for t in seeds[:len(sites)]):
                seeds.append((f'EZG{iy+1000:04d}{ix+1000:04d}',p,None))
    seeds.sort(key=lambda s:s[0])
    # Ordered Voronoi output preserves seed identity. It is a design partition.
    cells=list(voronoi_polygons(MultiPoint([s[1] for s in seeds]),extend_to=domain.envelope,ordered=True).geoms)
    county_geoms=[]; seedrows=[]
    for seed,cell in zip(seeds,cells):
        pieces=sorted(parts(cell.intersection(domain)),key=lambda p:(-p.area,p.centroid.x,p.centroid.y))
        for pi,g in enumerate(pieces):
            if g.area<1: continue
            # Every disconnected piece is a separate county, not an invisible land bridge.
            code=seed[0] if pi==0 else seed[0]+f'-P{pi+1:02d}'
            pt=seed[1] if g.covers(seed[1]) else g.representative_point()
            county_geoms.append(g); seedrows.append((code,pt,seed[2] if pi==0 else None))
    counties=[]; ownercounts=Counter()
    for g,(code,pt,site) in zip(county_geoms,seedrows):
        ll=transform(TO_LL,g); lon,lat=TO_LL(pt.x,pt.y)
        typ=terrain(lon,lat,pt,river_net)
        cents=round(geod_area(ll)*100); area=cents/100
        a=[round(cents*f) for f in FRACTIONS[typ][:-1]]; a.append(cents-sum(a))
        land={k:v/100 for k,v in zip(LAND_KEYS,a)}
        # Only historical-inspired, bounded design cores get a state; not huge nearest-capital empires.
        candidates=[(pt.distance(Point(TO_XY(*s['coordinates'])))/s['radius_km']/1000,s)
                    for s in sites if s['owner'] is not None]
        ratio,near=min(candidates,key=lambda x:x[0])
        owner=site['owner'] if site else (near['owner'] if ratio<=1 else None)
        ownercounts[owner or '未分配国家']+=1
        name=site['name'] if site else region(lon,lat)+'-'+code[3:]
        factor=1.25 if owner is not None else .85
        pop=max(1,round(area/100*DENSITY[typ]*factor))
        res=[]
        if typ in ('山地','丘陵'): res.append('石料')
        if typ in ('平原','河谷'): res.append('陶土')
        note={
          '版本':'v0.1-prototype',
          '县界与总面积':'MODEL-GRID：固定种子Voronoi游戏分区；面积为WGS84椭球面积，不是古县疆界。',
          '县名与治所':site['note'] if site else 'MODEL-NAMES：区域代号与模型代表点，不是考证古县名或真实古治所。',
          '地形':'MODEL-TERRAIN：粗略设计分区，未使用DEM或古湿地复原。',
          '人口与土地':'MODEL-ECONOMY：地形密度×面积×归属系数；七项土地按公开参数分配，非历史统计。',
          '自然资源':'MODEL-RESOURCES：石料/陶土按游戏地形放置；空列表表示本剧本未配置资源，并非地质调查结论。',
          '开局归属':'MODEL-POLITIES：历史启发的剧本核心区，非前770年政治边界复原；国家null表示本版未分配国家，不表示无人居住；郡均未设置。',
          '参考资料':site.get('sources',[]) if site else [],
        }
        counties.append(dict(zip(COUNTY_KEYS,[code,name,mapping(ll),[lon,lat],area,typ,pop,land,res,{'所属国家':owner,'所属郡':None},note])))
    # Two documented geological/archaeological locations; existence is not proof of 770 BCE exploitation.
    resource_points=read('sources/resource_points.json')
    tree=STRtree(county_geoms)
    for r in resource_points:
        p=Point(TO_XY(*r['coordinates']))
        matches=[int(i) for i in tree.query(p) if county_geoms[int(i)].covers(p)]
        if matches:
            c=counties[min(matches)]
            c['自然资源']=list(dict.fromkeys(c['自然资源']+r['resources']))
            c['资料依据']['自然资源']+=' '+r['note']
            c['资料依据']['参考资料']+=r['sources']
    # Geometric adjacency is only a candidate. Corner touching creates no connection.
    pairs=[]; edges=[]; rejected=0
    for i,g in enumerate(county_geoms):
        for j0 in tree.query(g):
            j=int(j0)
            if j<=i: continue
            common=g.boundary.intersection(county_geoms[j].boundary)
            lines=parts(common,('LineString',))
            if not lines or sum(x.length for x in lines)<10: continue
            pairs.append((i,j))
            line=max(lines,key=lambda z:z.length)
            pa,pb=seedrows[i][1],seedrows[j][1]; valid=[]
            for f in (.5,.25,.75,.1,.9):
                gate=line.interpolate(f,normalized=True)
                patha=LineString([pa,gate]); pathb=LineString([gate,pb])
                if g.buffer(.02).covers(patha) and county_geoms[j].buffer(.02).covers(pathb):
                    valid.append((patha.length+pathb.length,gate))
            road=None; cart=None
            if valid:
                gate=min(valid,key=lambda x:x[0])[1]
                t={counties[i]['地形'],counties[j]['地形']}
                detour=1.55 if '山地' in t else 1.35 if ('丘陵' in t or '湿地' in t) else 1.15
                road=round(km([TO_LL(p.x,p.y) for p in [pa,gate,pb]])*detour,3)
                cart='不能走车' if t.intersection({'山地','湿地'}) else '能走车'
            else: rejected+=1
            edges.append(dict(zip(EDGE_KEYS,[counties[i]['县编号'],counties[j]['县编号'],road,cart,None,None])))
    # One water hub per county; disjoint waterways in one county do not teleport.
    water=nx.Graph(); ports={}; county_water_edges={}
    def key(p): return (round(p[0],2),round(p[1],2))
    for i,g in enumerate(county_geoms):
        segs=parts(river_net.intersection(g),('LineString',))
        if not segs: continue
        seat=seedrows[i][1]
        si=min(range(len(segs)),key=lambda k:segs[k].distance(seat))
        port=nearest_points(segs[si],seat)[0]
        ports[i]=key((port.x,port.y)); owned=[]
        for k,seg in enumerate(segs):
            coords=list(seg.coords)
            if k==si:
                z=min(range(len(coords)-1),key=lambda z:LineString(coords[z:z+2]).distance(port))
                coords.insert(z+1,(port.x,port.y))
            for aa,bb in zip(coords,coords[1:]):
                a,b=key(aa),key(bb)
                if a==b: continue
                distance=km([TO_LL(*a),TO_LL(*b)])
                if water.has_edge(a,b): water[a][b]['counties'].add(i)
                else: water.add_edge(a,b,weight=distance,counties={i})
                owned.append((a,b))
        county_water_edges[i]=owned
    for (i,j),row in zip(pairs,edges):
        if i not in ports or j not in ports: continue
        local=nx.Graph()
        for a,b in county_water_edges.get(i,[])+county_water_edges.get(j,[]):
            local.add_edge(a,b,weight=water[a][b]['weight'])
        try: distance=nx.shortest_path_length(local,ports[i],ports[j],weight='weight')
        except (nx.NetworkXNoPath,nx.NodeNotFound): continue
        if distance>0:
            row['水路 A→B 距离']=row['水路 B→A 距离']=round(distance,3)
    edges=[normalise_edge(e) for e in edges if any(e[k] is not None for k in [EDGE_KEYS[2],EDGE_KEYS[4],EDGE_KEYS[5]])]
    edges.sort(key=lambda e:(e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]))
    registry=ROOT/'data/county_id_registry.json'
    if registry.exists():
        old_ids={r['县编号'] for r in json.loads(registry.read_text(encoding='utf-8'))}
        new_ids={c['县编号'] for c in counties}
        if old_ids-new_ids:
            raise ValueError('Stable county IDs would disappear. Provide an explicit ID migration before rebuilding.')
    write('data/counties.json',counties); write('data/connections.json',edges)
    write('data/counties.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','id':c['县编号'],'geometry':c['县界'],'properties':{k:v for k,v in c.items() if k!='县界'}} for c in counties]})
    for name,rows,keys in [('县表.csv',counties,COUNTY_KEYS),('县际距离表.csv',edges,EDGE_KEYS)]:
        with (ROOT/'data'/name).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader()
            writer.writerows({k:J(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    # Stable ID registry is a baseline; extending seeds must not reuse an existing ID.
    write('data/county_id_registry.json',[{'县编号':c['县编号'],'种子坐标':c['治所坐标']} for c in counties])
    write('data/manifest.json',{
       'version':'v0.1-prototype','status':'全域工程原型，非历史复原成品','start_era':'BCE','start_year':770,
       'coordinate_reference_system':'EPSG:4326','coordinate_order':['longitude','latitude'],
       'area_unit':'hectare','distance_unit':'kilometre','area_decimal_places':2,'distance_decimal_places':3,
       'county_count':len(counties),'connection_count':len(edges),'total_population_model':sum(c['初始人口'] for c in counties),
       'total_area_ha':str(sum(Decimal(str(c['总面积'])) for c in counties)),
       'land_routes':sum(e[EDGE_KEYS[2]] is not None for e in edges),'water_pairs':sum(e[EDGE_KEYS[4]] is not None or e[EDGE_KEYS[5]] is not None for e in edges),
       'polity_assignment':dict(ownercounts),'historical_inspired_site_count':len(sites),
       'generic_game_county_count':sum(s[2] is None for s in seedrows),'failed_land_visibility_candidates':rejected,
       'sources':read('sources/catalog.json'),'model':config,
       'warnings':[
          '覆盖设计外框，不声称已核定整个东周历史疆域；现代低分辨率海岸线也不是前770年海岸线。',
          '大量县名是区域代号；历史启发地点的坐标与归属必须另行核验。',
          '人口和七类土地面积均为模型数值，精确小数仅服务账目闭合，不代表史料精度。',
          '陆路由邻接与粗地形假设生成，不是实测古道；河道为手工概化设计，不证明古代通航。',
          '水路每县只选择一个内部水运节点；同县其他不连通水系不自动换乘。',
          '黄河下游使用向河北北流的示意线，不采用现代山东入海线路；前770年具体线位仍未考定。',
          '自然资源为剧本配置而非完整矿产普查；来源提及春秋采冶不能证明前770年已开采。',
       ],
       'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'sources').glob('*.json'))},
    })
    return counties,edges,county_geoms,domain

if __name__=='__main__':
    try:
        c,e,_,_=build()
        print(f'Built {len(c)} counties and {len(e)} direct connections; explicitly synthetic prototype.')
    except Exception as exc:
        print(f'Build failed: {exc}',file=sys.stderr); raise
