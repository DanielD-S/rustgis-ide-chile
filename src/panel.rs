//! The catalogue panel: every layer in a tree of the tab's themes, under RustGIS's search box;
//! the chosen layer described, and added as features or as its map image.
//!
//! The tree's command (`catalogue`) is the panel's state command too. Opened, it gives the tree in
//! the request's language; a node chosen, only the text and the buttons, so the tree keeps its
//! open branches and its search.

use crate::{CATALOG, Entry, Item, MANIFEST, THEMES, Theme, read_limit, scale_text};
use rustgis_plugin::serde_json::{self, Map};
use rustgis_plugin::{Node, Panel, Request, Value};

/// The panel's widgets (plugin.json's `panel`, from generate.py).
pub const TREE: &str = "layer";
const INFO: &str = "info";
pub const ADD: &str = "catalogue-add";
pub const MAP: &str = "catalogue-map";

/// The manifest's strings in the request's language, read once for an answer (`Request::tr`
/// reads the manifest on every call, and a tree has a string for each of its nodes).
pub struct Words {
    table: Option<Map<String, Value>>,
}

impl Words {
    pub fn new(req: &Request) -> Words {
        let lang = req.lang.split(['-', '_']).next().unwrap_or("en").to_ascii_lowercase();
        let table = serde_json::from_str::<Value>(MANIFEST).ok().and_then(|m| m["i18n"][lang.as_str()].as_object().cloned());
        Words { table }
    }

    pub fn tr(&self, s: &str, args: &[(&str, &str)]) -> String {
        let mut out = self.table.as_ref().and_then(|t| t.get(s)).and_then(Value::as_str).unwrap_or(s).to_string();
        for (k, v) in args {
            out = out.replace(&format!("{{{k}}}"), v);
        }
        out
    }
}

/// The layer the buttons add: the `layer` parameter's (a script's), else the panel's chosen one.
/// A script can set the panel's value too, but RustGIS keeps a tree's value only among its
/// nodes, which the tree has once the panel has opened.
pub fn chosen(req: &Request, words: &Words) -> Result<&'static Entry, String> {
    req.str(TREE)
        .or_else(|| req.panel_str(TREE))
        .and_then(|id| CATALOG.iter().find(|e| e.id == id))
        .ok_or_else(|| words.tr("Choose a layer in the catalogue first.", &[]))
}

/// The panel's state: the tree when it opens, and what describes the chosen node.
pub fn state(req: &Request, words: &Words) -> Panel {
    let mut panel = Panel::new();
    if !req.changed(TREE) {
        panel = panel.nodes(TREE, THEMES.iter().map(|t| theme_node(t, words)));
    }
    let id = req.panel_str(TREE).unwrap_or("");
    let entry = CATALOG.iter().find(|e| e.id == id);
    let text = match (entry, find_layer(THEMES, id), find_theme(THEMES, id)) {
        (Some(e), Some((label, help)), _) => describe(req, words, e, label, help),
        (_, _, Some(t)) => words.tr(
            "{theme}: {n} layers. Choose one to read about it.",
            &[("theme", &words.tr(t.label, &[])), ("n", &layers_in(t).to_string())],
        ),
        _ => words.tr("Choose a layer, or search for one.", &[]),
    };
    panel.text(INFO, text).enabled(ADD, entry.is_some()).enabled(MAP, entry.is_some_and(|e| !e.tiles.is_empty()))
}

fn theme_node(t: &Theme, words: &Words) -> Node {
    Node::new(t.id, words.tr(t.label, &[])).count(layers_in(t) as u64).children(t.items.iter().map(|i| match i {
        Item::Layer { id, label, .. } => Node::new(*id, words.tr(label, &[])),
        Item::Theme(t) => theme_node(t, words),
    }))
}

/// How many layers a theme holds, in its own themes too.
pub fn layers_in(t: &Theme) -> usize {
    t.items.iter().map(|i| if let Item::Theme(t) = i { layers_in(t) } else { 1 }).sum()
}

/// A layer's label and help (its command's), by its id.
fn find_layer(themes: &'static [Theme], id: &str) -> Option<(&'static str, &'static str)> {
    themes.iter().find_map(|t| {
        t.items.iter().find_map(|i| match i {
            Item::Layer { id: i, label, help } if *i == id => Some((*label, *help)),
            Item::Theme(t) => find_layer(std::slice::from_ref(t), id),
            _ => None,
        })
    })
}

fn find_theme(themes: &'static [Theme], id: &str) -> Option<&'static Theme> {
    themes.iter().find_map(|t| {
        if t.id == id {
            return Some(t);
        }
        t.items.iter().find_map(|i| if let Item::Theme(t) = i { find_theme(std::slice::from_ref(t), id) } else { None })
    })
}

/// What the panel says of a layer: what it is, whose it is, and how it is read.
fn describe(req: &Request, words: &Words, e: &Entry, label: &str, help: &str) -> String {
    let mut lines = vec![
        words.tr(label, &[]),
        words.tr(help, &[]),
        words.tr("Dataset: {name}", &[("name", e.name)]),
        words.tr("Source: {credit}", &[("credit", e.credit)]),
    ];
    lines.push(if e.whole {
        words.tr("Read whole, in one download.", &[])
    } else {
        words.tr(
            "Read in the map view at 1:{scale} or closer, up to {n} features at a time.",
            &[("scale", &scale_text(e.max_scale, &req.lang)), ("n", &scale_text(f64::from(read_limit(e, e.name)), &req.lang))],
        )
    });
    if !e.tiles.is_empty() {
        lines.push(words.tr("It also has a map image.", &[]));
    }
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use rustgis_plugin::{Kind, json};
    use std::collections::HashSet;

    fn request(id: &str, lang: &str, values: Value, changed: &[&str]) -> Request {
        Request {
            kind: Kind::Command,
            id: id.to_string(),
            params: json!({}),
            layers: Default::default(),
            files: Default::default(),
            lang: lang.to_string(),
            panel: values.as_object().cloned().unwrap_or_default(),
            panel_changed: changed.iter().map(|s| s.to_string()).collect(),
        }
    }

    fn ids(themes: &[Theme], depth: usize, out: &mut Vec<(String, bool, usize)>) {
        for t in themes {
            out.push((t.id.to_string(), false, depth));
            for i in t.items {
                match i {
                    Item::Layer { id, .. } => out.push((id.to_string(), true, depth + 1)),
                    Item::Theme(t) => ids(std::slice::from_ref(t), depth + 1, out),
                }
            }
        }
    }

    #[test]
    fn every_layer_is_in_the_tree_once() {
        let mut nodes = Vec::new();
        ids(THEMES, 1, &mut nodes);
        let layers: Vec<&str> = nodes.iter().filter(|n| n.1).map(|n| n.0.as_str()).collect();
        let catalog: Vec<&str> = CATALOG.iter().map(|e| e.id).collect();
        assert_eq!(layers.len(), catalog.len());
        assert_eq!(layers.iter().collect::<HashSet<_>>(), catalog.iter().collect::<HashSet<_>>());
        // RustGIS keeps a tree's nodes when their ids are unique, and at most 5,000, 8 deep.
        assert_eq!(nodes.iter().map(|n| &n.0).collect::<HashSet<_>>().len(), nodes.len());
        assert!(nodes.len() <= 5000 && nodes.iter().all(|n| n.2 <= 8));
        assert_eq!(THEMES.iter().map(layers_in).sum::<usize>(), CATALOG.len());
    }

    #[test]
    fn the_panel_opens_on_the_tree() {
        let req = request("catalogue", "es", json!({}), &[]);
        let p: Value = state(&req, &Words::new(&req)).into();
        let nodes = p["items"][TREE]["nodes"].as_array().unwrap();
        assert_eq!(nodes.len(), THEMES.len());
        assert_eq!(nodes[0]["label"], "Límites");
        assert_eq!(nodes[0]["children"][0], json!({"id": "regions", "label": "Regiones"}));
        // Environment is one menu on the tab: the tree shows the menu.
        assert!(nodes.iter().any(|n| n["label"] == "Medio ambiente y riesgos"), "{nodes:?}");
        assert_eq!(p["items"][INFO]["text"], "Elija una capa, o búsquela.");
        assert_eq!((&p["items"][ADD]["enabled"], &p["items"][MAP]["enabled"]), (&json!(false), &json!(false)));
    }

    #[test]
    fn a_chosen_layer_is_described() {
        let req = request("catalogue", "es", json!({"layer": "soils"}), &["layer"]);
        let p: Value = state(&req, &Words::new(&req)).into();
        // A node chosen: the tree stays as it is.
        assert!(p["items"].get(TREE).is_none(), "{p}");
        let text = p["items"][INFO]["text"].as_str().unwrap();
        assert!(text.starts_with("Suelos agrológicos\n"), "{text}");
        assert!(text.contains("Fuente: IDE MINAGRI") && text.contains("1:2.000.000 o más cerca, hasta 2.000 entidades"), "{text}");
        assert!(text.ends_with("También tiene imagen de mapa."), "{text}");
        assert_eq!((&p["items"][ADD]["enabled"], &p["items"][MAP]["enabled"]), (&json!(true), &json!(true)));

        // A layer read whole, with no map image, in English.
        let req = request("catalogue", "en", json!({"layer": "census-2024-communes"}), &["layer"]);
        let p: Value = state(&req, &Words::new(&req)).into();
        let text = p["items"][INFO]["text"].as_str().unwrap();
        assert!(text.contains("Read whole, in one download.") && !text.contains("map image"), "{text}");
        assert_eq!(p["items"][MAP]["enabled"], json!(false));

        // A theme: how many layers it holds.
        let req = request("catalogue", "es", json!({"layer": "theme-soils-agriculture"}), &["layer"]);
        let p: Value = state(&req, &Words::new(&req)).into();
        assert_eq!(p["items"][INFO]["text"], "Suelos y agricultura: 9 capas. Elija una para leer sobre ella.");
        assert_eq!(p["items"][ADD]["enabled"], json!(false));
    }

    #[test]
    fn the_buttons_need_a_layer() {
        for values in [json!({}), json!({"layer": "theme-boundaries"}), json!({"layer": null})] {
            let req = request(ADD, "es", values, &[]);
            assert_eq!(chosen(&req, &Words::new(&req)).unwrap_err(), "Elija primero una capa en el catálogo.");
        }
        let req = request(MAP, "en", json!({"layer": "wetlands"}), &[]);
        assert_eq!(chosen(&req, &Words::new(&req)).unwrap().id, "wetlands");
        // A script's `layer` parameter comes before the panel's.
        let mut req = request(ADD, "en", json!({"layer": "wetlands"}), &[]);
        req.params = json!({"layer": "census-2024-regions"});
        assert_eq!(chosen(&req, &Words::new(&req)).unwrap().id, "census-2024-regions");
    }
}
