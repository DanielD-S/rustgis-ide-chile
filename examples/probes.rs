//! The requests `scripts/check_services.py` sends to see that every layer's service still
//! answers, one JSON object a line, built with the plugin's own addresses (`arcgis_url`,
//! `wfs_url`, each entry's tile template) so the check asks what the plugin asks:
//!
//!     cargo run --quiet --example probes
//!
//! - `features`: one feature of each ArcGIS layer (`resultRecordCount=1`) or WFS feature type
//!   (`COUNT=1`), with the entry's filter, fields and generalisation: it must come as GeoJSON with
//!   its geometry.
//! - `map`: one 512-pixel map image over Santiago, for the entries that draw one.

use ide_chile::{CATALOG, arcgis_url, wfs_url};
use serde_json::json;

/// Santiago's centre, about 20 km across, in Web Mercator.
const SANTIAGO: &str = "-7875000,-3970000,-7855000,-3950000";

fn main() {
    for e in CATALOG {
        let mut probes = Vec::new();
        if e.kind == "wfs" {
            probes.push(("features", e.layer.to_string(), format!("{}&COUNT=1", wfs_url(e, None))));
        } else {
            for s in e.subs {
                probes.push(("features", s.name.to_string(), format!("{}&resultRecordCount=1", arcgis_url(e, s, None))));
            }
        }
        if !e.tiles.is_empty() {
            let url = e.tiles.replace("{bbox-epsg-3857}", SANTIAGO);
            probes.push(("map", "map image".to_string(), url));
        }
        for (kind, layer, url) in probes {
            println!("{}", json!({"entry": e.id, "name": e.name, "kind": kind, "layer": layer, "url": url}));
        }
    }
}
