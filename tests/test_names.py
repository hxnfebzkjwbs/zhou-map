import copy,re,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from shapely.geometry import shape,Point
from build_map import read,ROOT
from enrich_names import apply,choose_alias,digest,geometric_fingerprint

class NameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=read('data/counties.json')
        cls.f=read('sources/modern_name_crosswalk.json')
        cls.h=read('sources/historical_name_review.json')
        cls.r=read('data/name_enrichment_report.json')
    def test_every_county_named(self):
        self.assertTrue(all(c['县名'].strip() and not re.search(r'EZG|\d{6,}',c['县名']) for c in self.c))
    def test_crosswalk_ids(self):
        ids=[r['县编号'] for r in self.f['rows']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{c['县编号'] for c in self.c})
    def test_non_name_fields_unchanged(self):
        frozen={r['县编号']:r['base_fingerprint'] for r in self.f['rows']}
        for c in self.c:self.assertEqual(geometric_fingerprint(c),frozen[c['县编号']])
    def test_all_name_points_in_cell(self):
        rows={r['县编号']:r for r in self.f['rows']}
        for c in self.c:
            r=rows[c['县编号']]
            self.assertTrue(r['命名参考点在县内'])
            self.assertTrue(shape(c['县界']).covers(Point(r['source_record']['coordinates'])))
    def test_sources_present(self):
        for c in self.c:
            e=c['资料依据']['地名考证']
            self.assertEqual(e['现代地名来源'],f"https://www.geonames.org/{e['GeoNames编号']}/")
            self.assertNotEqual(e['地名语言依据'].get('historic'),True)
    def test_retained_ancient_names(self):
        names={c['县编号']:c['县名'] for c in self.c}
        for r in self.h['accepted']:
            self.assertEqual(names[r['县编号']],r['name'])
            self.assertTrue(r['sources'] and r['evidence'] and r['limitation'])
    def test_historic_alias_excluded(self):
        self.assertIsNone(choose_alias(None,['1','1','zh','古称','1','','','1','','']))
    def test_colloquial_alias_excluded(self):
        self.assertIsNone(choose_alias(None,['1','1','zh','俗称','1','','1','','','']))
    def test_ended_alias_excluded(self):
        self.assertIsNone(choose_alias(None,['1','1','zh','旧名','1','','','','1900','1950']))
    def test_chinese_language_preference(self):
        a=choose_alias(None,['1','1','','测试','','','','','',''])
        b=choose_alias(a,['2','1','zh-Hans','现代名称','','','','','',''])
        self.assertEqual(b['name'],'现代名称')
    def test_idempotent(self):
        counties=copy.deepcopy(self.c)
        first=apply(counties,self.f,self.h);snapshot=copy.deepcopy(counties)
        second=apply(counties,self.f,self.h)
        self.assertEqual(counties,snapshot);self.assertEqual(first,second)
    def test_changed_seat_rejected(self):
        counties=copy.deepcopy(self.c);counties[0]['治所坐标'][0]+=.001
        with self.assertRaises(ValueError):apply(counties,self.f,self.h)
    def test_connections_unchanged(self):
        self.assertEqual(digest(ROOT/'data/connections.json'),self.r['connections_sha256'])

if __name__=='__main__':unittest.main()
