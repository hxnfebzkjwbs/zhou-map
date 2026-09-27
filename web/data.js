/* Pure source validation; no inferred administration or modern geography. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ZhouData=api;})(typeof globalThis!=='undefined'?globalThis:this,()=>{
'use strict';
function validate(input){
 let source=input;
 if(input?.type==='FeatureCollection'){
  const m=input.metadata||{};source={...m,yearCode:m.yearCode||'BC770',territories:input.features.map(f=>{const p=f.properties||{};if(p.year!==undefined&&p.year!==-770)throw Error('区域年份不是前770年。');let rings;if(f.geometry?.type==='MultiPolygon')rings=f.geometry.coordinates;else if(f.geometry?.type==='Polygon')rings=[f.geometry.coordinates];else throw Error('只支持来源多边形。');return {oid:p.oid,name:p.name,labelCoord:p.label_lon==null||p.label_lat==null?null:[p.label_lon,p.label_lat],areaDeg2:p.area_deg2,rings};})};
 }
 if(source?.year!==-770||(source.yearCode!==undefined&&source.yearCode!=='BC770'))throw Error('需要前770年（year:-770）的数据。');
 if(!Array.isArray(source.territories)||!source.territories.length)throw Error('文件没有 territories 区域数据；地名索引不能代替边界文件。');
 const ids=new Set(),bounds=[Infinity,Infinity,-Infinity,-Infinity];let points=0;
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 for(const t of source.territories){
  if(typeof t.oid!=='string'||!t.oid||ids.has(t.oid))throw Error('来源编号缺失或重复。');ids.add(t.oid);
  if(t.name!==null&&(typeof t.name!=='string'||!t.name.trim()))throw Error('名称应为字符串或 null。');
  if(t.labelCoord!==null&&(!Array.isArray(t.labelCoord)||t.labelCoord.length!==2||!t.labelCoord.every(finite)||Math.abs(t.labelCoord[0])>180||Math.abs(t.labelCoord[1])>90))throw Error('标签坐标格式错误。');
  if(!Array.isArray(t.rings)||!t.rings.length)throw Error('区域缺少来源线环。');
  for(const group of t.rings){if(!Array.isArray(group)||!group.length)throw Error('空片段组。');for(const ring of group){
   if(!Array.isArray(ring)||ring.length<4)throw Error('边界线环点数不足。');
   for(const p of ring){if(!Array.isArray(p)||p.length!==2||!p.every(finite)||Math.abs(p[0])>180||Math.abs(p[1])>90)throw Error('非法边界坐标。');bounds[0]=Math.min(bounds[0],p[0]);bounds[1]=Math.min(bounds[1],p[1]);bounds[2]=Math.max(bounds[2],p[0]);bounds[3]=Math.max(bounds[3],p[1]);points++;}
   if(ring[0][0]!==ring.at(-1)[0]||ring[0][1]!==ring.at(-1)[1])throw Error('来源线环未闭合；没有自动补点。');
  }}
 }
 const named=source.territories.filter(t=>t.name!==null).length;
 return {source,bounds,counts:{total:ids.size,named,unknown:ids.size-named,points},whiteLandIsError:false};
}
function boundsOf(t){const b=[Infinity,Infinity,-Infinity,-Infinity];for(const g of t.rings)for(const r of g)for(const [x,y]of r){b[0]=Math.min(b[0],x);b[1]=Math.min(b[1],y);b[2]=Math.max(b[2],x);b[3]=Math.max(b[3],y);}return b;}
return {validate,boundsOf};
});
