# Straight-line test of stop times between timepoints (question ii).
import numpy as np

from settings_v2 import *


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
