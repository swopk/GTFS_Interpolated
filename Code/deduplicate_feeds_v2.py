# Keeps one representative feed per network from the full catalog download, as in screening.py.
import os
import re
import zipfile

import numpy as np
import pandas as pd

from settings_v2 import *


def norm_url(u):
    if not isinstance(u, str):
        return ""
    u = re.sub(r"^https?://", "", u.strip().lower())
    u = re.sub(r"^www\.", "", u)
    return u.split("?")[0].split("#")[0].rstrip("/")


def norm_name(n):
    if not isinstance(n, str):
        return ""
    n = re.sub(r"[^\w\s]+", " ", n.strip().lower(), flags=re.UNICODE)
    toks = [t for t in n.split() if t and t not in STOP_WORDS and len(t) > 1]
    return " ".join(sorted(toks)) or " ".join(n.split())


def km_between(lat1, lon1, lat2, lon2):
    if any(pd.isna(x) for x in [lat1, lon1, lat2, lon2]):
        return np.inf
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(min(a, 1.0)))


def fingerprint(path):
    out = {"agency_urls": set(), "agency_names": set(), "stops": set(),
           "n_stops": 0, "n_agencies": 0, "lat": np.nan, "lon": np.nan}
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            hit = [n for n in names if n.split("/")[-1] == "agency.txt"]
            if hit:
                with z.open(hit[0]) as fh:
                    a = pd.read_csv(fh, dtype=str, low_memory=False, encoding="utf-8-sig")
                a.columns = [c.strip().lstrip("﻿") for c in a.columns]
                out["n_agencies"] = int(len(a))
                if "agency_url" in a.columns:
                    out["agency_urls"] = {norm_url(u) for u in a["agency_url"].dropna()} - {""}
                if "agency_name" in a.columns:
                    out["agency_names"] = {norm_name(n) for n in a["agency_name"].dropna()} - {""}
            hit = [n for n in names if n.split("/")[-1] == "stops.txt"]
            if hit:
                with z.open(hit[0]) as fh:
                    st = pd.read_csv(fh, dtype=str, low_memory=False, encoding="utf-8-sig")
                st.columns = [c.strip().lstrip("﻿") for c in st.columns]
                if "stop_id" in st.columns:
                    ids = st["stop_id"].dropna().astype(str)
                    out["stops"] = set(ids)
                    out["n_stops"] = int(len(ids))
                if {"stop_lat", "stop_lon"}.issubset(st.columns):
                    out["lat"] = pd.to_numeric(st["stop_lat"], errors="coerce").median()
                    out["lon"] = pd.to_numeric(st["stop_lon"], errors="coerce").median()
    except Exception:
        pass
    return out


class Clusters:
    def __init__(self, providers):
        self.parent = {}
        self.names = {}
        self.providers = providers

    def find(self, x):
        self.parent.setdefault(x, x)
        self.names.setdefault(x, {self.providers.get(x, "")})
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        merged = self.names[ra] | self.names[rb]
        if len({n for n in merged if n}) > MAX_PROVIDERS_PER_CLUSTER:
            return
        self.parent[rb] = ra
        self.names[ra] = merged


def deduplicate(man):
    man = man.copy()
    man["sha256"] = man.get("sha256", pd.Series("", index=man.index)).fillna("")
    man["_bytedupe"] = 0
    seen = {}
    for i, h in man["sha256"].items():
        if h and h in seen:
            man.at[i, "_bytedupe"] = 1
        elif h:
            seen[h] = i

    ids = [str(x) for x in man["feed_id"]]
    paths = dict(zip(ids, man["local_path"] if "local_path" in man.columns
                     else [os.path.join(FEEDS_DIR, f"{f}.zip") for f in ids]))
    providers = {str(r.feed_id): norm_name(getattr(r, "agency", "")) for r in man.itertuples()}
    fps = {i: fingerprint(paths[i]) for i in ids}

    url_providers = {}
    for i in ids:
        for u in fps[i]["agency_urls"]:
            url_providers.setdefault(u, set()).add(providers.get(i, ""))
    vendor_urls = {u for u, p in url_providers.items()
                   if len({x for x in p if x}) > MAX_PROVIDERS_PER_URL}

    cl = Clusters(providers)
    country = man.get("country", pd.Series("??", index=man.index)).fillna("??")
    man["_country"] = country
    for _, grp in man.groupby("_country"):
        gids = [str(x) for x in grp["feed_id"]]
        if len(gids) < 2:
            continue
        sid_providers = {}
        for i in gids:
            prov = providers.get(i, "")
            for sid in fps[i]["stops"]:
                sid_providers.setdefault(sid, set()).add(prov)
        generic = {sid for sid, p in sid_providers.items()
                   if len({x for x in p if x}) > MAX_PROVIDERS_PER_STOP_ID}
        distinctive = {i: (fps[i]["stops"] - generic) for i in gids}
        urls = {i: (fps[i]["agency_urls"] - vendor_urls) for i in gids}

        for a_i, a in enumerate(gids):
            fa = fps[a]
            for b in gids[a_i + 1:]:
                if cl.find(a) == cl.find(b):
                    continue
                fb = fps[b]
                if not (fa["n_agencies"] >= AGGREGATOR_MIN_AGENCIES
                        or fb["n_agencies"] >= AGGREGATOR_MIN_AGENCIES):
                    ua, ub = urls[a], urls[b]
                    if ua and ub:
                        inter = len(ua & ub)
                        uj = inter / (len(ua) + len(ub) - inter)
                        if uj >= URL_JACCARD_THRESHOLD:
                            cl.union(a, b)
                            continue
                sa, sb = distinctive[a], distinctive[b]
                if len(sa) >= MIN_STOPS_FOR_OVERLAP and len(sb) >= MIN_STOPS_FOR_OVERLAP:
                    shared = len(sa & sb)
                    if shared >= MIN_SHARED_STOPS:
                        union_n = len(sa) + len(sb) - shared
                        if union_n and shared / union_n >= STOP_JACCARD_THRESHOLD:
                            cl.union(a, b)
                            continue
                if fa["agency_names"] & fb["agency_names"]:
                    if km_between(fa["lat"], fa["lon"], fb["lat"], fb["lon"]) <= NAME_PROXIMITY_KM:
                        cl.union(a, b)

    man["cluster"] = [cl.find(str(m)) for m in man["feed_id"]]
    man["_rank"] = man.get("status", pd.Series("", index=man.index)).fillna("").str.lower().map(STATUS_RANK).fillna(5)
    man["_stops"] = [fps[str(m)]["n_stops"] for m in man["feed_id"]]
    man["_bytes"] = pd.to_numeric(man.get("bytes", pd.Series(0, index=man.index)), errors="coerce").fillna(0)
    man = man.sort_values(["cluster", "_bytedupe", "_rank", "_stops", "_bytes", "feed_id"],
                          ascending=[True, True, True, False, False, True])
    man["is_representative"] = ~man.duplicated("cluster", keep="first")
    return man
