"""Chinese labels require an exact normalized source-name match inside the boundary.
Never substitute the name of a merely nearby town for an administrative unit.
"""
import json,re,unicodedata,zipfile,hashlib
from pathlib import Path
from shapely import STRtree
from shapely.geometry import shape,Point

def norm(s):
    s=unicodedata.normalize('NFKD',s.lower())
    s=''.join(c for c in s if not unicodedata.combining(c)).replace('’',"'")
    stop={'county','district','districty','city','autonomous','banner','special','xian','qu','shi','qi','zizhixian','zizhiqu','zizhiqi','shixiaqu','kun','gun','si','zhuang','yao','tujia','miao','hui','mongol','mongolian','manchu','tibetan','dong','nationalities','and','new','forestry','mining'}
    words=[w.strip('()') for w in s.replace('-',' ').split()]
    return re.sub('[^a-z0-9]','', ''.join(w for w in words if w not in stop and not w.endswith('zu')))

def alias_pick(current,a):
    if len(a)<8 or a[6]=='1' or a[7]=='1' or (len(a)>9 and a[9]):return current
    lang=a[2];name=a[3].strip()
    if lang not in ('','zh','zh-CN','zh-Hans','zh-TW','zh-Hant') or not re.fullmatch(r'[\u3400-\u9fff·・\s（）()\-]+',name) or len(name)<2:return current
    rank=(0 if name.endswith(('县','区','旗','市','縣','區')) else 1,
          0 if lang in ('zh-CN','zh-Hans') else 1 if lang=='zh' else 2 if lang=='' else 3,
          0 if a[4]=='1' else 1,0 if a[5]!='1' else 1,len(name),int(a[0]))
    v={'name':name,'language':lang or 'untagged-Han','alternate_id':int(a[0]),'historic':False,'rank':rank}
    return v if current is None or rank<current['rank'] else current

def build_name_map(features,folder):
    folder=Path(folder);geoms=[shape(f['geometry']) for f in features];tree=STRtree(geoms);records={}
    for cc in ('CN','KP'):
        with zipfile.ZipFile(folder/f'{cc}.zip') as z,z.open(f'{cc}.txt') as file:
            for line in file:
                a=line.decode('utf-8').rstrip('\r\n').split('\t')
                if len(a)!=19 or a[7] not in ('ADM3','ADM2','PPLA3','PPLA2'):continue
                p=Point(float(a[5]),float(a[4]))
                ix=[int(i) for i in tree.query(p,predicate='intersects') if features[int(i)]['properties']['shapeGroup']==('CHN' if cc=='CN' else 'PRK')]
                if not ix:continue
                names={norm(v) for v in [a[1],a[2],*a[3].split(',')] if any('a'<=x.lower()<='z' for x in v)}
                targets=[i for i in ix if norm(features[i]['properties']['shapeName']) in names]
                if targets:records[int(a[0])]={'targets':targets,'type':a[7],'coordinates':[float(a[5]),float(a[4])],'alias':None,'modified':a[18]}
    for cc in ('CN','KP'):
        with zipfile.ZipFile(folder/f'alternate-{cc}.zip') as z,z.open(f'{cc}.txt') as file:
            for line in file:
                a=line.decode('utf-8').rstrip('\r\n').split('\t')
                rec=records.get(int(a[1])) if len(a)>7 else None
                if rec:rec['alias']=alias_pick(rec['alias'],a)
    matched={}
    for gid,rec in records.items():
        if not rec['alias']:continue
        for i in rec['targets']:
            rank=(0 if rec['type']=='ADM3' else 1 if rec['type']=='ADM2' else 2,gid)
            if i not in matched or rank<matched[i][0]:matched[i]=(rank,gid,rec)
    rows=[]
    for i,f in enumerate(features):
        src=f['properties'];name=src['shapeName'];chinese=re.match(r'^[\u3400-\u9fff]+',name)
        row={'shapeID':src['shapeID'],'sourceLayer':f['sourceLayer'],'sourceName':name,'displayName':chinese.group(0) if chinese else name,'nameSource':'geoBoundaries原始名称','namePoint':None}
        if i in matched:
            _,gid,rec=matched[i];alias=dict(rec['alias']);alias.pop('rank')
            row.update(displayName=alias['name'],nameSource=f'https://www.geonames.org/{gid}/',namePoint=rec['coordinates'],nameFeature=rec['type'],nameEvidence=alias,sourceModified=rec['modified'])
        rows.append(row)
    return {'method':'地名原文标准化精确匹配且参考点在对应行政区内；无法匹配保留来源原文；不按距离随意套用邻近地名。',
            'raw_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob('*.zip'))},'rows':rows}
