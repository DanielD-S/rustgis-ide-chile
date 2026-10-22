# Changelog

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
