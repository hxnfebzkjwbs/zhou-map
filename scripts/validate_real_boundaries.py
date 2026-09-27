#!/usr/bin/env python3
"""Validate exact source correspondence and the canonical two-table contract.
Known cross-source overlaps are reported, never counted as a clean topology pass.
"""
from pathlib import Path
import json,hashlib
from shapely.geometry import shape
from validate import validate
from rebuild_real_boundaries import ROOT,load,save,geom_digest,cid

def main():
 counties=load(ROOT/'data/counties.json');edges=load(ROOT/'data/connections.json')
 features=load(ROOT/'sources/real_boundaries/features.json')['features'];sources={cid(f):f for f in features}
 assert {c['县编号'] for c in counties}==set(sources),'Source unit identity mismatch'
 result=validate(counties,edges,spatial=False)
 for c in counties:
  f=sources[c['县编号']];note=c['资料依据']['边界依据']
  assert c['县界']==f['geometry'],'A source boundary was changed: '+c['县编号']
  assert note['几何SHA256']==geom_digest(f['geometry'])
  assert note['并非前770年边界'] is True
  assert c['县编号'].startswith(('RCHN-','RPRK-','RMNG-'))
  assert shape(c['县界']).is_valid
  assert c['县编号']!=note['来源单元编号']
 issues=load(ROOT/'data/source_topology_issues.json')
 report=load(ROOT/'data/real_boundary_report.json')
 assert len(issues)==report['source_geometry_overlap_pairs']
 assert report['all_geometries_exactly_equal_to_source'] is True
 result.update(status='PASS_WITH_SOURCE_TOPOLOGY_WARNINGS' if issues else 'PASS',
  contract_status='PASS',geometry_source_identity_status='PASS',
  source_geometries_equal=len(counties),synthetic_grid_count=0,
  source_topology_status='WARN' if issues else 'PASS',source_overlap_pairs=len(issues),
  source_overlap_sum_m2=report['source_geometry_overlap_sum_m2'],
  source_metadata_count_warnings=report['metadata_record_count_warnings'],
  land_connected_components=report['land_components'],land_isolated_counties=report['land_isolated_counties'],
  topology_overlap_m2=None,design_extent_gap_m2=None,outside_design_extent_m2=None,
  coverage_claim='完整保留所选真实县域，不裁切到旧范围；未声称完整考定东周历史范围；来源冲突见source_topology_issues.json',
  checked=['两表字段和枚举','县ID与县对唯一性','外键与null语义','土地面积精确闭合','WGS84椭球面积','有效多边形','游戏节点位于县内','逐县源几何完全一致','源几何SHA256','来源时代显式记录','来源拼接冲突清单'],
  not_validated=['官方勘界认证','前770年县界','古人口土地和古道真实性','跨来源拓扑无重叠'])
 save(ROOT/'data/validation_report.json',result,True)
 print(json.dumps(result,ensure_ascii=False,indent=2))
 return result

if __name__=='__main__':main()
