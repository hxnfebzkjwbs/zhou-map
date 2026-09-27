#!/usr/bin/env python3
"""Add source-backed names without changing game geometry, seats or economics.
First run needs --gazetteer-dir; subsequent builds use the frozen crosswalk.
"""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, re, zipfile
from pathlib import Path
import numpy as np
from shapely import STRtree, points
from shapely.geometry import Point, shape
from build_map import ROOT, COUNTY_KEYS, EDGE_KEYS, read, write, J, GEOD

VERSION='v0.2-named'
CCS=('CN','KP','MN')
HAN=re.compile(r'^[\u3400-\u9fff·・\s（）()\-]+$')
PRIORITY={'PPLC':0,'PPLA':1,'PPLA2':2,'PPLA3':3,'ADM3':2,'PPLA4':5,'ADM4':6,'PPL':7,'PPLL':8,'MT':9,'MTS':9,'VAL':10,'PLN':10,'DSRT':10,'LK':10}
REVIEW_DATE='2026-09-27'

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def geometric_fingerprint(c):
    return hashlib.sha256(J({k:v for k,v in c.items() if k not in {'县名','资料依据'}}).encode()).hexdigest()

def choose_alias(current,candidate):
    """Exclude explicitly historic, colloquial and ended aliases."""
    a=candidate
    if len(a)<8 or a[7]=='1' or a[6]=='1' or (len(a)>9 and a[9]):return current
    lang=a[2];name=a[3].strip()
    if not HAN.fullmatch(name) or len(name)<2 or lang not in ('','zh','zh-CN','zh-Hans','zh-TW','zh-Hant'):return current
    rank=(0 if lang in ('zh-CN','zh-Hans') else 1 if lang=='zh' else 2 if lang=='' else 3,
          0 if a[4]=='1' else 1,0 if a[5]=='1' else 1,len(name),int(a[0]))
    item={'name':name,'language':lang or 'untagged-Han','alternate_id':int(a[0]),'preferred':a[4]=='1','historic':False,'rank':rank}
    return item if current is None or rank<current['rank'] else current

def collect_candidates(folder,counties):
    gs=[shape(c['县界']) for c in counties];bounds=[g.bounds for g in gs]
    west=min(b[0] for b in bounds)-1;east=max(b[2] for b in bounds)+1
    south=min(b[1] for b in bounds)-1;north=max(b[3] for b in bounds)+1
    records={};source_hash={}
    for cc in CCS:
        fn=folder/f'{cc}.zip';source_hash[fn.name]=digest(fn)
        with zipfile.ZipFile(fn) as z,z.open(f'{cc}.txt') as f:
            for line in f:
                a=line.decode('utf-8').rstrip('\r\n').split('\t')
                if len(a)!=19 or a[7] not in PRIORITY:continue
                lon,lat=float(a[5]),float(a[4])
                if not(west<=lon<=east and south<=lat<=north):continue
                gid=int(a[0]);records[gid]={'geonames_id':gid,'source_name':a[1],'coordinates':[lon,lat],
                    'feature_class':a[6],'feature_code':a[7],'country_code':a[8],
                    'admin_codes':a[10:14],'source_modified':a[18],'alias':None}
    for cc in CCS:
        fn=folder/f'alternate-{cc}.zip';source_hash[fn.name]=digest(fn)
        with zipfile.ZipFile(fn) as z,z.open(f'{cc}.txt') as f:
            for line in f:
                a=line.decode('utf-8').rstrip('\r\n').split('\t')
                if len(a)<8:continue
                rec=records.get(int(a[1]))
                if rec is not None:rec['alias']=choose_alias(rec['alias'],a)
    result=[]
    for rec in records.values():
        alias=rec.pop('alias')
        if alias:
            alias.pop('rank');rec['name']=alias.pop('name');rec['name_evidence']=alias
        else:
            rec['name']=rec['source_name'];rec['name_evidence']={'language':'source-original','historic':None,'note':'原始主名；未找到可使用的汉字别名，不自行音译。'}
        rec['source_url']=f"https://www.geonames.org/{rec['geonames_id']}/"
        result.append(rec)
    result.sort(key=lambda r:r['geonames_id'])
    return result,gs,source_hash

def assign_modern(folder,counties):
    records,geoms,source_hash=collect_candidates(folder,counties)
    tree=STRtree(geoms);seats=[c['治所坐标'] for c in counties];best={}
    for lo in range(0,len(records),50000):
        batch=records[lo:lo+50000];pp=points(np.asarray([r['coordinates'] for r in batch]))
        for q,idx in tree.query(pp,predicate='intersects').T:
            r=batch[int(q)];idx=int(idx);d=GEOD.inv(*seats[idx],*r['coordinates'])[2]/1000
            rank=(0 if HAN.fullmatch(r['name']) else 1,PRIORITY[r['feature_code']],d,r['geonames_id'])
            if idx not in best or rank<best[idx][0]:best[idx]=(rank,r,d,True)
    ptree=STRtree(points(np.asarray([r['coordinates'] for r in records])))
    for i in range(len(counties)):
        if i in best:continue
        n=int(ptree.nearest(Point(seats[i])));r=records[n]
        d=GEOD.inv(*seats[i],*r['coordinates'])[2]/1000
        if d>100:raise ValueError(f'No defensible modern name within 100 km: {counties[i]["县编号"]}')
        best[i]=((),r,d,False)
    rows=[]
    for i,c in enumerate(counties):
        _,r,d,inside=best[i]
        rows.append({'县编号':c['县编号'],'原型县名':c['县名'],'现代名称':r['name'],'命名参考点在县内':inside,
          '命名参考点距游戏治所公里':round(d,3),'source_record':r,'base_fingerprint':geometric_fingerprint(c)})
    frozen={'version':VERSION,'reviewed_on':REVIEW_DATE,'source':'GeoNames','license':'CC-BY-4.0',
       'attribution':'GeoNames geographical database, https://www.geonames.org/; CC BY 4.0.',
       'raw_source_sha256':source_hash,'candidate_count':len(records),
       'method':'县内现有汉字地名优先；再按首府/地级城市与县域中心/县治/乡镇/聚落/地形选取；同级选择距游戏治所最近者。无县内点时才用100公里内邻近地名，显式标注。',
       'rows':rows}
    write('sources/modern_name_crosswalk.json',frozen)
    return frozen

def apply(counties,frozen,historical):
    names={r['县编号']:r for r in frozen['rows']}
    if set(names)!={c['县编号'] for c in counties}:raise ValueError('Crosswalk IDs differ from county IDs')
    old={r['县编号']:r for r in historical['accepted']};audit=[]
    for c in counties:
        r=names[c['县编号']]
        if r['base_fingerprint']!=geometric_fingerprint(c):raise ValueError('County changed under frozen name mapping: '+c['县编号'])
        before=r['原型县名'];historic=old.get(c['县编号']);rec=r['source_record']
        c['县名']=historic['name'] if historic else r['现代名称']
        mode='有资料支持的古名' if historic else ('现代地名' if HAN.fullmatch(c['县名']) else '现代地名（原文）')
        evidence={'名称类型':mode,'现代参考名':r['现代名称'],'命名参考点坐标':rec['coordinates'],
          '命名参考点在县内':r['命名参考点在县内'],'距游戏治所公里':r['命名参考点距游戏治所公里'],
          '现代地名来源':rec['source_url'],'GeoNames编号':rec['geonames_id'],
          '地物类型':rec['feature_code'],'地名语言依据':rec['name_evidence'],
          '现代地名说明':'现代地理标签回退；不是前770年名称或官方现行行政区划认证。县界和游戏治所不因命名参考点而改变。',
          '古名依据':historic if historic else None}
        c['资料依据']['版本']=VERSION
        c['资料依据']['县名与治所']=('古名有地域与时代资料支持；具体审查范围见地名考证。' if historic else '按用户要求采用现代地名。')+' 治所仍为v0.1游戏节点，不宣称为真实古治所；与命名参考点是两个概念。'
        c['资料依据']['地名考证']=evidence
        c['资料依据']['参考资料']=list(dict.fromkeys(c['资料依据'].get('参考资料',[])+[rec['source_url']]+(historic['sources'] if historic else [])))
        audit.append({'县编号':c['县编号'],'旧县名':before,'新县名':c['县名'],'名称类型':mode,
          '现代参考名':r['现代名称'],'现代地名来源':rec['source_url'],
          '参考点在县内':r['命名参考点在县内'],'参考点距离公里':r['命名参考点距游戏治所公里']})
    return audit

def export(counties,edges):
    write('data/counties.json',counties)
    write('data/counties.geojson',{'type':'FeatureCollection','features':[{'type':'Feature','id':c['县编号'],'geometry':c['县界'],'properties':{k:v for k,v in c.items() if k!='县界'}} for c in counties]})
    for name,rows,keys in [('县表.csv',counties,COUNTY_KEYS),('县际距离表.csv',edges,EDGE_KEYS)]:
        with (ROOT/'data'/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
            w.writerows({k:J(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--gazetteer-dir',type=Path);parser.add_argument('--refresh',action='store_true');a=parser.parse_args()
    counties=read('data/counties.json');edges=read('data/connections.json')
    original_edges=digest(ROOT/'data/connections.json');frozen_path=ROOT/'sources/modern_name_crosswalk.json'
    if a.refresh or not frozen_path.exists():
        if not a.gazetteer_dir:raise ValueError('First build requires --gazetteer-dir; subsequent builds are offline')
        frozen=assign_modern(a.gazetteer_dir,counties)
    else:frozen=read('sources/modern_name_crosswalk.json')
    historical=read('sources/historical_name_review.json');audit=apply(counties,frozen,historical);export(counties,edges)
    with (ROOT/'data/name_changes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
    summary={'version':VERSION,'county_count':len(counties),'connection_count':len(edges),
       'name_types':dict(collections.Counter(r['名称类型'] for r in audit)),
       'counties_with_in_cell_modern_name_anchor':sum(r['参考点在县内'] for r in audit),
       'outside_anchor_counties':[r['县编号'] for r in audit if not r['参考点在县内']],
       'max_modern_anchor_distance_km':max(r['参考点距离公里'] for r in audit),
       'placeholder_name_count':sum(bool(re.search(r'EZG|\d{6,}',c['县名'])) for c in counties),
       'duplicate_display_names':{k:v for k,v in collections.Counter(c['县名'] for c in counties).items() if v>1},
       'stable_fields_unchanged':True,'connections_sha256':original_edges,
       'rejected_or_deferred_historical_names':historical.get('deferred',[]),
       'raw_source_sha256':frozen['raw_source_sha256'],
       'scope':'完成全域命名资料接入；未改变县界、治所、交通、人口、土地、资源及国家归属。现代名称不是现代行政边界。'}
    if summary['placeholder_name_count']:raise ValueError('Generic ID names remain')
    if digest(ROOT/'data/connections.json')!=original_edges:raise ValueError('Connections unexpectedly changed')
    write('data/name_enrichment_report.json',summary)
    manifest=read('data/manifest.json');manifest['version']=VERSION
    manifest['status']='全域已命名的游戏原型；古名有依据者保留，其余现代地名回退'
    manifest['name_enrichment']=summary;manifest['generic_game_county_count']=0
    manifest['source_sha256']={p.name:digest(p) for p in sorted((ROOT/'sources').glob('*.json'))}
    manifest['sources']=[x for x in manifest['sources'] if x['id']!='SRC-GEONAMES']+[{'id':'SRC-GEONAMES','url':'https://www.geonames.org/','license':'CC-BY-4.0','supports':'现代地名及地名参考点；逐县来源保存在资料依据；并非古代人口和疆域来源'}]
    manifest['warnings']=[x for x in manifest['warnings'] if not x.startswith('大量县名是区域代号')]+['现代地名参考点与游戏治所分别记录，不能把现代命名参考点等同于古代治所。']
    write('data/manifest.json',manifest);print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
