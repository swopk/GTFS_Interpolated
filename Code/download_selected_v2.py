# Downloads the 3,082 representative feeds from their versioned URLs and checks each SHA-256 hash.
import os
import time
import hashlib
import zipfile

import argparse

import requests
import pandas as pd

from settings_v2 import DATA_DIR, FEEDS_DIR, PROVENANCE, MANIFEST
from settings_v2 import PUBLISHED as MEASUREMENTS, PUBLISHED_FAILURES as FAILURES
DOWNLOAD_TIMEOUT = 120
MAX_BYTES = 2_000_000_000
PAUSE = 0.5


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def valid_zip(path):
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        return any(n.endswith("stop_times.txt") for n in names)
    except Exception:
        return False


def fetch(url, dest):
    t0 = time.time()
    with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            total = 0
            for chunk in r.iter_content(1 << 20):
                total += len(chunk)
                if total > MAX_BYTES or time.time() - t0 > 300:
                    return False
                f.write(chunk)
    return valid_zip(dest)


def target_ids():
    ids = set(pd.read_csv(MEASUREMENTS, dtype=str)["feed_id"])
    if os.path.exists(FAILURES):
        ids |= set(pd.read_csv(FAILURES, dtype=str)["feed_id"])
    return ids


def run(ids=None, limit=None):
    os.makedirs(FEEDS_DIR, exist_ok=True)
    prov = pd.read_csv(PROVENANCE, dtype=str).fillna("")
    prov = prov[prov["feed_id"].isin(target_ids())]
    if ids:
        prov = prov[prov["feed_id"].isin(ids)]
    if limit:
        prov = prov.head(limit)

    rows = []
    for i, r in enumerate(prov.itertuples(index=False), 1):
        dest = os.path.join(FEEDS_DIR, f"{r.feed_id}.zip")
        if os.path.exists(dest) and valid_zip(dest) and (not r.sha256 or sha256(dest) == r.sha256):
            status = "cached"
        else:
            status = "failed"
            for url in [r.download_url, r.producer_url]:
                if not url:
                    continue
                try:
                    ok = fetch(url, dest)
                except Exception:
                    ok = False
                if ok and (not r.sha256 or sha256(dest) == r.sha256):
                    status = "downloaded"
                    break
        rows.append({"feed_id": r.feed_id, "agency": r.agency,
                     "country": r.country, "download_status": status,
                     "sha256": r.sha256})
        if i % 200 == 0:
            pd.DataFrame(rows).to_csv(MANIFEST, index=False)
        time.sleep(PAUSE)

    man = pd.DataFrame(rows)
    man.to_csv(MANIFEST, index=False)
    ready = int(man["download_status"].isin(["cached", "downloaded"]).sum())
    print(f"{ready} of {len(man)} representative feeds ready; wrote {MANIFEST}")
    return man


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    run(a.ids, a.limit)
