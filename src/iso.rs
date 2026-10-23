//! Layer Metadata (ISO 19115): an IDE Chile layer's metadata as a table of ISO 19115 elements.
//!
//! The records are in `metadata.rs`, which `generate.py` makes from `metadata.json`, which
//! `refresh.py` reads: a layer's record from the IDE Chile catalogue (the Geoportal de Chile's
//! CSW, ISO 19139) where it has one, matched by the service address its online resources name;
//! else the same ISO 19115 elements from the layer's ArcGIS service (and its ArcGIS Online item),
//! which `MD_Metadata.metadataStandardName` says. They are read when the plugin is built, so the
//! tool works offline and in any RustGIS; the table's last rows say when, and where the live
//! record is.

use rustgis_plugin::{Map, Request, Value, geojson, json};

use crate::CATALOG;
use crate::cut::Output;
use crate::metadata::{ELEMENTS, READ, RECORDS};

/// One metadata record of a catalog layer.
#[derive(Clone, Copy, Debug)]
pub struct Record {
    /// The catalog entry's id.
    pub entry: &'static str,
    /// The service layer it describes, when the entry reads several and the catalogue describes
    /// each; `None` for the whole entry.
    pub sub: Option<u32>,
    /// `csw` (the IDE Chile catalogue) or `arcgis` (the layer's service).
    pub source: &'static str,
    /// (ISO 19115 element, value), in the order of the record; an element may repeat.
    pub elements: &'static [(&'static str, &'static str)],
}

/// The records of a catalog entry.
pub fn records(entry: &str) -> Vec<&'static Record> {
    RECORDS.iter().filter(|r| r.entry == entry).collect()
}

fn tr(req: &Request, s: &str, args: &[(&str, &str)]) -> String {
    req.tr(crate::MANIFEST, s, args)
}

/// Runs the tool: the table of the chosen layer's records.
pub fn run(req: &Request) -> Result<Output, String> {
    let chosen = req.str("layer").map(str::trim).unwrap_or_default();
    let Some(entry) = CATALOG.iter().find(|e| e.name == chosen || e.id == chosen) else {
        return Err(tr(req, "IDE Chile has no layer '{name}'.", &[("name", chosen)]));
    };
    let recs = records(entry.id);
    if recs.is_empty() {
        return Err(tr(req, "{name} has no metadata.", &[("name", entry.name)]));
    }
    let (col_record, col_element, col_description, col_value) =
        (tr(req, "Record", &[]), tr(req, "ISO 19115 element", &[]), tr(req, "Description", &[]), tr(req, "Value", &[]));
    let descriptions: Vec<(&str, String)> = ELEMENTS.iter().map(|(p, en)| (*p, tr(req, en, &[]))).collect();
    let mut rows = Vec::new();
    for r in &recs {
        let title = r.elements.iter().find(|(p, _)| *p == "CI_Citation.title").map(|(_, v)| *v).unwrap_or(entry.name);
        // The elements in the table's order (ELEMENTS), each value in the record's order.
        for (path, description) in &descriptions {
            for (_, value) in r.elements.iter().filter(|(p, _)| p == path) {
                let mut props = Map::new();
                props.insert(col_record.clone(), json!(title));
                props.insert(col_element.clone(), json!(path));
                props.insert(col_description.clone(), json!(description));
                props.insert(col_value.clone(), json!(value));
                rows.push(geojson::feature(Value::Null, Value::Object(props)));
            }
        }
    }
    let csw = recs.iter().filter(|r| r.source == "csw").count();
    let source = if csw == 0 {
        tr(
            req,
            "{name}: the IDE Chile catalogue has no record of this layer; its ISO 19115 elements come from its ArcGIS service.",
            &[("name", entry.name)],
        )
    } else if recs.len() == 1 {
        tr(req, "{name}: the record of the IDE Chile catalogue (CSW).", &[("name", entry.name)])
    } else {
        tr(req, "{name}: {n} records from the IDE Chile catalogue (CSW).", &[("name", entry.name), ("n", &csw.to_string())])
    };
    Ok(Output::new().table(&tr(req, "Metadata of {name}", &[("name", entry.name)]), geojson::collection(rows)).message(source).message(tr(
        req,
        "Metadata read on {date}; the live record may be newer.",
        &[("date", READ)],
    )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use rustgis_plugin::{Kind, serde_json};

    #[test]
    fn every_layer_has_its_metadata() {
        for e in CATALOG {
            let recs = records(e.id);
            assert!(!recs.is_empty(), "{} has no metadata", e.id);
            for r in &recs {
                assert!(r.source == "csw" || r.source == "arcgis", "{}: {}", e.id, r.source);
                if let Some(sub) = r.sub {
                    assert!(e.subs.iter().any(|s| s.id == sub), "{}: no layer {sub}", e.id);
                }
                for (path, value) in r.elements {
                    assert!(ELEMENTS.iter().any(|(p, _)| p == path), "{}: {path}", e.id);
                    assert!(!value.trim().is_empty(), "{}: {path} is empty", e.id);
                }
                let has = |p: &str| r.elements.iter().any(|(q, _)| *q == p);
                assert!(
                    has("CI_Citation.title") && has("MD_Metadata.metadataStandardName") && has("CI_OnlineResource.linkage"),
                    "{}",
                    e.id
                );
                // A catalogue record says where it is.
                assert_eq!(r.source == "csw", has("CSW.GetRecordById"), "{}", e.id);
            }
        }
        // The Energy layer is described layer by layer; the agrological soils by their service.
        assert_eq!(records("energy").len(), 8);
        assert!(records("energy").iter().all(|r| r.source == "csw" && r.sub.is_some()));
        let soils = records("soils");
        assert_eq!(soils.len(), 1);
        assert_eq!(soils[0].source, "csw");
        assert!(soils[0].elements.iter().any(|(p, v)| *p == "MD_Resolution.equivalentScale" && *v == "1:10000"), "{:?}", soils[0].elements);
    }

    fn request(layer: &str, lang: &str) -> Request {
        Request {
            kind: Kind::Tool,
            id: "layer-metadata".into(),
            params: json!({ "layer": layer }),
            layers: Map::new(),
            files: Map::new(),
            lang: lang.into(),
            panel: Map::new(),
            panel_changed: Vec::new(),
        }
    }

    fn table(out: &Output) -> (String, Vec<Value>) {
        let v: Value = serde_json::from_str(&out.to_json()).unwrap();
        let t = &v["tables"][0];
        (t["name"].as_str().unwrap().to_string(), t["geojson"]["features"].as_array().unwrap().clone())
    }

    #[test]
    fn the_tool_makes_a_table_of_iso_elements() {
        // By the layer's name on the map (the choice), in Spanish.
        let out = run(&request("Suelos agrológicos (CIREN)", "es")).unwrap();
        let (name, rows) = table(&out);
        assert_eq!(name, "Metadatos de Suelos agrológicos (CIREN)");
        let first = &rows[0]["properties"];
        assert_eq!(first["Elemento ISO 19115"], "CI_Citation.title");
        assert_eq!(first["Descripción"], "Título");
        assert_eq!(first["Valor"], "Servicio Web de Mapas - Suelos Agrológicos");
        assert!(rows.iter().all(|r| r["geometry"].is_null()));
        assert!(rows.iter().any(|r| r["properties"]["Elemento ISO 19115"] == "LI_Lineage.statement"));
        assert!(out.messages[0].ends_with("el registro del catálogo de IDE Chile (CSW)."), "{:?}", out.messages);
        assert!(out.messages[1].starts_with("Metadatos leídos el 20"), "{:?}", out.messages);

        // By id, in English; a layer from its ArcGIS service.
        let out = run(&request("volcanoes", "en")).unwrap();
        let (name, rows) = table(&out);
        assert_eq!(name, "Metadata of Riesgo volcánico 2023 (SERNAGEOMIN)");
        assert_eq!(rows[0]["properties"]["ISO 19115 element"], "CI_Citation.title");
        assert!(out.messages[0].contains("has no record of this layer"), "{:?}", out.messages);

        // Energy: the records of its layers, each titled.
        let out = run(&request("energy", "es")).unwrap();
        let (_, rows) = table(&out);
        let titles: std::collections::BTreeSet<&str> = rows.iter().filter_map(|r| r["properties"]["Registro"].as_str()).collect();
        assert_eq!(titles.len(), 8, "{titles:?}");
        assert!(out.messages[0].contains("8 registros del catálogo"), "{:?}", out.messages);

        assert_eq!(run(&request("Narnia", "es")).unwrap_err(), "IDE Chile no tiene una capa 'Narnia'.");
    }
}
