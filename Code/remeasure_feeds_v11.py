# Runs measure_feed_v2.py on every representative feed and writes data_files/feed_data_v2.csv.
import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd

from settings_v2 import *
from measure_feed_v2 import measure


def measure_one(job):
    feed_id, path = job
    t0 = time.time()
    try:
        m = measure(path)
    except Exception as e:
        m = {"fail_reason": type(e).__name__}
    return feed_id, m, round(time.time() - t0, 1)


def to_json(o):
    return o.item() if hasattr(o, "item") else str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--big-mb", type=float, default=100)
    a = ap.parse_args()

    pub = pd.read_csv(PUBLISHED, dtype=str)[["feed_id", "agency", "country"]]
    fail = pd.read_csv(PUBLISHED_FAILURES, dtype=str)[["feed_id", "agency", "country"]]
    reps = pd.concat([pub, fail], ignore_index=True)
    if a.ids:
        reps = reps[reps["feed_id"].isin(a.ids)]
    if a.limit:
        reps = reps.head(a.limit)
    reps["path"] = [os.path.join(FEEDS_DIR, f"{f}.zip") for f in reps["feed_id"]]
    missing = reps[~reps["path"].map(os.path.exists)]
    if len(missing):
        print(f"{len(missing)} feeds not found in {FEEDS_DIR}; run download_selected_v2.py first")
    reps = reps[reps["path"].map(os.path.exists)]

    full = not (a.ids or a.limit)
    tag = "" if full else "_test"
    progress = os.path.join(OUT_DIR, f"remeasure_progress_v2{tag}.jsonl")
    done = {}
    if os.path.exists(progress):
        with open(progress, encoding="utf8") as f:
            for line in f:
                r = json.loads(line)
                done[r["feed_id"]] = r
    todo = reps[~reps["feed_id"].isin(done)].copy()
    todo["mb"] = todo["path"].map(os.path.getsize) / 1e6
    big = todo[todo["mb"] > a.big_mb].sort_values("mb", ascending=False)
    small = todo[todo["mb"] <= a.big_mb]
    print(f"{len(done)} already done, {len(small)} small and {len(big)} large feeds to measure", flush=True)

    with open(progress, "a", encoding="utf8") as log:
        def save(feed_id, m, secs):
            done[feed_id] = {"feed_id": feed_id, "seconds": secs, "result": m}
            log.write(json.dumps(done[feed_id], default=to_json) + "\n")
            log.flush()
            if len(done) % 100 == 0:
                print(f"{len(done)} of {len(reps)} feeds measured", flush=True)

        for r in big.itertuples():
            save(*measure_one((r.feed_id, r.path)))
        jobs = list(zip(small["feed_id"], small["path"]))
        if a.workers > 1:
            with ProcessPoolExecutor(max_workers=a.workers) as ex:
                for fut in as_completed([ex.submit(measure_one, j) for j in jobs]):
                    save(*fut.result())
        else:
            for j in jobs:
                save(*measure_one(j))

    rows, fails = [], []
    for r in reps.itertuples():
        m = done[r.feed_id]["result"]
        base = {"feed_id": r.feed_id, "agency": r.agency, "country": r.country}
        if "fail_reason" in m:
            fails.append({**base, "fail_reason": m["fail_reason"]})
        else:
            rows.append({**base, **m})
    out = os.path.join(OUT_DIR, f"feed_data_v2{tag}.csv")
    pd.DataFrame(rows).to_csv(out, index=False)
    pd.DataFrame(fails).to_csv(os.path.join(OUT_DIR, f"feed_failures_v2{tag}.csv"), index=False)
    print(f"wrote {out}: {len(rows)} analysed feeds, {len(fails)} excluded")


if __name__ == "__main__":
    main()
