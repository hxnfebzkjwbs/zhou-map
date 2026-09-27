# v0.3 data attribution, licenses and limitations

## OpenStreetMap-derived Chinese administrative boundaries

Contains information from **OpenStreetMap and its contributors**, made available under the Open Data Commons Open Database License 1.0 (ODbL): https://opendatacommons.org/licenses/odbl/1-0/ . Attribution and source licensing: https://www.openstreetmap.org/copyright .

The CHN ADM3 polygons were obtained through **geoBoundaries**, upstream release commit `9469f09`. The source metadata identifies **Lee Beryman, OpenStreetMap** and a represented boundary year of **2017**. Metadata: https://www.geoboundaries.org/api/current/gbOpen/CHN/ADM3/ . Original download URL, source identity, boundary date and geometry hash remain in each county record.

The OSM-derived boundary database and its adaptations are provided under ODbL 1.0. Retain this notice, contributor attribution and license link when redistributing. The editable derivative database and the selected unmodified source records are available in `data/counties.json` and `sources/real_boundaries/features.json`; build scripts document all processing. Raw source download hashes and metadata are frozen in `sources/real_boundaries/metadata.json`.

Processing consists of selecting complete administrative units intersecting the previous game extent, assigning new stable IDs, adding source-matched names and explicitly modelled game attributes, and computing area and adjacency. **No selected geometry is clipped, simplified, perturbed or replaced with a grid.** Source geometry is compared against each final county record.

## WFP / OCHA administrative boundaries

PRK ADM2 polygons are attributed to **World Food Programme and OCHA ROAP**, represented year **2019**, obtained through geoBoundaries. Source: https://data.humdata.org/dataset/dpr-korea-administrative-boundaries . Metadata: https://www.geoboundaries.org/api/current/gbOpen/PRK/ADM2/ .

License of this separately identified source: **Creative Commons Attribution 3.0 Intergovernmental Organisations (CC BY 3.0 IGO)**, https://creativecommons.org/licenses/by/3.0/igo/ . Source attribution and license are retained alongside each record; inclusion does not imply endorsement by the source organisations. The game-area selection is a modification to the database selection, not to the individual polygon coordinates.

The downloaded Mongolia source (2021, NSO/OCHA) contributes no selected units to this version. Its metadata is retained for acquisition auditing only.

## GeoNames modern labels

Modern name matching uses **GeoNames**, https://www.geonames.org/ , under **CC BY 4.0**, https://creativecommons.org/licenses/by/4.0/ . Format and terms: https://download.geonames.org/export/dump/readme.txt .

This project filters modern administrative features and aliases, excludes explicitly historical/colloquial/ended aliases, and requires a normalized source-name match plus containment in the corresponding boundary. Unmatched source names are kept rather than invented. Selected IDs, URLs, source modification dates and download hashes are frozen in `sources/real_boundaries/names.json`. Modern population data from GeoNames are NOT imported as ancient population.

## Legacy input and historical references

The old Natural Earth-based design extent is used only for selecting whole source counties, not for drawing the new county boundaries. Natural Earth is public domain: https://www.naturalearthdata.com/about/terms-of-use/ . Legacy synthetic grid records are retained only to document model-attribute redistribution and old-to-new spatial correspondence.

Historical location references remain separately cited. A historical place alias within a modern county does not prove the modern county outline existed in 770 BCE. Referenced historical articles are paraphrased, not reproduced wholesale; their inclusion does not license their full text.

## What this release does not assert

These are source-backed modern administrative polygons, **not 770 BCE county boundaries, not an official survey certification, and not a claim of 2026 administrative currency**. Source layers disagree along some boundaries: known overlaps are preserved and reported in `data/source_topology_issues.json`. No position on disputed political boundaries is inferred from choosing a source layer.

Population, seven land-use categories, broad terrain, opening polities, resource placement and routes remain explicitly labelled game models or redistributions of the prior model. The game seat is not certified as an ancient settlement or modern government office. The license notices above apply to the relevant source/derived databases and contents; they do not impose a new blanket license on unrelated application code or historical text.
