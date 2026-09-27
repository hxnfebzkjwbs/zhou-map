#!/usr/bin/env python3
"""Validate both gameplay tables, spatial topology and directional routing."""
from __future__ import annotations
import json, math, sys
from decimal import Decimal
import networkx as nx
from shapely.geometry import shape, Point
from shapely import STRtree
from shapely.ops import unary_union, transform
from build_map import COUNTY_KEYS, EDGE_KEYS, LAND_KEYS, TO_XY, geod_area, read, write

TERRAINS={'平原','河谷','丘陵','山地','湿地'}
RESOURCES={'铜矿','铅（锡）矿','铁矿','金（银）矿','煤矿','石料','陶土','盐源','玉石'}

def check(condition,message):
    if not condition: raise ValueError(message)

def number(v):
    return type(v) in (int,float) and math.isfinite(v)

def validate(counties,edges,domain=None,spatial=True):
    check(isinstance(counties,list) and len(counties)>0,'县表不能为空')
    check(isinstance(edges,list),'距离表必须为列表')
    ids=set();projected=[];edgepairs=set()
    for c in counties:
        check(set(c)==set(COUNTY_KEYS),'县表字段不符合契约')
        code=c['县编号'];check(isinstance(code,str) and code and code.strip()==code and code not in ids,'县编号重复/为空/有空格');ids.add(code)
        check(isinstance(c['县名'],str) and c['县名'].strip(),'县名为空')
        check(c['地形'] in TERRAINS,'地形枚举无效')
        check(type(c['初始人口']) is int and c['初始人口']>=0,'人口必须为非负整数')
        check(number(c['总面积']) and c['总面积']>0,'总面积必须为有限正数')
        lu=c['初始土地用途'];check(isinstance(lu,dict) and set(lu)==set(LAND_KEYS),'七类土地用途不完整')
        check(all(number(x) and x>=0 for x in lu.values()),'土地用途面积无效')
        check(sum(Decimal(str(x)) for x in lu.values())==Decimal(str(c['总面积'])),'土地用途合计不等于总面积')
        check(all(Decimal(str(x))*100==(Decimal(str(x))*100).to_integral_value() for x in [c['总面积'],*lu.values()]),'面积超过两位小数')
        r=c['自然资源'];check(isinstance(r,list) and all(isinstance(x,str) and x in RESOURCES for x in r) and len(r)==len(set(r)),'资源枚举或重复项无效')
        adm=c['开局行政归属'];check(isinstance(adm,dict) and set(adm)=={'所属国家','所属郡'},'行政归属字段不完整')
        check(all(v is None or (isinstance(v,str) and v.strip()) for v in adm.values()),'行政空值请用null')
        check(isinstance(c['资料依据'],(str,dict)) and c['资料依据'],'资料依据为空')
        geo=c['县界'];check(geo.get('type') in ('Polygon','MultiPolygon'),'县界必须为Polygon/MultiPolygon')
        g=shape(geo);check(not g.is_empty and g.is_valid,'县界为空或无效')
        bx=g.bounds;check(-180<=bx[0]<=bx[2]<=180 and -90<=bx[1]<=bx[3]<=90,'县界经纬度超界')
        xy=c['治所坐标'];check(isinstance(xy,list) and len(xy)==2 and all(number(x) for x in xy),'治所必须为两个有限数')
        check(-180<=xy[0]<=180 and -90<=xy[1]<=90,'治所经纬度超界')
        check(g.buffer(1e-10).covers(Point(xy)),'治所不在县界内')
        check(abs(geod_area(g)-c['总面积'])<=.0051,'总面积与椭球几何面积不一致')
        projected.append(transform(TO_XY,g))
    for e in edges:
        check(set(e)==set(EDGE_KEYS),'距离表字段不符合契约')
        a,b=e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]
        check(a in ids and b in ids,'距离表存在悬空外键')
        check(a<b,'县对必须A<B，且不能自连接')
        check((a,b) not in edgepairs,'同一县对重复');edgepairs.add((a,b))
        road,cart,ab,ba=[e[x] for x in EDGE_KEYS[2:]]
        check(all(x is None or (number(x) and x>0) for x in [road,ab,ba]),'存在通道必须为正距离；无通道必须为null，禁止0、空字符串及NaN')
        check((road is None and cart is None) or (road is not None and cart in {'能走车','不能走车'}),'陆路与通行类型不一致')
        check(any(x is not None for x in [road,ab,ba]),'空县对不应入表')
    overlap=0.;gap=None;outside=None
    if spatial:
        tree=STRtree(projected)
        for i,g in enumerate(projected):
            for j0 in tree.query(g):
                j=int(j0)
                if j>i:
                    area=g.intersection(projected[j]).area
                    check(area<1.,f'县界重叠：{i},{j},面积{area}平方米');overlap+=area
        if domain is not None:
            whole=unary_union(projected);d=transform(TO_XY,domain)
            gap=d.difference(whole).area;outside=whole.difference(d).area
            check(gap<10 and outside<10,'分区没有完整覆盖设计范围或越界')
    graph=route_graph(counties,edges,'land')
    components=list(nx.connected_components(graph.to_undirected()))
    return {'status':'PASS','county_count':len(counties),'connection_count':len(edges),
       'land_connected_components':len(components),'land_isolated_counties':sorted(nx.isolates(graph)),
       'land_routes':sum(e[EDGE_KEYS[2]] is not None for e in edges),
       'water_pairs':sum(e[EDGE_KEYS[4]] is not None or e[EDGE_KEYS[5]] is not None for e in edges),
       'one_way_water_pairs':sum((e[EDGE_KEYS[4]] is None)!=(e[EDGE_KEYS[5]] is None) for e in edges),
       'topology_overlap_m2':overlap,'design_extent_gap_m2':gap,'outside_design_extent_m2':outside,
       'coverage_claim':'仅验证设计外框覆盖；不验证历史范围或史料真实性',
       'checked':['字段与枚举','主键唯一','县对唯一与规范顺序','外键','正距离/null语义','陆路类型同步','七类面积精确闭合','椭球面积','有效多边形','治所位于县内','跨县面积重叠','设计范围覆盖','连通分量'],
       'not_validated':['前770年县名与治所考证','前770年各国疆域','古代人口与土地统计','古道和河道实际线位与通行性','完整自然资源分布']}

def route_graph(counties,edges,mode):
    """Build one mode, without inventing cost-free land/water transfers."""
    if mode not in {'land','cart','water'}: raise ValueError('mode must be land/cart/water')
    g=nx.DiGraph();g.add_nodes_from(c['县编号'] for c in counties)
    for e in edges:
        a,b=e[EDGE_KEYS[0]],e[EDGE_KEYS[1]]
        if mode in {'land','cart'}:
            d=e[EDGE_KEYS[2]]
            if d is not None and (mode=='land' or e[EDGE_KEYS[3]]=='能走车'):
                g.add_edge(a,b,weight=d);g.add_edge(b,a,weight=d)
        else:
            for u,v,k in [(a,b,EDGE_KEYS[4]),(b,a,EDGE_KEYS[5])]:
                if e[k] is not None:g.add_edge(u,v,weight=e[k])
    return g

if __name__=='__main__':
    try:
        result=validate(read('data/counties.json'),read('data/connections.json'),shape(read('sources/playable_land.geojson')['geometry']))
        write('data/validation_report.json',result)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,KeyError,TypeError) as e:
        print(f'VALIDATION FAILED: {e}',file=sys.stderr);sys.exit(1)
