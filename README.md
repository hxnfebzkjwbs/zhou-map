# 东周舆图 · v0.3真实现代县界版

战略游戏开局为公元前770年。**县界已由规则六边形全部替换为有来源的现代行政区多边形；不是前770年县界复原，也不是2026年现行行政区划或官方勘界认证。**

## 网页

GitHub Pages：https://hxnfebzkjwbs.github.io/zhou-map/

入口为根目录 `index.html`，从main的 `/(root)` 发布。右上角显示v0.3，默认“真实行政边界”图层；加载完成显示2043个分区。县详情直接显示边界来源及年代。若仍显示v0.2，请在Pages部署成功后强制刷新。

支持地图点选、缩放平移、名称/来源原文/历史地点别名搜索、国家/地形/资源筛选、JSON下载，以及独立的陆路/车行/水路寻路。网页直接读取两张JSON，不另造展示地图。

```bash
# 本地打开源码版
python -m http.server 8000
# 在浏览器访问 http://localhost:8000/

# 打包可直接打开的离线单文件
python scripts/build_viewer.py --output dist
```

离线HTML使用gzip无损压缩内嵌相同JSON，保留全部县界坐标；需要支持DecompressionStream的现代浏览器，不需要服务器、CDN、地图平台或额外字体。

## 两张运行时JSON

- `data/counties.json`：2043个行政单元，保持县表原字段。
- `data/connections.json`：5733对直接连接，其中239对另有模型水路。

县界包含1,248,246个坐标点，与所选源几何逐条完全一致。没有Voronoi、六边形生成、随机扰动、平滑、简化或县域裁切。只纳入与旧地图设计范围相交的完整单元。边缘因此与旧外框不同，不能把旧范围差异理解为已考定的古代疆域。

坐标为WGS84，经度在前。面积单位公顷，七类土地以0.01公顷精确闭合。存在通道的距离大于0；无通道为null，没有陆路时通行类型也为null。每对县只有一行，A<B，水路方向分别记录。数据发布不依赖Excel、CSV或单独GeoJSON。

## 来源

|来源|年代|本图单元数|许可|
|---|---:|---:|---|
|geoBoundaries CHN ADM3；Lee Beryman / OpenStreetMap contributors|2017|1997|ODbL 1.0|
|geoBoundaries PRK ADM2；World Food Programme / OCHA ROAP|2019|46|CC BY 3.0 IGO|

原始完整精度数据固定上游提交 `9469f09`。源名称、源单元ID、边界年份、下载网址、许可、几何SHA256均在每县 `资料依据.边界依据` 中。GeoNames仅用于县内精确名称匹配，适用CC BY 4.0。1921个显示名称含汉字，其余保留来源原文，不任意借用邻近城镇名称。

完整归属、处理说明和许可链接见 `NOTICE.md`。OSM派生数据库按ODbL提供，保留其他源的署名和许可。源国别代码不等于前770年国家归属。

## 哪些仍是游戏模型

真实的是来源行政多边形，不是所有属性。人口、七类土地、粗地形、开局国家和资源仍采用明确标注的游戏模型或旧模型的空间重分配。游戏治所不是已核实的古治所或现代政府地址。

连接按真实县域共边重新建立，但车行分类、绕行距离和水运走廊仍是模型，不是已考证古道。地图连线仅示意连接。陆路图有6个连通分量，没有用虚构道路强行连成一片。

## 已知误差与编号变化

源数据之间有12对多边形面积重叠，合计约13.595平方公里，详见 `data/source_topology_issues.json`。保持源几何并报告，不擅自改界，也不声称“零重叠”。CHN元数据标称2867个单元，实际源文件2864个，该差异也已记录。

新RCHN/RPRK编号不复用旧EZ六边形编号。`data/id_migration.json`覆盖全部1195个旧分区，给出多对多相交面积，仅用于迁移审查，不自动决定部队、城市或国界归属。

## 构建与验证

精确复现使用 **Python3.13.5** 及锁定依赖。不同Python版本的浮点累加可能改变模型数值的末位；源县界坐标不经过数值重算。

```bash
python -m pip install -r requirements.txt
python scripts/rebuild_real_boundaries.py
python scripts/validate_real_boundaries.py
python -m unittest discover -s tests -v
node --test tests/web-model.test.cjs
python scripts/build_viewer.py --output dist
```

冻结输入位于 `sources/real_boundaries/`，安装依赖后可离线重建。旧网格自动生成工作流已退役，旧CLI不再重建六边形。

25项Python测试、24项网页模型测试、39项桌面/手机浏览器检查通过。县表、距离表及编号迁移表已在GitHub Actions中与本地验证输出逐字节对照，并再次离线重建确认一致。整体质量状态是 **PASS_WITH_SOURCE_TOPOLOGY_WARNINGS**：数据契约与源几何一致性通过，来源拼接误差仍明确保留。

机器报告：`data/real_boundary_report.json`、`data/validation_report.json`、`data/reproducibility_report.json`、`data/test_report.json`、`data/web_ui_report.json`。更多说明见 `docs/v0.3-real-boundaries.md` 和 `docs/web-viewer.md`。
