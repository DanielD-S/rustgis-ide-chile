"""Checks that every layer's service still answers what the plugin asks it.

    python scripts/check_services.py                    # the probes from `cargo run --example probes`
    python scripts/check_services.py --report out.md    # and a Markdown report of what failed

Each probe (see examples/probes.rs) is one of the plugin's own requests, cut to one feature: a
feature must come back as GeoJSON with its geometry, and a map image as an image. A server that
can't page (`resultRecordCount`) is asked for its first feature by id instead. A request that
fails is tried again twice, a while later, before it counts: the services are slow at times. A
server gets at most a few requests at once.

The requests go through curl, as refresh.py's do: it takes the Geoportal de Chile's certificate
chain, which RustGIS takes too and Python's SSL refuses on Windows.

Exits 1 when a probe fails. The weekly Services workflow turns the report into an issue, and
closes it when every service answers again.
"""

import argparse
import collections
import concurrent.futures
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
AGENT = "RustGIS IDE Chile plugin (services check; github.com/DanielD-S/rustgis-ide-chile)"
TIMEOUT = 90
WAITS = (10, 30)  # before the second and third tries
PER_HOST = 3
# An answer this big means the server ignored the one-feature limit: it serves the layer, which is
# what is checked, so the rest isn't read.
CAP = 5 * 1024 * 1024


def probes():
    env = dict(os.environ)
    if os.name == "nt":
        # The library names RustGIS's host imports, which a native Windows link can't resolve
        # (Linux leaves them out).
        env["RUSTFLAGS"] = (env.get("RUSTFLAGS", "") + " -C link-arg=/FORCE:UNRESOLVED").strip()
    out = subprocess.run(
        ["cargo", "run", "--quiet", "--locked", "--example", "probes"],
        cwd=ROOT, env=env, check=True, capture_output=True, text=True, encoding="utf-8",
    ).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip()]


_hosts = collections.defaultdict(lambda: threading.Semaphore(PER_HOST))
_lock = threading.Lock()


def host_gate(url):
    host = urllib.parse.urlsplit(url).hostname
    with _lock:
        return _hosts[host]


def fetch(url):
    """(HTTP status, content type, at most CAP + 1 bytes of the body); raises when there is no answer."""
    with host_gate(url), tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "body"
        r = subprocess.run(
            ["curl", "-sS", "-L", "--compressed", "--max-time", str(TIMEOUT), "-A", AGENT, "-o", str(out),
             "-w", "%{http_code} %{content_type}", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode:
            raise OSError(f"curl {r.returncode}: {r.stderr.strip()}")
        code, _, ctype = r.stdout.partition(" ")
        body = b""
        if out.exists():
            with open(out, "rb") as f:
                body = f.read(CAP + 1)
        return int(code or 0), ctype.strip(), body


def first_text(body, n=160):
    text = body[:4000].decode("utf-8", "replace")
    # A WFS exception or an HTML page: its words, not its markup.
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())[:n]


def judge(probe, status, ctype, body):
    """None when the answer is what the plugin needs, else what is wrong."""
    if status >= 400 and not body.lstrip().startswith(b"{"):
        return f"HTTP {status}: {first_text(body)}"
    if probe["kind"] == "map":
        if ctype.startswith("image/") and body:
            return None
        try:
            err = json.loads(body).get("error")
        except Exception:
            err = None
        if err:
            return f"map image: {err.get('message') or err}" if isinstance(err, dict) else f"map image: {err}"
        return f"map image: answered {ctype or 'no content type'}: {first_text(body)}"
    if len(body) > CAP:
        return None
    try:
        doc = json.loads(body)
    except Exception:
        return f"not GeoJSON: {first_text(body)}"
    if not isinstance(doc, dict):
        return "not GeoJSON: not an object"
    if doc.get("error"):
        err = doc["error"]
        return f"error {err.get('code', '')}: {err.get('message') or err}" if isinstance(err, dict) else f"error: {err}"
    feats = doc.get("features")
    if not isinstance(feats, list):
        return "not GeoJSON: no features list"
    if not feats:
        return "no features"
    if feats[0].get("geometry") is None:
        return "features come without geometry"
    return None


def by_id(url):
    """The probe's request for the layer's first feature by its id, for a server that can't page."""
    whole = url.replace("&resultRecordCount=1", "")
    _, _, body = fetch(whole.replace("f=geojson", "f=json") + "&returnIdsOnly=true")
    ids = json.loads(body).get("objectIds") or []
    return f"{whole}&objectIds={min(ids)}" if ids else None


def attempt(probe):
    """None, or what is wrong with the answer to the probe."""
    problem = judge(probe, *fetch(probe["url"]))
    if problem and "pagination is not supported" in problem.lower():
        url = by_id(probe["url"])
        if not url:
            return "no features"
        problem = judge(probe, *fetch(url))
    return problem


def check(probe):
    """(probe, None) or (probe, the last problem)."""
    problem = None
    for n in range(len(WAITS) + 1):
        if n:
            time.sleep(WAITS[n - 1])
        try:
            problem = attempt(probe)
        except Exception as e:  # unreachable, timed out, refused…
            problem = f"{type(e).__name__}: {e}"
        if problem is None:
            return probe, None
    return probe, problem


def cell(text):
    return text.replace("|", r"\|").replace("\n", " ")


def report(results, started):
    failed = [(p, why) for p, why in results if why]
    entries = {p["entry"] for p, _ in results}
    bad_entries = sorted({p["entry"] for p, _ in failed})
    lines = [
        f"**{len(results) - len(failed)} of {len(results)} requests answered**; "
        + (f"{len(bad_entries)} of {len(entries)} layers have a problem." if failed else f"all {len(entries)} layers answer."),
        "",
        f"Checked {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(started))} by `scripts/check_services.py`.",
    ]
    if failed:
        lines += ["", "| Command | Layer | Request | Problem |", "|---|---|---|---|"]
        for p, why in sorted(failed, key=lambda f: (f[0]["entry"], f[0]["kind"], f[0]["layer"])):
            lines.append(f"| `{p['entry']}` | {cell(p['name'])}: {cell(p['layer'])} | [{p['kind']}]({p['url']}) | {cell(why)} |")
        lines += [
            "",
            "A layer whose service moved needs its new address in `generate.py` (then "
            "`python refresh.py services <id>` and `python generate.py`); one whose service is gone "
            "leaves the table until there is another.",
        ]
    return "\n".join(lines) + "\n", failed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--probes", help="a file of probes (one JSON object a line) instead of running the example")
    ap.add_argument("--report", help="write the Markdown report here")
    ap.add_argument("--jobs", type=int, default=12)
    args = ap.parse_args()

    started = time.time()
    if args.probes:
        todo = [json.loads(l) for l in pathlib.Path(args.probes).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        todo = probes()
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(check, todo))
    text, failed = report(results, started)
    if args.report:
        pathlib.Path(args.report).write_text(text, encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text)
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    print(f"{time.time() - started:.0f} s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
