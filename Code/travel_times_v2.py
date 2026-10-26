# Inter-stop travel times and whole-minute shares (question i).
import numpy as np
import pandas as pd

from settings_v2 import *


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


def whole_minute_share(times):
    times = times.dropna()
    return float(np.mean(times % 60 == 0)) if len(times) else np.nan
