# Peak-versus-midday comparison for bus and segregated modes (question iii).
import numpy as np
import pandas as pd

from settings_v2 import *


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


def peak_midday(seg, peaks=(AM, PM)):
    seg = seg.copy()
    seg["direction_id"] = seg["direction_id"].fillna("")
    t = seg["dep_s"].to_numpy()
    in_peak = np.zeros(len(seg), dtype=bool)
    for a, b in peaks:
        in_peak |= (t >= a) & (t < b)
    in_mid = (t >= MIDDAY[0]) & (t < MIDDAY[1])
    seg["band"] = np.where(in_peak, "peak", np.where(in_mid, "mid", None))
    seg = seg[seg["band"].notna()]
    if len(seg) == 0:
        return np.nan, np.nan, 0
    key = ["route_id", "direction_id", "from_stop_id", "to_stop_id"]
    cell = seg.groupby(key + ["band"])["rt"].agg(["mean", "size"]).reset_index()
    cell = cell[cell["size"] >= MIN_TRIPS_PER_CELL]
    wide = cell.pivot_table(index=key, columns="band", values="mean")
    if "peak" not in wide or "mid" not in wide:
        return np.nan, np.nan, 0
    wide = wide.dropna(subset=["peak", "mid"])
    if len(wide) == 0:
        return np.nan, np.nan, 0
    diff = wide["peak"] - wide["mid"]
    return float(diff.sum() / wide["mid"].sum()), float(diff.mean()), int(len(wide))
