# Measures one feed and returns its row of feed_data_v2.csv.
import numpy as np

from settings_v2 import *
from read_feed_v2 import read_zip, pick_service, mode_stop_times
from travel_times_v2 import runtimes, grid_of, whole_minute_share
from interpolation_test_v2 import line_checks
from peak_offpeak_v2 import peak_variation, peak_midday


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
    row["share_blank_stop_times"] = float(bus["dep_s"].isna().mean())
    pm_inc, pm_s, pm_n = peak_midday(seg)
    row["n_bus_peak_midday_segments"] = pm_n
    row["bus_peak_midday_increase"] = pm_inc
    row["bus_peak_midday_s"] = pm_s
    row["bus_am_midday_increase"] = peak_midday(seg, (AM,))[0]
    row["bus_pm_midday_increase"] = peak_midday(seg, (PM,))[0]
    ctrl_inc, ctrl_s = [], []
    if ctrl is not None:
        for _, g in ctrl.groupby("route_type"):
            inc, sec, n = peak_midday(runtimes(g))
            if n >= MIN_CONTROL_SEGMENTS:
                ctrl_inc.append(inc)
                ctrl_s.append(sec)
    row["n_control_modes_peak_midday"] = len(ctrl_inc)
    row["has_peak_midday_baseline"] = bool(ctrl_inc) and pm_n >= MIN_CONTROL_SEGMENTS
    k = int(np.argmax(ctrl_inc)) if ctrl_inc else None
    row["segregated_peak_midday_increase"] = ctrl_inc[k] if ctrl_inc else np.nan
    row["segregated_peak_midday_s"] = ctrl_s[k] if ctrl_inc else np.nan
    if row["has_peak_midday_baseline"]:
        row["bus_peak_midday_exceeds_control"] = bool(pm_inc > ctrl_inc[k])
    else:
        row["bus_peak_midday_exceeds_control"] = np.nan
    return row
