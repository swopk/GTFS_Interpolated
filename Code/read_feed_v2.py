# Reads a feed, picks the analyzed weekday and selects its bus or rail trips.
import zipfile

import numpy as np
import pandas as pd

from settings_v2 import *


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
