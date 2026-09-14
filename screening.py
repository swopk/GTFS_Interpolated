import os
import re
import zipfile

import numpy as np
import pandas as pd

MANIFEST = "data/manifest.csv"
PROVENANCE = "data/feed_metadata.csv"
FEEDS_DIR = "feeds"
OUT_DIR = "data"

BUS_TYPES = {"3", "11", "700", "702", "704", "705", "710", "711", "712", "713", "714", "715"}
CONTROL_TYPES = {"0", "1", "2", "900", "901", "400", "401", "402", "100", "101", "102"}
AM = (7 * 3600, 9 * 3600)
PM = (16 * 3600, 18 * 3600)
MIN_TRIPS_PER_CELL = 3
MIN_CONTROL_SEGMENTS = 20
MIN_BUS_TRIPS = 50
MIN_RUNTIMES = 20
MAX_RUNTIME = 3600
PREFERRED_WEEKDAYS = {1, 2, 3}
LINE_TOL_S = 1.5

STOP_JACCARD_THRESHOLD = 0.50
MIN_SHARED_STOPS = 25
MIN_STOPS_FOR_OVERLAP = 50
NAME_PROXIMITY_KM = 5.0
MAX_PROVIDERS_PER_URL = 3
MAX_PROVIDERS_PER_CLUSTER = 4
MAX_PROVIDERS_PER_STOP_ID = 3
URL_JACCARD_THRESHOLD = 0.50
AGGREGATOR_MIN_AGENCIES = 5
STATUS_RANK = {"active": 0, "valid": 0, "unspecified": 1, "": 1,
               "future": 2, "inactive": 3, "deprecated": 4}

STOP_WORDS = {"transit", "transportation", "authority", "district", "regional",
              "public", "bus", "buses", "metro", "metropolitan", "county", "city",
              "of", "the", "system", "services", "service", "agency", "department",
              "transportes", "transporte", "trafik", "verkehr", "mobilite",
              "mobilites", "reseau", "transports", "transport"}


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


def read_zip(path):
    tables = {}
    wanted = ["stop_times", "trips", "routes", "stops", "calendar", "calendar_dates", "agency"]
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        for w in wanted:
            m = [n for n in names if n.endswith(w + ".txt")]
            if m:
                with z.open(m[0]) as f:
                    tables[w] = pd.read_csv(f, dtype=str, low_memory=False, encoding="utf-8-sig")
    return tables


def to_seconds(s):
    s = s.astype("string").str.strip()
    p = s.str.split(":", expand=True)
    if p.shape[1] < 3:
        return pd.Series(np.nan, index=s.index)
    return (pd.to_numeric(p[0], errors="coerce") * 3600
            + pd.to_numeric(p[1], errors="coerce") * 60
            + pd.to_numeric(p[2], errors="coerce"))


def pick_service(tables, trips):
    active = {}
    if "calendar" in tables:
        cal = tables["calendar"]
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        if set(days + ["start_date", "end_date", "service_id"]).issubset(cal.columns):
            for _, r in cal.iterrows():
                try:
                    a = pd.to_datetime(r["start_date"], format="%Y%m%d")
                    b = pd.to_datetime(r["end_date"], format="%Y%m%d")
                except (ValueError, TypeError):
                    continue
                if pd.isna(a) or pd.isna(b) or b < a:
                    continue
                on = [i for i, d in enumerate(days) if str(r[d]).strip() == "1"]
                if not on:
                    continue
                end = min(b, a + pd.Timedelta(days=90))
                for day in pd.date_range(a, end, freq="D"):
                    if day.weekday() in on:
                        active.setdefault(day, set()).add(r["service_id"])
    if "calendar_dates" in tables:
        cd = tables["calendar_dates"]
        if {"date", "exception_type", "service_id"}.issubset(cd.columns):
            for _, r in cd.iterrows():
                try:
                    day = pd.to_datetime(r["date"], format="%Y%m%d")
                except (ValueError, TypeError):
                    continue
                if pd.isna(day):
                    continue
                if str(r["exception_type"]).strip() == "1":
                    active.setdefault(day, set()).add(r["service_id"])
                elif str(r["exception_type"]).strip() == "2" and day in active:
                    active[day].discard(r["service_id"])
    counts = trips.groupby("service_id").size()
    best, best_n = None, -1
    for day, sids in active.items():
        if day.weekday() not in PREFERRED_WEEKDAYS:
            continue
        n = int(counts.reindex(list(sids)).fillna(0).sum())
        if n > best_n:
            best, best_n = sids, n
    return best or set()


def mode_stop_times(tables, service_ids, types):
    trips = tables["trips"]
    trips = trips[trips["service_id"].isin(service_ids)].copy()
    if "direction_id" not in trips.columns:
        trips["direction_id"] = ""
    routes = tables["routes"][["route_id", "route_type"]].copy()
    routes["route_type"] = routes["route_type"].astype("string").str.strip()
    routes = routes[routes["route_type"].isin(types)]
    trips = trips.merge(routes, on="route_id", how="inner")
    if len(trips) == 0:
        return None
    st = tables["stop_times"]
    st = st[st["trip_id"].isin(set(trips["trip_id"]))].copy()
    if len(st) == 0:
        return None
    st["stop_sequence"] = pd.to_numeric(st["stop_sequence"], errors="coerce")
    st = st.dropna(subset=["stop_sequence"])
    st["dep_s"] = to_seconds(st["departure_time"])
    st["arr_s"] = to_seconds(st["arrival_time"])
    if "shape_dist_traveled" in st.columns:
        st["dist"] = pd.to_numeric(st["shape_dist_traveled"], errors="coerce")
    else:
        st["dist"] = np.nan
    if "timepoint" not in st.columns:
        st["timepoint"] = ""
    st["timepoint"] = st["timepoint"].astype("string").str.strip()
    st = st.sort_values(["trip_id", "stop_sequence"])
    st = st.merge(trips[["trip_id", "route_id", "direction_id", "route_type"]], on="trip_id", how="left")
    return st


def runtimes(st):
    nxt = st.groupby("trip_id").shift(-1)
    rt = nxt["arr_s"] - st["dep_s"]
    seg = pd.DataFrame({
        "route_id": st["route_id"], "direction_id": st["direction_id"],
        "from_stop_id": st["stop_id"], "to_stop_id": nxt["stop_id"],
        "dep_s": st["dep_s"], "rt": rt,
    })
    seg = seg.dropna(subset=["to_stop_id", "rt", "dep_s"])
    return seg[(seg["rt"] > 0) & (seg["rt"] <= MAX_RUNTIME)]


def grid_of(values):
    v = np.unique(values)
    if len(v) < 3:
        return np.nan
    d = np.diff(np.sort(v))
    d = d[d > 0]
    if len(d) == 0:
        return np.nan
    vals, counts = np.unique(d, return_counts=True)
    return float(vals[np.argmax(counts)])


def line_checks(st, basis):
    xcol = "dist" if basis == "distance" else "stop_sequence"
    approx_test = approx_hit = tp_test = tp_hit = 0
    for _, g in st.groupby("trip_id"):
        g = g.dropna(subset=["dep_s", xcol]).sort_values(xcol)
        if len(g) < 3:
            continue
        x = g[xcol].to_numpy(dtype=float)
        t = g["dep_s"].to_numpy(dtype=float)
        tp = g["timepoint"].fillna("").astype(str).to_numpy()
        anc = tp == "1"
        if anc.sum() < 2:
            continue
        xa, ta = x[anc], t[anc]
        order = np.argsort(xa)
        xa, ta = xa[order], ta[order]
        if len(np.unique(xa)) < 2:
            continue
        expected = np.interp(x, xa, ta)
        bracket = (x >= xa[0]) & (x <= xa[-1])

        am = (tp == "0") & bracket & (t % 60 != 0)
        approx_test += int(am.sum())
        approx_hit += int((np.abs(t[am] - expected[am]) <= LINE_TOL_S).sum())

        ai = np.where(anc)[0]
        for k in range(1, len(ai) - 1):
            j = ai[k]
            if x[j] <= x[ai[k - 1]] or x[j] >= x[ai[k + 1]] or t[j] % 60 == 0:
                continue
            frac = (x[j] - x[ai[k - 1]]) / (x[ai[k + 1]] - x[ai[k - 1]])
            exp = t[ai[k - 1]] + frac * (t[ai[k + 1]] - t[ai[k - 1]])
            tp_test += 1
            tp_hit += int(abs(t[j] - exp) <= LINE_TOL_S)
    return approx_test, approx_hit, tp_test, tp_hit


def peak_variation(seg):
    seg = seg.copy()
    seg["band"] = np.where((seg["dep_s"] >= AM[0]) & (seg["dep_s"] < AM[1]), "am",
                  np.where((seg["dep_s"] >= PM[0]) & (seg["dep_s"] < PM[1]), "pm", None))
    seg = seg[seg["band"].notna()]
    if len(seg) == 0:
        return np.nan, 0
    key = ["route_id", "direction_id", "from_stop_id", "to_stop_id"]
    cell = seg.groupby(key + ["band"])["rt"].agg(["mean", "size"]).reset_index()
    cell = cell[cell["size"] >= MIN_TRIPS_PER_CELL]
    wide = cell.pivot_table(index=key, columns="band", values="mean")
    if "am" not in wide or "pm" not in wide:
        return np.nan, 0
    wide = wide.dropna(subset=["am", "pm"])
    if len(wide) == 0:
        return np.nan, 0
    return float((wide["am"] - wide["pm"]).abs().mean()), int(len(wide))


def whole_minute_share(times):
    times = times.dropna()
    return float(np.mean(times % 60 == 0)) if len(times) else np.nan


def measure(path):
    tables = read_zip(path)
    if "stop_times" not in tables or "trips" not in tables or "routes" not in tables:
        return {"fail_reason": "missing required table"}
    services = pick_service(tables, tables["trips"])
    if not services:
        return {"fail_reason": "no usable service date"}

    bus = mode_stop_times(tables, services, BUS_TYPES)
    if bus is None or bus["trip_id"].nunique() < MIN_BUS_TRIPS:
        return {"fail_reason": "insufficient fixed-route bus service"}
    seg = runtimes(bus)
    if len(seg) < MIN_RUNTIMES:
        return {"fail_reason": "insufficient fixed-route bus service"}

    dep = bus["dep_s"].dropna()
    rt = seg["rt"].to_numpy()
    tp = bus["timepoint"]
    declared = {"0", "1"}.issubset(set(tp.dropna().unique()))
    basis = "distance" if bus["dist"].notna().mean() > 0.5 else "stopcount"

    row = {
        "n_bus_trips": int(bus["trip_id"].nunique()),
        "n_travel_times": int(len(seg)),
        "n_distinct_travel_times": int(len(np.unique(rt))),
        "median_travel_time_s": float(np.median(rt)),
        "temporal_resolution_s": grid_of(rt),
        "share_travel_times_whole_minute": float(np.mean(rt % 60 == 0)),
        "share_stop_times_whole_minute": whole_minute_share(dep),
        "timepoint_status": "declared" if declared else "not_declared",
        "approximate_share": float((tp == "0").mean()) if declared else np.nan,
        "share_timepoints_whole_minute": whole_minute_share(bus.loc[tp == "1", "dep_s"]) if declared else np.nan,
        "share_approx_whole_minute": whole_minute_share(bus.loc[tp == "0", "dep_s"]) if declared else np.nan,
        "interpolation_basis": basis if declared else "",
    }

    if declared:
        at, ah, tt, th = line_checks(bus, basis)
        row["n_approx_testable"] = at
        row["share_approx_on_line"] = float(ah / at) if at else np.nan
        row["n_timepoints_testable"] = tt
        row["share_timepoints_on_line"] = float(th / tt) if tt else np.nan
    else:
        row["n_approx_testable"] = 0
        row["share_approx_on_line"] = np.nan
        row["n_timepoints_testable"] = 0
        row["share_timepoints_on_line"] = np.nan

    bus_var, bus_n = peak_variation(seg)
    control_vars, n_control = [], 0
    ctrl = mode_stop_times(tables, services, CONTROL_TYPES)
    if ctrl is not None:
        for _, g in ctrl.groupby("route_type"):
            v, n = peak_variation(runtimes(g))
            if n >= MIN_CONTROL_SEGMENTS:
                control_vars.append(v)
                n_control += 1
    row["n_control_modes"] = n_control
    row["has_control_baseline"] = n_control > 0 and bus_n >= MIN_CONTROL_SEGMENTS
    row["bus_peak_to_peak_s"] = float(bus_var) if not np.isnan(bus_var) else np.nan
    row["segregated_peak_to_peak_s"] = float(max(control_vars)) if control_vars else np.nan
    if row["has_control_baseline"] and not np.isnan(bus_var):
        row["bus_exceeds_own_control"] = bool(bus_var > max(control_vars))
    else:
        row["bus_exceeds_own_control"] = np.nan
    return row


def run(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    src = MANIFEST if os.path.exists(MANIFEST) else PROVENANCE
    man = pd.read_csv(src, dtype=str)
    man = man.rename(columns={"mdb_id": "feed_id", "provider": "agency", "file_bytes": "bytes"})
    if "download_status" in man.columns:
        man = man[man["download_status"].isin(["cached", "downloaded"])]
    man = man.reset_index(drop=True)

    man = deduplicate(man)
    man[["feed_id", "cluster", "is_representative", "_bytedupe"]].rename(
        columns={"_bytedupe": "byte_identical_duplicate"}).to_csv(
        os.path.join(OUT_DIR, "representatives.csv"), index=False)

    reps = man[man["is_representative"]]
    if limit:
        reps = reps.head(limit)

    rows, fails = [], []
    for i, r in enumerate(reps.itertuples(), 1):
        path = getattr(r, "local_path", os.path.join(FEEDS_DIR, f"{r.feed_id}.zip"))
        base = {"feed_id": r.feed_id, "agency": getattr(r, "agency", ""),
                "country": getattr(r, "country", "")}
        try:
            m = measure(path)
        except Exception as e:
            m = {"fail_reason": type(e).__name__}
        if "fail_reason" in m:
            fails.append({**base, "fail_reason": m["fail_reason"]})
        else:
            rows.append({**base, **m})
        if i % 200 == 0:
            pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "feed_measurements.csv"), index=False)

    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(OUT_DIR, "feed_measurements.csv"), index=False)
    fail = pd.DataFrame(fails)
    fail.to_csv(os.path.join(OUT_DIR, "feed_failures.csv"), index=False)

    n_byte = int(man["_bytedupe"].sum())
    n_net = int((~man["is_representative"]).sum()) - n_byte
    steps = [("downloaded_feeds", len(man)),
             ("excluded_byte_identical", n_byte),
             ("excluded_same_network", n_net),
             ("representatives_processed", len(reps)),
             ("analysed_usable_bus", len(out)),
             ("excluded_no_usable_bus", len(fail))]
    if len(fail):
        for reason, n in fail["fail_reason"].value_counts().items():
            steps.append((f"excluded: {reason}", int(n)))
    pd.DataFrame(steps, columns=["stage", "n"]).to_csv(
        os.path.join(OUT_DIR, "attrition.csv"), index=False)
    return out


if __name__ == "__main__":
    run()
