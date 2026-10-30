# Changelog

## 0.5.1 (2026-10-29)

- **Protected Areas** reads the SBAP's `SINAP` service, the same layer of 246 areas: the SBAP
  closed `Áreas_Protegidas`, which now asks for a token, so 0.5.0's layer read nothing. Its
  ISO 19115 record is read again from the new service's item.
- **Mining Concessions** goes: SERNAGEOMIN's `WGS84` service, the one copy of the mining
  cadastre the plugin found public, was taken down, and no other public service of it was found.
  The layer comes back when there is one; `filter`, `fields` and `max_scale` stay for it. The
  Mining & Energy menu keeps the mining installations, the tailings cadastre and energy.
- 62 layers.

## 0.5.0 (2026-10-23)

- **Mining Concessions**: SERNAGEOMIN's mining cadastre, the exploration and exploitation
  concessions in force (constituted or in process; eliminated ones are left out), with roll,
  name, type, hectares, expiry, holder's name, registration and commune; the holder's RUT isn't
  read. Read in the map view at 1:100,000 or closer: a mining district holds tens of thousands
  of concessions at 1:1,000,000, and the service gives 2,000 to a request.
- A layer read in the map view says when its server cut the read short (the view held more than
  the service gives at once), instead of adding a partial layer in silence.
- Each layer can have its own filter, fields and closest scale (`filter`, `fields`, `max_scale`
  in `generate.py`).
- **Clear Map Images** goes, making room for the concessions within RustGIS's 64 commands: a map
  image is taken away by choosing it again, or from **Map › Basemap**.

## 0.4.0 (2026-10-23)

- Seven layers of mining, water, protected areas and energy, found through the IDE Chile
  catalogue or their publisher's ArcGIS organisation and checked live: SERNAGEOMIN's mining
  installations, 2025 tailings cadastre and 2023 volcanic risk ranking; the SBAP's protected
  areas; the DGA's water scarcity decrees in force and 2026 hydrometric network; and the Ministry
  of Energy's power plants, substations and transmission lines. 62 layers; the plugin's 64
  commands are RustGIS's limit.
- **Layer Metadata (ISO 19115)**, a tool: the chosen layer's metadata as a table of ISO 19115
  elements, from its record in the IDE Chile catalogue (the Geoportal de Chile's CSW) where there
  is one (42 records for 36 layers), else from its ArcGIS service. Read by `refresh.py` into
  `metadata.json`, so it works offline and in every RustGIS.
- The ribbon's Agriculture group is now Resources, with the Soils & Agriculture and Mining &
  Energy menus (RustGIS takes at most 8 groups on a tab).

## 0.3.1 (2026-10-22)

- The Census 2024 regions, provinces and communes come with their geometry: the INE's boundary
  service answered the 10 m generalisation the plugin asked for (since 0.2.0) with no geometry for
  all but two features, so these layers now ask for the coarsest level that keeps them whole
  (about 500 m for the communes, 2 km for provinces and regions). Smaller downloads too: 17, 3
  and 2 MB.
- The CUT tools work on big layers: they keep each feature's geometry as the text it came as
  instead of parsing and rewriting its coordinates, which ran Join and Complete out of RustGIS's
  instruction budget on the 25 MB communes layer.

## 0.3.0 (2026-10-22)

- The CUT tools, in the Tools pane under Plugins › IDE Chile and on the tab's CUT group: **Join
  Table by CUT** joins a CSV to communes, provinces or regions by their código único territorial
  or their name, however written (codes with or without the leading zero, other spellings, the
  codes of before 2007 and 2018), reading the CSV as Chile's services export it (semicolons,
  Windows-1252, decimal commas) and listing the rows that joined nothing with the reason;
  **Assign Commune to Points** gives points the commune, province and region they fall in;
  **Complete CUT** adds the current code and official names to a layer with a code or name field.
  The division is the INE's Census 2024 one (345 communes, 56 provinces, 16 regions), read into
  `communes.json` by `refresh.py`.
- Needs RustGIS 0.3.0 or later, which brought `layer.addUrl` and the files tools read, and the
  `files` permission for the CSV.
- The plugin lives in its own repository, [DanielD-S/rustgis-ide-chile](https://github.com/DanielD-S/rustgis-ide-chile), and is released from it; its homepage points here.

## 0.2.0 (2026-10-19)

- The INE's Census 2024: the regions, provinces and communes of the political-administrative
  division the census was taken on, the indicators by commune and by region, and the
  neighbourhood units with their figures. 55 layers.

## 0.1.0 (2026-10-17)

- Public geospatial services of Chile as one-click layers: Geoportal de Chile, IDE MINAGRI,
  IDE MINVU and the INE's Census 2017. 49 layers, in a ribbon tab of their own, in English and
  Spanish.
