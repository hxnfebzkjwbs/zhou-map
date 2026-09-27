# Data attribution and limitations

## GeoNames

Modern place names and reference coordinates are derived from the GeoNames geographical database: https://www.geonames.org/ . Source downloads: https://download.geonames.org/export/dump/ and https://download.geonames.org/export/dump/alternatenames/ .

License: Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/ . GeoNames provides its data as-is without a warranty of accuracy, timeliness or completeness; see https://download.geonames.org/export/dump/readme.txt .

Changes made by this project: filtering to the game area; selection of modern Chinese aliases or retention of original names; exclusion of explicitly historical, colloquial and ended aliases; association with synthetic game cells; retention of selected source fields; and replacement of selected labels with separately reviewed ancient names. Source geometry points and game seats are distinct. Modern population fields from GeoNames are NOT imported into the 770 BCE population model.

Each selected modern feature retains its GeoNames ID, URL and name evidence in `sources/modern_name_crosswalk.json` and the county table's `资料依据.地名考证`. Raw download checksums are frozen in the crosswalk. When distributing the derived name data, retain GeoNames attribution, this license reference and an indication that the data were modified. This notice does not purport to license unrelated project code or third-party historical text.

## Natural Earth

The v0.1 game extent used a local low-resolution Natural Earth land geometry. Natural Earth data are public domain: https://www.naturalearthdata.com/about/terms-of-use/ . The exact packaged upstream edition was not supplied. The stored geometry and its recorded checksum remain the reproducible input; they do not reconstruct the 770 BCE coast.

## Historical reference sources

Historical sources are cited with URLs and paraphrased scope notes. Their mention does not grant a license to republish their full contents and does not validate the synthetic county boundaries, population, economics, resources or polity radii. See `sources/historical_name_review.json` and `sources/scenario_bundle.json`.

## Game design

Counties are stable game cells, not a claim of a universal county system in 770 BCE. Model-derived terrain, population, land use, transport and political assignments remain explicitly labelled. Modern names are fallback labels, not proof of ancient settlements or present official administrative boundaries.
