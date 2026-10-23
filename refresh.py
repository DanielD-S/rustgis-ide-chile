"""Reads what each ArcGIS service in the table offers and writes services.json for generate.py,
and the communes of the Census 2024 for communes.json.

    python refresh.py && python generate.py && cargo fmt
    python refresh.py communes                 # communes.json only
    python refresh.py services <id> [<id>…]    # these entries' services only, merged into services.json
    python refresh.py metadata                 # metadata.json only (ISO 19115, see below)

For every ArcGIS entry: the service's queryable layers (group layers can't be queried), each with
its name, geometry type and extent in Web Mercator (EPSG:3857), from which the plugin picks the
layers that reach the map view. An extent in another system is left out (the layer is then always
considered).

communes.json is the political-administrative division the INE took the Census 2024 on, from its
communes layer: each commune's CUT (código único territorial) with its name and its province's
and region's codes and names, as the INE spells them. The CUT tools (`src/cut.rs`) match codes
and names against it.
"""

import concurrent.futures
import importlib.util
import json
import math
import pathlib
import sys
import urllib.error
import urllib.request

root = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gen", root / "generate.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

R = 6378137.0


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RustGIS IDE Chile plugin"}), timeout=120) as r:
        return json.load(r)


def mercator(lon, lat):
    lat = max(min(lat, 85.05), -85.05)
    return math.radians(lon) * R, math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * R


def fetch(entry):
    base = entry["service"]
    try:
        meta = get(base + "?f=pjson")
    except Exception as ex:
        return entry["id"], {"service": base, "error": str(ex)}
    layers = []
    for layer in meta.get("layers", []):
        if layer.get("subLayerIds"):
            continue
        try:
            d = get(f"{base}/{layer['id']}?f=pjson")
            ext = d.get("extent") or {}
            sr = ext.get("spatialReference") or {}
            wkid = sr.get("latestWkid") or sr.get("wkid")
            bbox = None
            if ext.get("xmin") is not None:
                if wkid in (3857, 102100):
                    bbox = [ext["xmin"], ext["ymin"], ext["xmax"], ext["ymax"]]
                elif wkid == 4326:
                    x0, y0 = mercator(ext["xmin"], ext["ymin"])
                    x1, y1 = mercator(ext["xmax"], ext["ymax"])
                    bbox = [x0, y0, x1, y1]
            if bbox:
                bbox = [round(v) for v in bbox]
            layers.append({"id": layer["id"], "name": d.get("name") or layer["name"], "geometry": d.get("geometryType"), "bbox": bbox, "max": d.get("maxRecordCount")})
        except Exception as ex:
            layers.append({"id": layer["id"], "name": layer["name"], "error": str(ex)})
    return entry["id"], {"service": base, "layers": layers}


def communes():
    """Writes communes.json from the Census 2024 communes layer (the whole layer, no geometry)."""
    entry = next(e for e in gen.LAYERS if e["id"] == "census-2024-communes")
    (layer,) = entry["subs"]
    url = f"{entry['service']}/{layer[0]}/query?where=1%3D1&outFields=CUT,COD_REGION,REGION,COD_PROVINCIA,PROVINCIA,COMUNA&returnGeometry=false&f=json"
    d = get(url)
    assert not d.get("exceededTransferLimit"), "the communes didn't come whole"
    rows = []
    for f in d["features"]:
        a = f["attributes"]
        rows.append({k.lower(): a[k] for k in ("CUT", "COD_REGION", "REGION", "COD_PROVINCIA", "PROVINCIA", "COMUNA")})
    rows.sort(key=lambda r: r["cut"])
    assert len(rows) == len({r["cut"] for r in rows}), "duplicate CUT"
    assert all(1101 <= r["cut"] <= 16399 and r["cut"] // 1000 == r["cod_region"] and r["cut"] // 100 == r["cod_provincia"] for r in rows)
    out = {"source": entry["service"], "layer": layer[0], "credit": entry["credit"], "communes": rows}
    (root / "communes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"communes.json: {len(rows)} communes, {len({r['cod_provincia'] for r in rows})} provinces, {len({r['cod_region'] for r in rows})} regions")


# ---------------------------------------------------------------------------------------------
# Metadata (ISO 19115), for the Layer Metadata tool: metadata.json, which generate.py turns into
# src/metadata.rs. A layer's record comes from the Geoportal de Chile's catalogue (a CSW serving
# ISO 19139), matched by the service address its online resources name; a layer the catalogue
# has no record of gets the same ISO 19115 elements from its ArcGIS service (and, for an ArcGIS
# Online layer, its item), said so in MD_Metadata.metadataStandardName.

CSW = "https://geoportal.cl/csw"
GMD = "{http://www.isotc211.org/2005/gmd}"
NS = {"gmd": "http://www.isotc211.org/2005/gmd", "gco": "http://www.isotc211.org/2005/gco", "csw": "http://www.opengis.net/cat/csw/2.0.2"}
# The longest an element's text is kept (abstracts and constraints can run to pages).
MAX_TEXT = 1200


def get_bytes(url):
    """A document's bytes. The catalogue's certificate chain fails Python's check on some systems
    (curl's passes), so curl is the fallback."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RustGIS IDE Chile plugin"}), timeout=180) as r:
            return r.read()
    except urllib.error.URLError as ex:
        if "CERTIFICATE" not in str(ex).upper():
            raise
        import subprocess

        return subprocess.run(["curl", "-sS", "-f", "-m", "180", "-A", "RustGIS IDE Chile plugin", url], capture_output=True, check=True).stdout


def clean(text):
    """Text without HTML tags, entities or runs of spaces, cut to MAX_TEXT."""
    import html
    import re

    t = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= MAX_TEXT else t[: MAX_TEXT - 1].rstrip() + "…"


def norm_url(u):
    """An address to compare: decoded, lower case, without query, `/rest`, a trailing
    WMSServer/WFSServer or slash."""
    import re
    import urllib.parse

    u = urllib.parse.unquote(u).split("?")[0].lower().replace("/rest/services/", "/services/")
    u = re.sub(r"/(wmsserver|wfsserver|wms|wfs)$", "", u.rstrip("/"))
    return u.replace("http://", "https://")


def csw_records():
    """Every record of the catalogue, ISO 19139: (fileIdentifier, title, datestamp, links)."""
    import xml.etree.ElementTree as ET

    records, start = [], 1
    while True:
        url = (
            f"{CSW}?service=CSW&version=2.0.2&request=GetRecords&typeNames=csw:Record&resultType=results&elementSetName=full"
            f"&outputSchema=http://www.isotc211.org/2005/gmd&maxRecords=100&startPosition={start}"
        )
        root_el = ET.fromstring(get_bytes(url))
        for md in root_el.iter(GMD + "MD_Metadata"):
            ident = md.find("gmd:identificationInfo/*", NS)
            records.append({
                "id": text(md, "gmd:fileIdentifier/gco:CharacterString"),
                "title": text(ident, "gmd:citation/gmd:CI_Citation/gmd:title/gco:CharacterString"),
                "datestamp": text(md, "gmd:dateStamp/gco:DateTime") or text(md, "gmd:dateStamp/gco:Date"),
                "links": [text(o, "gmd:linkage/gmd:URL") for o in md.iter(GMD + "CI_OnlineResource")],
            })
        res = root_el.find("csw:SearchResults", NS)
        nxt = int(res.get("nextRecord", "0")) if res is not None else 0
        matched = int(res.get("numberOfRecordsMatched", "0")) if res is not None else 0
        if nxt == 0 or nxt > matched or nxt <= start:
            return records
        start = nxt


def text(el, path):
    if el is None:
        return ""
    x = el.find(path, NS)
    return (x.text or "").strip() if x is not None and x.text else ""


def iso_elements(record_id):
    """The ISO 19115 elements of a catalogue record (GetRecordById, ISO 19139), as [path, value]."""
    import urllib.parse
    import xml.etree.ElementTree as ET

    url = f"{CSW}?service=CSW&version=2.0.2&request=GetRecordById&elementSetName=full&outputSchema=http://www.isotc211.org/2005/gmd&id={urllib.parse.quote(record_id)}"
    md = next(ET.fromstring(get_bytes(url)).iter(GMD + "MD_Metadata"))
    ident = md.find("gmd:identificationInfo/*", NS)
    out = []

    def add(path, value):
        value = clean(value)
        if value and [path, value] not in out:
            out.append([path, value])

    add("MD_Metadata.fileIdentifier", text(md, "gmd:fileIdentifier/gco:CharacterString"))
    add("MD_Metadata.dateStamp", text(md, "gmd:dateStamp/gco:DateTime") or text(md, "gmd:dateStamp/gco:Date"))
    add("MD_Metadata.contact", text(md, "gmd:contact/gmd:CI_ResponsibleParty/gmd:organisationName/gco:CharacterString"))
    std = text(md, "gmd:metadataStandardName/gco:CharacterString")
    ver = text(md, "gmd:metadataStandardVersion/gco:CharacterString")
    add("MD_Metadata.metadataStandardName", f"{std} {ver}".strip() + " (catálogo IDE Chile)")
    add("CI_Citation.title", text(ident, "gmd:citation/gmd:CI_Citation/gmd:title/gco:CharacterString"))
    for d in ident.iterfind("gmd:citation/gmd:CI_Citation/gmd:date/gmd:CI_Date", NS) if ident is not None else []:
        kind = d.find("gmd:dateType/gmd:CI_DateTypeCode", NS)
        kind = kind.get("codeListValue") if kind is not None else ""
        if kind in ("creation", "publication", "revision"):
            add(f"CI_Citation.date.{kind}", text(d, "gmd:date/gco:Date") or text(d, "gmd:date/gco:DateTime"))
    add("MD_DataIdentification.abstract", text(ident, "gmd:abstract/gco:CharacterString"))
    for rp in ident.iterfind(".//gmd:pointOfContact/gmd:CI_ResponsibleParty", NS) if ident is not None else []:
        org = text(rp, "gmd:organisationName/gco:CharacterString")
        role = rp.find("gmd:role/gmd:CI_RoleCode", NS)
        role = role.get("codeListValue") if role is not None else ""
        add("MD_DataIdentification.pointOfContact", f"{org} ({role})" if role else org)
    for tc in ident.iterfind("gmd:topicCategory/gmd:MD_TopicCategoryCode", NS) if ident is not None else []:
        add("MD_DataIdentification.topicCategory", tc.text or "")
    add("MD_Resolution.equivalentScale", text(ident, ".//gmd:spatialResolution//gmd:denominator/gco:Integer") and "1:" + text(ident, ".//gmd:spatialResolution//gmd:denominator/gco:Integer"))
    add("MD_ReferenceSystem.referenceSystemIdentifier", text(md, ".//gmd:referenceSystemInfo//gmd:code/gco:CharacterString"))
    bb = ident.find(".//gmd:EX_GeographicBoundingBox", NS) if ident is not None else None
    if bb is not None:
        w, e, s, n = (text(bb, f"gmd:{k}/gco:Decimal") for k in ("westBoundLongitude", "eastBoundLongitude", "southBoundLatitude", "northBoundLatitude"))
        if all((w, e, s, n)):
            add("EX_GeographicBoundingBox", f"W {w}, E {e}, S {s}, N {n}")
    for c in ident.iterfind("gmd:resourceConstraints/*", NS) if ident is not None else []:
        for ul in c.iterfind("gmd:useLimitation/gco:CharacterString", NS):
            add("MD_Constraints.useLimitation", ul.text or "")
        for ac in c.iterfind("gmd:accessConstraints/gmd:MD_RestrictionCode", NS):
            add("MD_LegalConstraints.accessConstraints", ac.get("codeListValue") or ac.text or "")
        for oc in c.iterfind("gmd:otherConstraints/gco:CharacterString", NS):
            add("MD_LegalConstraints.otherConstraints", oc.text or "")
    add("LI_Lineage.statement", text(md, ".//gmd:dataQualityInfo//gmd:LI_Lineage/gmd:statement/gco:CharacterString"))
    for ol in list(md.iterfind(".//gmd:distributionInfo//gmd:CI_OnlineResource", NS))[:3]:
        add("CI_OnlineResource.linkage", text(ol, "gmd:linkage/gmd:URL"))
    add("CSW.GetRecordById", url)
    return out


def arcgis_elements(entry, sub):
    """The same ISO 19115 elements, from an ArcGIS service, its layer `sub` and, for an ArcGIS
    Online layer, its item."""
    import datetime

    def day(ms):
        return datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date().isoformat() if ms else ""

    base = entry["service"]
    service = get(base + "?f=json")
    layer = get(f"{base}/{sub}?f=json") if sub is not None else {}
    item = {}
    if service.get("serviceItemId"):
        try:
            item = get(f"https://www.arcgis.com/sharing/rest/content/items/{service['serviceItemId']}?f=json")
        except Exception:
            item = {}
    info = service.get("documentInfo") or {}
    out = []

    def add(path, value):
        value = clean(value)
        if value and [path, value] not in out:
            out.append([path, value])

    add("MD_Metadata.fileIdentifier", item.get("id") or f"{base}/{sub}" if sub is not None else base)
    add("MD_Metadata.dateStamp", day(item.get("modified")) or day((layer.get("editingInfo") or {}).get("lastEditDate")))
    add("MD_Metadata.contact", entry["credit"])
    add("MD_Metadata.metadataStandardName", "ISO 19115, elementos tomados del servicio ArcGIS REST (sin registro en el catálogo IDE Chile)")
    title = info.get("Title") if info.get("Title", "").strip().lower() not in ("", "map", "untitled") else ""
    add("CI_Citation.title", item.get("title") or (layer.get("name") if sub is not None else "") or title or entry["name"])
    add("CI_Citation.date.creation", day(item.get("created")))
    add("CI_Citation.date.revision", day((layer.get("editingInfo") or {}).get("lastEditDate")) or day(item.get("modified")))
    add("MD_DataIdentification.abstract", item.get("description") or item.get("snippet") or layer.get("description") or service.get("serviceDescription") or service.get("description") or info.get("Comments") or info.get("Subject"))
    add("MD_DataIdentification.pointOfContact", (item.get("accessInformation") or layer.get("copyrightText") or service.get("copyrightText") or info.get("Author") or entry["credit"]) + " (pointOfContact)")
    sr = (layer.get("extent") or service.get("fullExtent") or {}).get("spatialReference") or {}
    wkid = sr.get("latestWkid") or sr.get("wkid")
    if wkid:
        add("MD_ReferenceSystem.referenceSystemIdentifier", f"EPSG:{wkid}")
    ext = item.get("extent")
    if ext and len(ext) == 2:
        (w, s), (e, n) = ext
        add("EX_GeographicBoundingBox", f"W {w:.4f}, E {e:.4f}, S {s:.4f}, N {n:.4f}")
    add("MD_LegalConstraints.otherConstraints", item.get("licenseInfo"))
    add("CI_OnlineResource.linkage", f"{base}/{sub}" if sub is not None else base)
    if item.get("id"):
        add("CI_OnlineResource.linkage", f"https://www.arcgis.com/home/item.html?id={item['id']}")
    return out


def metadata():
    """Writes metadata.json: each catalog layer's ISO 19115 record(s)."""
    import datetime

    records = csw_records()
    print(f"catalogue: {len(records)} records")
    # Mirrors: the Ministry of Bienes Nacionales republishes other services' layers for its
    # emergency viewer ("[INFORMACIÓN BASE]", "(EMERGENCIA …)"), as its own records, and some name
    # the wrong service (its landslide record links the Energy service). The publisher's record,
    # or its ArcGIS item, describes a layer instead.
    records = [r for r in records if "[INFORMACI" not in r["title"].upper() and "(EMERGENCIA" not in r["title"].upper()]
    out = []
    for e in gen.LAYERS:
        found = {}  # sub (None for the whole entry) → record
        for r in records:
            for link in r["links"]:
                u = norm_url(link)
                if e["kind"] == "wfs":
                    ws = e["layer"].split(":")[0].lower()
                    hit = f"/geoserver/{ws}" in u and (u.endswith(f"/geoserver/{ws}") or f"/geoserver/{ws}/" in u)
                    sub = None
                else:
                    base = norm_url(e["service"])
                    rest = u[len(base):] if u.startswith(base) else None
                    hit = rest is not None and (rest == "" or rest.startswith("/"))
                    sub = int(rest[1:]) if hit and rest[1:].isdigit() else None
                    if sub is not None and sub not in {s[0] for s in e["subs"]}:
                        hit = False
                if not hit:
                    continue
                key = sub
                pick = gen.ISO_RECORDS.get(e["id"])
                better = key not in found or (
                    # A chosen record; else the publisher's own over a mirror ("[INFORMACIÓN BASE]"),
                    # else the newest.
                    (pick == r["id"])
                    or (found[key]["id"] != pick and ("[" in found[key]["title"]) > ("[" in r["title"]))
                    or (found[key]["id"] != pick and ("[" in found[key]["title"]) == ("[" in r["title"]) and r["datestamp"] > found[key]["datestamp"])
                )
                if better:
                    found[key] = r
                break
        # A layer read as one (a WFS type, an ArcGIS service of one layer): its layer's record is
        # the entry's.
        if len(e["subs"]) == 1 and e["subs"][0][0] in found and None not in found:
            found[None] = found.pop(e["subs"][0][0])
        # The record of the whole service, where there is one; else one per layer the catalogue
        # describes (Energy's power plants, substations and lines); else one from the service.
        per_layer = [k for k in found if k is not None]
        if per_layer and len(e["subs"]) > 1:
            plan = [(s[0], found.get(s[0])) for s in e["subs"]]
        elif None in found:
            plan = [(None, found[None])]
        elif e["kind"] == "arcgis":
            plan = [(e["subs"][0][0] if len(e["subs"]) == 1 else None, None)]
        else:
            plan = []
        for sub, r in plan:
            try:
                if r:
                    elements, source = iso_elements(r["id"]), "csw"
                else:
                    elements, source = arcgis_elements(e, sub), "arcgis"
            except Exception as ex:
                print(f"{e['id']} {sub}: {ex}")
                continue
            # The entry's own layer when it is read as one: its sub is the entry's.
            key = None if len(e["subs"]) <= 1 else sub
            out.append({"entry": e["id"], "sub": key, "source": source, "elements": elements})
            print(f"{e['id']:30} {str(key):>4} {source:6} {next((v for p, v in elements if p == 'CI_Citation.title'), '')[:60]}")
    doc = {"catalogue": CSW, "read": datetime.date.today().isoformat(), "records": out}
    (root / "metadata.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"metadata.json: {len(out)} records, {sum(r['source'] == 'csw' for r in out)} from the catalogue")


def refresh_services(ids):
    """Reads the services of the entries `ids` only, keeping the others as they are in services.json."""
    path = root / "services.json"
    known = json.loads(path.read_text(encoding="utf-8"))
    entries = [e for e in gen.LAYERS if e["kind"] == "arcgis" and e["id"] in ids]
    assert len(entries) == len(set(ids)), set(ids) - {e["id"] for e in entries}
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        for k, v in pool.map(fetch, entries):
            known[k] = v
            print(f"{k}: {v.get('error') or str(len(v['layers'])) + ' layers'}")
    path.write_text(json.dumps(known, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main():
    if sys.argv[1:] == ["communes"]:
        communes()
        return
    if sys.argv[1:2] == ["services"]:
        refresh_services(sys.argv[2:])
        return
    if sys.argv[1:] == ["metadata"]:
        metadata()
        return
    communes()
    entries = [e for e in gen.LAYERS if e["kind"] == "arcgis"]
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        services = dict(pool.map(fetch, entries))
    (root / "services.json").write_text(json.dumps(services, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in services.items():
        if "error" in v:
            print(f"{k}: {v['error']}")
        else:
            print(f"{k}: {len(v['layers'])} layers")
    metadata()


if __name__ == "__main__":
    main()
