# zhou-map

公元前770年开局的战略游戏地图数据。当前数据版本：**v0.2-named**；已加入可交互的**东周舆图网页**。

## 网页入口

根目录 `index.html` 直接读取 `data/counties.json` 和 `data/connections.json`，无需前端构建、CDN、外部字体或地图平台。

```bash
python -m http.server 8000
```

在浏览器访问 `http://localhost:8000/`。也可生成无需服务器、可双击打开的离线单文件：

```bash
python scripts/build_viewer.py --output dist
```

打开 `dist/zhou-atlas-offline.html`。新的网页包只分发两张 JSON 数据，不附 Excel、CSV 或独立 GeoJSON。旧版派生文件保留作工程历史，不是网页输入。

支持地图缩放和平移、地名搜索、国家/地形/资源筛选、四种着色、县详情、来源查看、JSON 导出，以及独立的陆路/车行/单向水路最短路径。地图连线是连接示意，不是实际古道河道。桌面三栏、手机抽屉布局；完整说明见 [网页使用说明](docs/web-viewer.md)。

已通过24项模型测试和37项浏览器检查；自动测试由 `Validate web atlas` 工作流运行。源码提交不表示已经启用公网托管。

## 数据入口

运行时仍然只使用两张基础表：

- `data/counties.json`：县表，1195行。
- `data/connections.json`：县际距离表，3413行。

原工程的CSV为`data/县表.csv`和`data/县际距离表.csv`。`data/counties.geojson`只是县表的另一种表示；来源对照、改名日志和校验报告不是第三张游戏运行表。

本版已将全部区域代号替换为来源支持的地名：4个保留古名、1183个使用现代汉字地名、8个保留地名库原文。古名未获本轮核验不表示该古名不存在，只表示本版依用户要求回退现代名称。现代名称采用GeoNames参考，不宣称为官方现行行政区划认证。

地名升级不改变任何县编号、县界、游戏治所、人口、土地、地形、资源、归属或交通距离。现代命名参考点与游戏治所分别记录，不能混为古代真实治所。所有1195个现代命名参考点均位于对应游戏分区内。

完整说明见`docs/v0.2-named.md`。机器检查结果见`data/validation_report.json`、`data/test_report.json`及`data/reproducibility_report.json`。

## 重建地图数据

仅使用网页时不必重建地图数据。Python 3.11或更新版本，安装依赖之后，使用已冻结的地名对照表，无需联网即可重建：

```bash
python -m pip install -r requirements.txt
python scripts/build_map.py
python scripts/enrich_names.py
python scripts/validate.py
python -m unittest discover -s tests -v
```

初次接入或有意更新地名库时才使用`--gazetteer-dir <目录>`。目录需含CN.zip、KP.zip、MN.zip及alternate-CN.zip、alternate-KP.zip、alternate-MN.zip。`--refresh`会重新生成来源对照，应单独审查结果；日常重建不要使用。原始下载哈希和每条采用的源记录保存在`sources/modern_name_crosswalk.json`。

GitHub Actions的`Build named map`负责构建、验证、运行测试，然后才提交生成数据。取得第三方数据使用公开下载，无需外部账号密钥。

## 两表契约

县表字段：县编号、县名、县界、治所坐标、总面积、地形、初始人口、初始土地用途、自然资源、开局行政归属、资料依据。

县际距离表字段：县 A 编号、县 B 编号、陆路距离、陆路通行类型、水路 A→B 距离、水路 B→A 距离。

- 县编号唯一且固定；县是游戏空间单元，不表示前770年已经普遍实行郡县制。
- 坐标为WGS84，经度在前、纬度在后。县界为GeoJSON Polygon或MultiPolygon。
- 面积单位公顷；耕地、休耕地、可开垦地、牧地、林地、建设用地、难利用土地七类互斥，合计严格等于总面积。
- 地形枚举：平原、河谷、丘陵、山地、湿地。
- 资源枚举：铜矿、铅（锡）矿、铁矿、金（银）矿、煤矿、石料、陶土、盐源、玉石。无设定资源为`[]`，不记录储量。
- 距离单位公里；存在通道必须大于0。不存在通道使用JSON `null`或旧版CSV空单元格，绝不以0代替。无陆路时通行类型也为空。
- 每对县仅一行，A编号小于B编号；交换县顺序时同时交换水路方向。陆路类型只可为能走车、不能走车。
- 陆路双向共用距离，水路两方向独立。流速不是物理距离。非直接连接的县经中间县寻路。
- 未设置的郡为`null`，不套用后世郡名。未分配国家不表示无人居住。

## 来源与局限

地名资料：GeoNames，CC BY 4.0，https://www.geonames.org/ 。数据格式和许可：https://download.geonames.org/export/dump/readme.txt 。署名和加工说明见`NOTICE.md`。

保留古名的材料、日期和适用范围见`sources/historical_name_review.json`；每县的`资料依据.地名考证`可直接追溯到来源URL。

县界、人口、土地用途、粗略地形、国家核心区和道路仍是v0.1游戏模型，不是历史复原。地图设计外框尚未完成整个东周历史范围的逐段核定。现代海岸和地名不等于前770年的海岸和地名。结构校验通过不等于历史准确性已获验证。
