"""Builds the plugin and packages it as dist/<id>-<version>.rgplugin.

    rustup target add wasm32-unknown-unknown
    python scripts/package.py                 # build and package
    python scripts/package.py --tag v0.3.0    # also check the tag and write the registry entry

The package is reproducible, like the ones opengeos/rustgis-plugins builds: plugin.json, the
module and the README, in that order, with a fixed date. With --tag, the tag must be the
version in plugin.json and Cargo.toml, and dist/registry-entry.json is the file to submit to
opengeos/rustgis-plugins as registry/ide-chile.json once the release is published.
"""

import argparse
import hashlib
import io
import json
import pathlib
import subprocess
import sys
import tomllib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO = "DanielD-S/rustgis-ide-chile"
CATEGORIES = ["Data", "Basemaps"]
ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def package(manifest: bytes, wasm: bytes, readme: bytes) -> bytes:
    buf = io.BytesIO()
    entry = json.loads(manifest).get("entry", "plugin.wasm")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in (("plugin.json", manifest), (entry, wasm), ("README.md", readme)):
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", help="the release tag, vX.Y.Z")
    args = ap.parse_args()

    manifest = (ROOT / "plugin.json").read_bytes()
    m = json.loads(manifest)
    version = m["version"]
    crate = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["package"]
    if crate["version"] != version:
        print(f"Cargo.toml says {crate['version']}, plugin.json says {version}", file=sys.stderr)
        return 1
    if args.tag and args.tag != f"v{version}":
        print(f"the tag {args.tag} isn't v{version}, the version in plugin.json", file=sys.stderr)
        return 1

    subprocess.run(["cargo", "build", "--release", "--locked", "--target", "wasm32-unknown-unknown"], cwd=ROOT, check=True)
    wasm = (ROOT / "target/wasm32-unknown-unknown/release" / (crate["name"].replace("-", "_") + ".wasm")).read_bytes()
    data = package(manifest, wasm, (ROOT / "README.md").read_bytes())

    name = f"{m['id']}-{version}.rgplugin"
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / name).write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    (dist / (name + ".sha256")).write_text(f"{sha}  {name}\n", encoding="utf-8")
    print(f"{dist / name}  {len(data):,} bytes  sha256 {sha}")

    if args.tag:
        entry = {
            "id": m["id"],
            "source": {"url": f"https://github.com/{REPO}/releases/download/{args.tag}/{name}", "sha256": sha},
            "categories": CATEGORIES,
        }
        (dist / "registry-entry.json").write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
        print((dist / "registry-entry.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
