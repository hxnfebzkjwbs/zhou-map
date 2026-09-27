"""v0.3 provenance tests replace obsolete synthetic-grid name-ID assertions."""
import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rebuild_real_boundaries import ROOT,load,cid,geom_digest
from real_names import alias_pick
class RealBoundaryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=load(ROOT/'data/counties.json');cls.f={cid(f):f for f in load(ROOT/'sources/real_boundaries/features.json')['features']}
 def test_every_boundary_is_exact_source_geometry(self):
  for c in self.c:self.assertEqual(c['县界'],self.f[c['县编号']]['geometry'])
 def test_no_synthetic_ids_reused(self):
  self.assertTrue(all(c['县编号'].startswith(('RCHN-','RPRK-','RMNG-')) for c in self.c))
 def test_source_geometry_digest(self):
  for c in self.c:self.assertEqual(c['资料依据']['边界依据']['几何SHA256'],geom_digest(self.f[c['县编号']]['geometry']))
 def test_modern_epoch_is_explicit(self):
  for c in self.c:
   e=c['资料依据']['边界依据'];self.assertTrue(e['并非前770年边界']);self.assertIn(e['边界年代'],['2017','2019','2021'])
 def test_boundary_license_present(self):
  for c in self.c:self.assertTrue(c['资料依据']['边界依据']['来源许可'])
 def test_old_ids_have_explicit_migration(self):
  old=load(ROOT/'sources/legacy_grid_counties.json');mig=load(ROOT/'data/id_migration.json')
  self.assertEqual({x['县编号'] for x in old},{x['旧县编号'] for x in mig['rows']})
  self.assertTrue(all(y['新县编号'] in self.f for x in mig['rows'] for y in x['新区域']))
 def test_old_grid_is_not_a_geometry_fallback(self):
  self.assertEqual(len(self.f),len(self.c));self.assertEqual(load(ROOT/'data/real_boundary_report.json')['synthetic_grid_count'],0)
 def test_source_conflicts_are_not_hidden(self):
  r=load(ROOT/'data/real_boundary_report.json');issues=load(ROOT/'data/source_topology_issues.json')
  self.assertEqual(r['source_geometry_overlap_pairs'],len(issues));self.assertTrue(all(x['重叠平方米']>1 for x in issues))
 def test_historical_alias_rejected_as_modern(self):
  self.assertIsNone(alias_pick(None,['1','1','zh','古称','1','','','1','','']))
 def test_full_county_alias_preferred(self):
  short=alias_pick(None,['1','1','zh','鹿寨','1','1','','','',''])
  full=alias_pick(short,['2','1','zh','鹿寨县','','','','','',''])
  self.assertEqual(full['name'],'鹿寨县')
if __name__=='__main__':unittest.main()
