# IDE Chile

Public geospatial services of Chile as one-click layers for RustGIS: the
[Geoportal de Chile](https://www.geoportal.cl) (the national node of IDE Chile),
[IDE MINAGRI](https://ide.minagri.gob.cl) (the Ministry of Agriculture, served by CIREN),
[IDE MINVU](https://ide.minvu.cl) (the Ministry of Housing and Urbanism), the
[INE](https://geoine-ine-chile.opendata.arcgis.com)'s Censuses 2024 and 2017,
[SERNAGEOMIN](https://www.sernageomin.cl) (mining and geology), the
[SBAP](https://sbap.gob.cl) (protected areas), the [DGA](https://dga.mop.gob.cl) (water) and the
[Ministry of Energy](https://ide-energia.minenergia.cl).

Boundaries, soils, land use, wetlands, protected areas, water, mining, energy, urban planning,
census data, roads, schools, health and tourism: 62 layers in a ribbon tab of their own, each a
command that scripts, the command line and the AI Assistant can run too. Three **CUT tools** join
any table of Chile to its communes, provinces or regions by their código único territorial,
however it is written, assign communes to points, and complete codes and names (see
[The CUT tools](#the-cut-tools)); **Layer Metadata** shows any layer's ISO 19115 record (see
[Metadata (ISO 19115)](#metadata-iso-19115)).

## Its tab

**IDE Chile**, at the end of the ribbon's tab strip:

- **Boundaries**: Regions, Communes (IDE MINAGRI)
- **Resources**: **Soils & Agriculture ▾** (9): agrological soils, land use (CONAF), rural
  properties, irrigation, erosion, fruit cadastre, weather stations, summer pastures, hunting ban
  areas; **Mining & Energy ▾** (3): SERNAGEOMIN's mining installations and 2025 tailings
  cadastre, and the Ministry of Energy's power plants, substations and transmission lines
- **Environment**: **Environment & Hazards ▾** (11): wildfires 2024–2025, SERNAGEOMIN's 2023
  volcanic risk ranking, the SBAP's protected areas, Ramsar wetlands, the MMA wetlands
  inventory, hydrography, basins, aquifer restrictions, the DGA's water scarcity decrees in force
  and its 2026 hydrometric network, Köppen-Geiger climate zones
- **Cities**: **Cities & Housing ▾** (8): urban limits, IPT risk areas, heritage, urban
  wetlands, informal settlements, urban parks, housing deficit 2024, bike lanes (IDE MINVU)
- **Census**: **Census 2024 ▾** (6): regions, provinces and communes of the political-administrative
  division the census was taken on, indicators by commune and by region, neighbourhood units with
  their figures; **Census 2017 ▾** (9): regions, provinces, communes, blocks, localities, cities,
  towns, villages, hamlets (INE)
- **Services**: **Transport & Services ▾** (14): roads, railways, airports, schools, preschools,
  higher education, health services, police stations, municipalities, capitals, tourist
  attractions, street markets, sports facilities, Sendero de Chile (Geoportal de Chile)
- **CUT**: Join Table by CUT, Assign Commune to Points, Complete CUT (geoprocessing tools, also
  in the Tools pane under Plugins › IDE Chile)
- **Manage**: Layer Metadata (ISO 19115), Clear IDE Chile, About IDE Chile

The interface is in English with a full Spanish translation; layer names on the map are the
datasets' own names.

## Features, read whole or in the map view

Every layer is added as features: an attribute table, selection, symbology and analysis. They
come as GeoJSON from the service through RustGIS's `layer.addUrl`, on the desktop, on the
command line and in the web app. The plugin needs RustGIS 0.3.0 or later, which brought that
command and the files the CUT tools read; on a web app that can't download from a plugin, it
falls back to the map image where there is one and otherwise gives the address to paste into
**Home › Add Data › From URL**, saying so.

- Small layers (census communes, capitals, airports, Ramsar wetlands…) are read whole and zoomed
  to; ArcGIS layers read whole are generalised to about 10 m, so national data stays a few
  megabytes. The INE's Census 2024 boundaries are the exception: their service answers a request
  finer than about 0.003° with no geometry at all, so they come generalised to about 500 m
  (communes, 17 MB) and 2 km (provinces and regions, about 3 MB each); the IDE MINAGRI
  boundaries have the full detail in the map view.
- Large layers (communes, soils, land use, the wetlands inventory, hydrography, the road
  network, census blocks, schools…) are read in the current map view, up to 5,000 features at a
  time (2,000 from ArcGIS servers), generalised to the view's pixel: zoom to your area first
  (1:2,000,000 or closer), and choose the layer again after moving the map to read the new view.
- An ArcGIS service published by region or by theme (agrological soils, land use, rural
  properties, erosion, the fruit cadastre, urban limits…) adds one layer per published layer that
  reaches the view, named after it, up to eight at a time. A layer whose extent reaches the view
  but holds nothing in it comes in empty.
- Where the service also draws its own map image, `{"map": true}` adds that instead, as a web
  tile layer (an ArcGIS MapServer `export` request per 512-pixel tile, from zoom 4 up): like every
  web tile layer in RustGIS it is drawn under the map's own layers and listed under
  **Map › Basemap**, not in the Layers pane; chosen again, it is taken away, and **Clear Map
  Images** removes them all.

```sh
rustgis-cli run --plugin ide-chile-0.4.0.rgplugin   --cmd 'map.goToXY={"x":-70.65,"y":-33.45}' --cmd 'map.setScale={"scale":300000}'   --cmd 'plugin:ide-chile/communes'   --cmd 'plugin:ide-chile/soils'   --cmd 'plugin:ide-chile/census-2024-communes'   --cmd 'plugin:ide-chile/regions={"map":true}'   --cmd 'share.exportMap={"path":"santiago.png"}'
```

## The CUT tools

Most public data of Chile comes as a table by commune, not as a map: the INE's census figures,
SINIM's municipal finances, CASEN, Servel's votes, CEAD's crime, DEIS's health, Mineduc's
enrolment. Joining it to the communes' geometry fails for three local reasons: the CSV is
semicolon-separated, in Windows-1252 and with decimal commas; the key is written differently on
each side (`1101` and `01101`, `Aysén` and `Aisén`, `Coyhaique` and `Coihaique`, `Región de Los
Lagos`); and data from before 2018 carries Ñuble's communes under Biobío's codes (before 2007,
Arica y Parinacota's and Los Ríos's under Tarapacá's and Los Lagos's). Three tools, in the
Tools pane under **Plugins › IDE Chile** and on the tab's **CUT** group, take care of that:

- **Join Table by CUT**: a layer of communes, provinces or regions (Census 2024 › Communes, or
  any other) and a CSV file. The tool finds the key field in the layer and the key column in the
  table (or takes the ones you name), tells communes from provinces and regions (or takes the
  level you choose), and adds the table's columns to the features. The result is a new layer,
  ready for a choropleth; a table **Rows without a feature** lists every row that joined nothing
  and why (an unknown code or name, an empty key, a duplicate of an earlier row); and the
  messages say how many rows and features matched, how many old codes were translated and how
  many names were matched by another spelling. Features without a row are kept with empty
  columns, or left out.
- **Assign Commune to Points**: a layer of points and one of communes (or provinces, or regions).
  Each point gets `CUT`, `COMUNA`, `COD_PROVINCIA`, `PROVINCIA`, `COD_REGION` and `REGION` of
  the polygon it falls in (as far up as the polygons' level reaches). Both layers must be in the
  same coordinate system; the tool says so when they don't overlap at all.
- **Complete CUT**: a layer with any field of codes or names, however written. The tool adds the
  current CUT and the official names at every level above, and a `CUT_NOTA` field that says when
  a value was an old code, another spelling, empty or unknown. A field the layer already had with
  another value (the Census 2017 layers' numeric `REGION`, say) is kept as `<field>_ORIG`.

An empty layer or table stops a tool with an error. A layer with no field of codes or names
stops Join Table by CUT with an error too, but Assign Commune to Points and Complete CUT end with
a message saying so and no result: they are run on any layer, and say why nothing came of it.

What the tools recognise:

- Codes with or without the leading zero, as text or as numbers (`1101`, `01101`, `1101.0`);
  region codes 1–16 and province codes 11–163 at their levels; the codes of before 2007 and 2018,
  and Antártica's (12202), which the Census 2024 division draws with Cabo de Hornos.
- Names in any case, with or without accents, hyphens and apostrophes, with a leading "Región
  de", "Provincia de" or "Comuna de" (which also settles the level), by their Roman numeral or
  short name for regions (`XIII`, `RM`, `Metropolitana`, `O'Higgins`, `Araucanía`), and by the
  spellings people use that the INE doesn't: Aisén, Puerto Aysén, Coihaique, Paiguano, Marchigüe,
  Llay-Llay, La Calera, Treguaco, Puerto Natales, Puerto Saavedra, Puerto Cisnes, San Vicente de
  Tagua Tagua, Cabo de Hornos (Ex-Navarino), Puerto Williams, Santiago Centro, Rapa Nui. Two
  communes are easy to confuse and kept apart: Florida (Biobío) and La Florida (Santiago).
- CSV files in UTF-8 (with or without a byte order mark) or Windows-1252, separated by
  semicolons, commas, tabs or pipes, with quoted fields; a column is a number when every value in
  it is one, written `1.234,5` or `1234.5` (`12,5%` too); dashes, `s/i` and `n/a` are empty.
  A column with leading zeros stays text.

The fields the tools write are the INE's, so a result lines up with the Census 2024 layers; the
`CUT` is a number, as in those layers. The division behind the tools is the one the INE took the
Census 2024 on, read from its communes layer (345 communes, 56 provinces, 16 regions) and listed
in [`communes.json`](communes.json) with its source, layer and the day it was read, as each
run's last message says. On the command line:

```sh
rustgis-cli run --plugin ide-chile-0.4.0.rgplugin   --cmd 'plugin:ide-chile/census-2024-communes'   --cmd 'gp.run={"tool":"plugin:ide-chile/join-cut","params":{"layer":"Censo 2024: comunas","table":"sinim_2024.csv"}}'   --cmd 'share.exportMap={"path":"ingresos.png"}'
```

## Sources and terms

Every address was checked against the live service on 2026-10-15 (the Census 2024 ones on 2026-10-19). Each layer shows its source as
its credit, and the data stays under its publisher's terms:

| Source | Service | Layers |
|---|---|---|
| [IDE MINAGRI](https://ide.minagri.gob.cl/geoweb/directorio-de-servicios/) | CIREN's ArcGIS Server (`esri.ciren.cl`) | boundaries, soils, land use, properties, irrigation, erosion, fruit cadastre, agroclimate, wildfires, Ramsar wetlands, hunting ban areas |
| [IDE MINVU](https://ide.minvu.cl) | ArcGIS Server (`geoide.minvu.cl`) | urban limits, risk areas, heritage, urban wetlands, settlements, parks, housing deficit, bike lanes |
| [INE](https://geoine-ine-chile.opendata.arcgis.com) | ArcGIS Online feature services | Census 2024, Census 2017 |
| [Geoportal de Chile](https://www.geoportal.cl) | GeoServer WFS (`geoportal.cl/geoserver`) | wetlands (MMA), hydrography, basins, aquifers, climate zones, roads, railways, airports, schools, health, police, municipalities, capitals, tourism, street markets, sports, Sendero de Chile |
| [SERNAGEOMIN](https://www.sernageomin.cl) | ArcGIS Online feature services | mining installations, tailings cadastre 2025, volcanic risk ranking 2023 |
| [SBAP](https://sbap.gob.cl) | ArcGIS Online feature service (Sistema de Información de la Biodiversidad) | protected areas |
| [DGA](https://dga.mop.gob.cl) | ArcGIS Online feature services | water scarcity decrees in force, hydrometric network 2026 |
| [Ministry of Energy](https://ide-energia.minenergia.cl) | ArcGIS Server (`ide-energia.minenergia.cl`) | power plants, substations, transmission lines |

The layers added in 0.4.0 were found through the Geoportal de Chile's catalogue or their
publisher's own ArcGIS organisation, and checked on 2026-10-23: each answers GeoJSON with its
geometry. The SBAP's protected areas are 56 MB whole, so they are read in the map view; the DGA's
services on the Ministry of Public Works' server (`rest-sit.mop.gob.cl`) answer no GeoJSON, so the
plugin reads the DGA's ArcGIS Online copies. SERNAGEOMIN and the SEA have no service in the
catalogue, and Bienes Nacionales' GeoServer refused connections that day.

The Geoportal de Chile's WMS layers are published in EPSG:4326 only, which RustGIS's tile layers
don't draw, so those layers are offered as features.

## Metadata (ISO 19115)

**Layer Metadata (ISO 19115)**, on the tab's **Manage** group and in the Tools pane under
Plugins › IDE Chile, adds a table of the chosen layer's metadata as ISO 19115 elements: title,
abstract, responsible party and its role, creation, publication and revision dates, topic
category, scale, reference system, geographic extent, lineage, use limitation and constraints,
online resources, and the record's own identifier, date, contact and standard.

- Where the IDE Chile catalogue (the Geoportal de Chile's CSW, `https://geoportal.cl/csw`,
  ISO 19139) has a record of the layer, the table is that record, with the address to read it
  live (`GetRecordById`). A record is matched to a layer by the service address its online
  resources name: 42 records for 36 layers, the Ministry of Energy's layers one by one.
- Where it has none (the INE's census layers, most of IDE MINVU's, the new SERNAGEOMIN, SBAP and
  DGA layers), the same elements come from the layer's ArcGIS service and its ArcGIS Online item,
  and `MD_Metadata.metadataStandardName` says so.
- The Ministry of Bienes Nacionales republishes other services' layers in the catalogue for its
  emergency viewer ("[INFORMACIÓN BASE]"), and some of those records name the wrong service; they
  aren't used.

The records are read when the plugin is built (`python refresh.py metadata`, into
`metadata.json`), so the tool works offline and in every RustGIS; its messages say when they were
read. On the command line:

```sh
rustgis-cli run --plugin ide-chile-0.4.0.rgplugin   --cmd 'gp.run={"tool":"plugin:ide-chile/layer-metadata","params":{"layer":"Suelos agrológicos (CIREN)"}}'   --cmd 'share.exportTable={"table":"Metadata of Suelos agrológicos (CIREN)","path":"suelos-iso19115.csv"}'
```

## Permissions

edit and network (adding web tile layers and feature layers, which RustGIS loads from the
services' servers), and files (the CSV table a CUT tool reads: RustGIS hands the plugin the file
you pick, nothing else)

## Build

```sh
rustup target add wasm32-unknown-unknown
python scripts/package.py      # dist/ide-chile-<version>.rgplugin and its SHA-256
cargo test
```

To try it, load the package (or this folder) in RustGIS with **Plugins › Plugin Manager ›
Settings › Add Plugin Folder…**, or on the command line with
`rustgis-cli run --plugin dist/ide-chile-<version>.rgplugin --cmd 'plugin:ide-chile/about'`.

`plugin.json`'s commands, tools, tab and translations, `src/catalog.rs`, `src/communes.rs` and
`src/metadata.rs` are generated by [`generate.py`](generate.py) from one table of layers, the
tools' declarations, the other spellings and old codes the CUT tools recognise, and three files
[`refresh.py`](refresh.py) reads from the services: `services.json`, what each ArcGIS service
publishes (its queryable layers and their extents), `communes.json`, the Census 2024 division,
and `metadata.json`, each layer's ISO 19115 record (`python refresh.py && python generate.py &&
cargo fmt`; a new layer's service alone with `python refresh.py services <id>`). Tests check they agree, that every spelling and old code names
a commune of the division, that every string has its Spanish, and run the three tools on small
layers and tables. CI fails when the generated files don't match the table.

## Release

The plugin is listed in the [RustGIS plugin registry](https://plugins.rustgis.app) from this
repository's releases:

1. Bump `VERSION` in `generate.py` and `version` in `Cargo.toml`, run
   `python generate.py && cargo fmt`, and add the version to [`CHANGELOG.md`](CHANGELOG.md).
2. Commit, then tag and push: `git tag v0.3.0 && git push origin main v0.3.0`.
3. The **Release** workflow tests and builds the plugin, and publishes a release with
   `ide-chile-<version>.rgplugin`, its SHA-256 and `registry-entry.json`.
4. Open a pull request on [opengeos/rustgis-plugins](https://github.com/opengeos/rustgis-plugins)
   that replaces `registry/ide-chile.json` with that `registry-entry.json`.

Versions up to 0.2.0 were built in opengeos/rustgis-plugins, where the plugin started; this
repository keeps their history.
