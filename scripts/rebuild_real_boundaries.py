#!/usr/bin/env python3
"""Replace synthetic grid cells with untouched, source-backed administrative polygons.
Boundary dates are modern, not 770 BCE. Economics and routes remain explicit game models.
"""
from __future__ import annotations
import argparse,hashlib,json,math,shutil,sys
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
import networkx as nx
import shapely
from shapely import STRtree
from shapely.geometry import shape,Point,LineString
from shapely.ops import transform,unary_union,nearest_points
from build_map import GEOD,TO_XY,TO_LL,LAND_KEYS,COUNTY_KEYS,EDGE_KEYS,parts,geod_area,km,J
from real_names import build_name_map

ROOT=Path(__file__).resolve().parents[1]
VERSION='v0.3-real-boundaries'
SOURCE_LEVELS=[('CHN','ADM3'),('MNG','ADM2'),('PRK','ADM2')]

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,x,pretty=False):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,allow_nan=False,indent=2 if pretty else None,separators=None if pretty else (',',':'))+'\n',encoding='utf-8')
def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def geom_digest(g):return hashlib.sha256(J(g).encode()).hexdigest()
def cid(f):return 'R'+f['properties']['shapeGroup']+'-'+hashlib.sha256((f['sourceLayer']+':'+f['properties']['shapeID']).encode()).hexdigest()[:12]

def freeze_inputs(source_dir,gazetteer_dir):
    target=ROOT/'sources/real_boundaries';target.mkdir(parents=True,exist_ok=True)
    fp=target/'features.json';mp=target/'metadata.json';np=target/'names.json'
    if fp.exists() and mp.exists() and np.exists():return load(fp)['features'],load(mp),load(np)
    if not source_dir or not gazetteer_dir:raise ValueError('First build requires --source-dir and --gazetteer-dir; subsequent builds use frozen inputs offline.')
    bundle=load(ROOT/'sources/scenario_bundle.json');domain=shape(bundle['sources/playable_land.geojson']['geometry'])
    features=[];metadata={}
    for iso,level in SOURCE_LEVELS:
        label=iso+'_'+level;src=Path(source_dir)/f'{label}.json';d=load(src);meta=load(Path(source_dir)/f'{label}_metadata.json')
        metadata[label]={**meta,'download_sha256':digest(src),'actual_feature_count':len(d['features']),
                         'metadata_feature_count_matches':int(meta['admUnitCount'])==len(d['features'])}
        for f in d['features']:
            g=shape(f['geometry'])
            if not g.is_valid:raise ValueError('Invalid source polygon; do not silently repair: '+f['properties']['shapeID'])
            # Inclusion only. NEVER clip, simplify, snap, perturb or regenerate a source geometry.
            if g.intersects(domain) and g.intersection(domain).area>0.0001:
                features.append({**f,'sourceLayer':label})
    names=build_name_map(features,gazetteer_dir)
    save(fp,{'type':'FeatureCollection','selection':'Whole units whose intersection with previous design extent exceeds 0.0001 square degrees. Inclusion test only; geometry is not clipped.','features':features})
    save(mp,metadata,True);save(np,names,True)
    return features,metadata,names

def allocate(cents,weights):
    total=sum(weights);raw=[cents*x/total for x in weights]
    values=[math.floor(x) for x in raw]
    for i in sorted(range(len(weights)),key=lambda i:(-(raw[i]-values[i]),i))[:cents-sum(values)]:values[i]+=1
    assert sum(values)==cents and min(values)>=0
    return {k:v/100 for k,v in zip(LAND_KEYS,values)}

def make_water(counties,main_geoms,river_net,pairs):
    ports={};county_edges={};water=nx.Graph()
    key=lambda p:(round(p[0],2),round(p[1],2))
    for i,g in enumerate(main_geoms):
        segs=parts(river_net.intersection(g),('LineString',))
        if not segs:continue
        seat=Point(TO_XY(*counties[i]['治所坐标']));si=min(range(len(segs)),key=lambda k:segs[k].distance(seat))
        port=nearest_points(segs[si],seat)[0];ports[i]=key((port.x,port.y));owned=[]
        for k,seg in enumerate(segs):
            coords=list(seg.coords)
            if k==si:
                z=min(range(len(coords)-1),key=lambda z:LineString(coords[z:z+2]).distance(port))
                coords.insert(z+1,(port.x,port.y))
            for aa,bb in zip(coords,coords[1:]):
                a,b=key(aa),key(bb)
                if a==b:continue
                distance=km([TO_LL(*a),TO_LL(*b)])
                water.add_edge(a,b,weight=distance);owned.append((a,b))
        county_edges[i]=owned
    result={}
    for i,j in pairs:
        if i not in ports or j not in ports:continue
        local=nx.Graph()
        for a,b in county_edges.get(i,[])+county_edges.get(j,[]):local.add_edge(a,b,weight=water[a][b]['weight'])
        try:d=nx.shortest_path_length(local,ports[i],ports[j],weight='weight')
        except (nx.NetworkXNoPath,nx.NodeNotFound):continue
        if d>0.0005:result[(i,j)]=round(d,3)
    return result

def build(source_dir=None,gazetteer_dir=None):
    features,metadata,names=freeze_inputs(source_dir,gazetteer_dir)
    legacy=ROOT/'sources/legacy_grid_counties.json'
    if not legacy.exists():
        old=load(ROOT/'data/counties.json')
        if any(c['县编号'].startswith('RCHN-') for c in old):raise ValueError('Legacy baseline missing; do not reassign new IDs as old ones')
        shutil.copyfile(ROOT/'data/counties.json',legacy)
    old=load(legacy);old_geoms=[transform(TO_XY,shape(c['县界'])) for c in old];old_tree=STRtree(old_geoms)
    bundle=load(ROOT/'sources/scenario_bundle.json')
    river_net=unary_union([transform(TO_XY,LineString(r['coordinates'])) for r in bundle['sources/rivers.json']])
    sites=bundle['sources/sites.json'];accepted={r['县编号']:r for r in load(ROOT/'sources/historical_name_review.json')['accepted']}
    features=sorted(features,key=cid);namemap={x['shapeID']:x for x in names['rows']}
    counties=[];new_geoms=[];main_geoms=[];migration=defaultdict(list)
    for f in features:
        g=shape(f['geometry']);gp=transform(TO_XY,g);main=max(parts(gp),key=lambda p:p.area)
        meta=metadata[f['sourceLayer']];nr=namemap[f['properties']['shapeID']]
        point=Point(TO_XY(*nr['namePoint'])) if nr['namePoint'] else main.representative_point()
        if not main.covers(point):point=main.representative_point()
        lon,lat=TO_LL(point.x,point.y)
        overlap=[]
        for j0 in old_tree.query(gp):
            j=int(j0);area=gp.intersection(old_geoms[j]).area/10000
            if area>0.0001:overlap.append((j,area))
        near=int(old_tree.nearest(point));weights=defaultdict(float)
        for j,a in overlap:weights[j]+=a
        uncovered=max(0.,gp.area/10000-sum(weights.values()));weights[near]+=uncovered
        if not weights:weights[near]=gp.area/10000
        terrain=Counter();owners=Counter();land=[0.]*7;pop=0.
        for j,a in weights.items():
            o=old[j];terrain[o['地形']]+=a;owners[o['开局行政归属']['所属国家']]+=a
            pop+=a*o['初始人口']/o['总面积']
            for k,key in enumerate(LAND_KEYS):land[k]+=a*o['初始土地用途'][key]/o['总面积']
        typ=terrain.most_common(1)[0][0];owner=owners.most_common(1)[0][0]
        area_cents=round(geod_area(g)*100);id_=cid(f)
        historical=[]
        for s in sites:
            if s['id'] in accepted and g.covers(Point(s['coordinates'])):historical.append({'name':accepted[s['id']]['name'],'coordinates':s['coordinates'],'sources':accepted[s['id']]['sources'],'note':'历史地点别名；不把现代县界当作该古城疆域。'})
        resources=['石料'] if typ in ('山地','丘陵') else ['陶土'] if typ in ('平原','河谷') else []
        for res in bundle['sources/resource_points.json']:
            if g.covers(Point(res['coordinates'])):resources=list(dict.fromkeys(resources+res['resources']))
        sources=[meta['gjDownloadURL'],'https://www.geoboundaries.org/']
        if nr['nameSource'].startswith('https:'):sources.append(nr['nameSource'])
        note={
            '版本':VERSION,
            '边界依据':{'类型':'现代真实行政边界资料','并非前770年边界':True,'边界年代':meta['boundaryYearRepresented'],
                '来源':'geoBoundaries / '+meta['boundarySource'],'来源层级':f['sourceLayer'],'来源名称':f['properties']['shapeName'],
                '来源单元编号':f['properties']['shapeID'],'来源网址':meta['gjDownloadURL'],'来源许可':meta['boundaryLicense'],
                '坐标系':'EPSG:4326','几何处理':'完整保留源多边形；未裁切、未简化、未扰动、未生成网格。',
                '几何SHA256':geom_digest(f['geometry']),'官方勘界认证':False},
            '县界与总面积':'县界直接来自注明年代的行政区划数据；面积按该多边形WGS84椭球计算，可能含行政区水面，不是古代统计面积。',
            '县名与治所':'县名来自边界源或县内精确名称匹配；治所字段仍是游戏节点，不保证为现代县政府或古代治所。',
            '地名考证':{'名称类型':'现代行政地名','现代参考名':nr['displayName'],'来源原文':nr['sourceName'],
                '现代地名来源':nr['nameSource'],'命名参考点坐标':nr['namePoint'],
                '命名参考点在县内':True if nr['namePoint'] else None,
                '距游戏治所公里':round(GEOD.inv(lon,lat,*nr['namePoint'])[2]/1000,3) if nr['namePoint'] else None},
            '历史地点':historical,
            '地形':'MODEL：按旧版地形设计区与真实县域相交面积选择主类，尚非DEM地形调查。',
            '人口与土地':'MODEL：按新旧区域相交面积重分配旧版游戏密度；旧范围外使用最近旧分区密度外推。七类面积精确闭合，不是前770年史料。',
            '开局归属':'MODEL：取与县域重叠最多的旧剧本归属，非考定古国边界；郡未设置。',
            '自然资源':'MODEL：石料/陶土仍按游戏地形配置，铜绿山概位按真实县域重新归入；不构成完整矿产调查。',
            '交通依据':'MODEL：仅按主体多边形真实共边建立陆路候选，距离为两游戏节点经共边点的椭球长度乘绕行系数；水路沿旧版手工走廊重新求段，不是已验证古道或古河道。',
            '模型外推面积公顷':round(uncovered,2),'参考资料':sources,
        }
        county=dict(zip(COUNTY_KEYS,[id_,nr['displayName'],f['geometry'],[lon,lat],area_cents/100,typ,max(0,round(pop)),allocate(area_cents,land),resources,{'所属国家':owner,'所属郡':None},note]))
        counties.append(county);new_geoms.append(gp);main_geoms.append(main)
        for j,a in overlap:migration[old[j]['县编号']].append({'新县编号':id_,'新县名':nr['displayName'],'相交面积公顷':round(a,4),'占旧县比例':round(a/(old_geoms[j].area/10000),8)})
    assert len({c['县编号'] for c in counties})==len(counties)
    print('Built source-backed counties:',len(counties),flush=True)
    tree=STRtree(new_geoms);pairs=[];rows=[];overlaps=[]
    for i,g in enumerate(new_geoms):
        for j0 in tree.query(g):
            j=int(j0)
            if j<=i:continue
            conflict=g.intersection(new_geoms[j]).area
            if conflict>1.:
                overlaps.append({'县A':counties[i]['县编号'],'县B':counties[j]['县编号'],'县A名称':counties[i]['县名'],'县B名称':counties[j]['县名'],'重叠平方米':round(conflict,3),
                                 '处理':'保留两份原始边界，不擅自裁切；标记为来源拼接冲突，不能视为已消除重叠。'})
            common=main_geoms[i].boundary.intersection(main_geoms[j].boundary)
            lines=parts(common,('LineString',))
            if not lines or sum(s.length for s in lines)<10:continue
            gate=max(lines,key=lambda s:s.length).interpolate(.5,normalized=True)
            kinds={counties[i]['地形'],counties[j]['地形']};factor=1.55 if '山地' in kinds else 1.35 if kinds&{'丘陵','湿地'} else 1.15
            d=round(km([counties[i]['治所坐标'],TO_LL(gate.x,gate.y),counties[j]['治所坐标']])*factor,3)
            if d<=0:raise ValueError('Zero route length')
            pairs.append((i,j));rows.append(dict(zip(EDGE_KEYS,[counties[i]['县编号'],counties[j]['县编号'],d,'不能走车' if kinds&{'山地','湿地'} else '能走车',None,None])))
    water=make_water(counties,main_geoms,river_net,pairs)
    for pair,row in zip(pairs,rows):
        if pair in water:row[EDGE_KEYS[4]]=row[EDGE_KEYS[5]]=water[pair]
    rows.sort(key=lambda e:(e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]))
    save(ROOT/'data/counties.json',counties);save(ROOT/'data/connections.json',rows)
    registry=[{'县编号':c['县编号'],'来源单元编号':c['资料依据']['边界依据']['来源单元编号'],'来源层级':c['资料依据']['边界依据']['来源层级']} for c in counties]
    save(ROOT/'data/county_id_registry.json',registry,True)
    mig=[]
    for j,o in enumerate(old):
        entries=sorted(migration[o['县编号']],key=lambda x:(-x['相交面积公顷'],x['新县编号']))
        mig.append({'旧县编号':o['县编号'],'旧县名':o['县名'],'新区域':entries,'未覆盖旧区域公顷':round(max(0.,old_geoms[j].area/10000-sum(x['相交面积公顷'] for x in entries)),4)})
    save(ROOT/'data/id_migration.json',{'旧版本':'v0.2-named','新版本':VERSION,'兼容性':'不兼容直接复用旧县ID；本文件只提供多对多空间相交参考，不能自动迁移部队、国界或道路。','rows':mig},True)
    save(ROOT/'data/source_topology_issues.json',overlaps,True)
    union=unary_union(new_geoms);old_domain=transform(TO_XY,shape(bundle['sources/playable_land.geojson']['geometry']))
    graph=nx.Graph();graph.add_nodes_from(c['县编号'] for c in counties);graph.add_edges_from((r[EDGE_KEYS[0]],r[EDGE_KEYS[1]]) for r in rows)
    bysource=Counter(f['sourceLayer'] for f in features)
    report={'version':VERSION,'status':'PASS_WITH_SOURCE_TOPOLOGY_WARNINGS' if overlaps else 'PASS',
        'county_count':len(counties),'connection_count':len(rows),'water_pairs':len(water),'source_units':dict(bysource),
        'all_geometries_exactly_equal_to_source':all(c['县界']==f['geometry'] for c,f in zip(counties,features)),
        'synthetic_grid_count':0,'geometry_vertices':int(sum(shapely.get_num_coordinates(shape(c['县界'])) for c in counties)),
        'min_boundary_vertices':int(min(shapely.get_num_coordinates(shape(c['县界'])) for c in counties)),
        'source_geometry_overlap_pairs':len(overlaps),'source_geometry_overlap_sum_m2':round(sum(x['重叠平方米'] for x in overlaps),3),
        'old_design_extent_not_covered_km2':round(old_domain.difference(union).area/1e6,3),
        'full_counties_beyond_old_design_extent_km2':round(union.difference(old_domain).area/1e6,3),
        'land_components':nx.number_connected_components(graph),'land_isolated_counties':list(nx.isolates(graph)),
        'name_with_Han_count':sum(any('\u3400'<=ch<='\u9fff' for ch in c['县名']) for c in counties),
        'area_ha':str(sum(Decimal(str(c['总面积'])) for c in counties)),
        'metadata_record_count_warnings':[{'source':k,'metadata':int(m['admUnitCount']),'actual':m['actual_feature_count']} for k,m in metadata.items() if not m['metadata_feature_count_matches']],
        'not_claimed':['前770年真实县界或完整古国疆域','官方勘界或2026现行区划认证','真实古代人口土地和交通距离','来源拼接误差已消除','所有岛屿和跨境道路已配置'],
        'boundary_sources':metadata,
        'reproduction':'Frozen input coordinates are retained verbatim as parsed JSON. Selection retains whole source units; no Voronoi, hex grid, smoothing, simplification or clipping.'}
    save(ROOT/'data/real_boundary_report.json',report,True)
    manifest={'version':VERSION,'status':'真实现代行政边界资料+显式前770年游戏模型；不是前770年县界复原',
        'coordinate_reference_system':'EPSG:4326','start_era':'BCE','start_year':770,'county_count':len(counties),'connection_count':len(rows),
        'area_unit':'hectare','distance_unit':'kilometre','area_decimal_places':2,'distance_decimal_places':3,
        'boundary_years':{k:m['boundaryYearRepresented'] for k,m in metadata.items() if k in bysource},
        'id_migration':'id_migration.json','raw_geometry_source':'sources/real_boundaries/features.json','topology_report':'source_topology_issues.json',
        'boundary_data_license':'CHN: ODbL-1.0 (OpenStreetMap contributors); PRK: CC-BY-3.0-IGO (WFP/OCHA); geoBoundaries attribution retained. GeoNames names: CC-BY-4.0.',
        'geometry_exact_match':report['all_geometries_exactly_equal_to_source'],'source_topology_overlap_pairs':len(overlaps),
        'warnings':['边界是注明年代的现代数据，不是770BCE；县级、区、县级市等同为本游戏空间单元。','原始边界未裁切；范围外保留相交完整县域，旧设计海岸不再控制县界。','资料存在跨来源重叠，保留原值并列出冲突；本版不宣称拓扑无重叠。','人口、土地、地形、归属和交通仍是游戏设计或空间重分配，不是资料测量。','新ID命名空间避免假县与真县混用，旧存档须审查迁移。']}
    save(ROOT/'data/manifest.json',manifest,True)
    for pattern in ('*.csv','*.geojson'):
        for p in (ROOT/'data').glob(pattern):p.unlink()
    for name in ('name_enrichment_report.json','reproducibility_report.json','test_report.json','validation_report.json'):
        p=ROOT/'data'/name
        if p.exists():p.unlink()
    print(json.dumps({k:v for k,v in report.items() if k not in ('boundary_sources','land_isolated_counties')},ensure_ascii=False,indent=2),flush=True)
    return counties,rows,report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-dir',type=Path);p.add_argument('--gazetteer-dir',type=Path);args=p.parse_args()
    build(args.source_dir,args.gazetteer_dir)
