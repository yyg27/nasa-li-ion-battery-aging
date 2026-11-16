"""Section 3.2 Data Preprocessing - NASA Li-ion Battery Aging Dataset (Kaggle: mantarain).

Loads charge/discharge/impedance/meta CSVs, cleans them, verifies the cycles_left label
and writes analysis-ready files to ./processed. Prints a cleaning log used in the report.

Requirements: pip install pandas numpy pyarrow
Usage: python preprocessing.py [data_dir]   (default: nasa-li-ion-battery-aging-datasets)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent  # paths work from any working directory (e.g. Colab)
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "nasa-li-ion-battery-aging-datasets"
OUT = HERE / "processed"
R_MAX = 10.0      # ohm; real Re/Rct/|Z| values are ~0.05-0.3 ohm, anything above is a fitting/sensor error
V_LOAD_MAX = 10.0  # V; load voltage never exceeds ~4.2 V, larger values are logging glitches
MIN_ROWS = 10      # discharge cycles with fewer samples were aborted
KEYS = ["battery_id", "cycle_id"]
log = []


def note(step, before, after):
    log.append((step, before, after, before - after))


def check(ok, msg):
    """Unlike assert, this is never skipped (python -O strips asserts)."""
    if not ok:
        raise SystemExit(f"check failed: {msg}")


def keep_cycles(meta, cycle_type, df):
    """Drop cycles of cycle_type from meta that no longer exist in df, so all outputs list the same cycles."""
    gone = (meta["cycle_type"] == cycle_type) & ~meta.set_index(KEYS).index.isin(df.set_index(KEYS).index)
    return meta[~gone]


def expected_cycles_left(df):
    """cycles_left = last DISCHARGE cycle_number of the battery - current cycle_number."""
    last = discharge_cn.groupby("battery_id")["cycle_number"].max()
    return df["battery_id"].map(last) - df["cycle_number"]


# ---------- meta ----------
meta = pd.read_csv(DATA / "meta.csv")
meta["start_time"] = pd.to_datetime(meta["start_time"], format="ISO8601")
n = len(meta)
meta = meta[meta["complete"]].drop(columns="complete")
note("meta: drop incomplete cycles (complete=False)", n, len(meta))
n = len(meta)
meta = meta[~((meta["cycle_type"] == "discharge") & (meta["capacity_ah"] <= 0))]
note("meta: drop discharge cycles with capacity <= 0 Ah", n, len(meta))
for c in ["est_electrolyte_res", "est_charge_trans_res"]:
    bad = (meta[c] <= 0) | (meta[c] > R_MAX)
    log.append((f"meta: set non-physical {c} to NaN", int(bad.sum()), None, None))
    meta.loc[bad, c] = np.nan

# ---------- discharge ----------
dis = pd.read_csv(DATA / "discharge.csv", engine="pyarrow")
discharge_cn = dis[["battery_id", "cycle_number"]]
n = len(dis)
dis = dis.merge(meta.loc[meta.cycle_type == "discharge", KEYS], on=KEYS)  # keep only valid cycles
note("discharge: drop rows of removed cycles", n, len(dis))
n = len(dis)
dis = dis[dis["voltage_load"] <= V_LOAD_MAX]
note(f"discharge: drop rows with voltage_load > {V_LOAD_MAX} V", n, len(dis))
n = len(dis)
dis = dis[dis.groupby(KEYS)["elapsed_seconds"].transform("size") >= MIN_ROWS]
note(f"discharge: drop cycles with < {MIN_ROWS} samples", n, len(dis))
n = len(meta)
meta = keep_cycles(meta, "discharge", dis)
note(f"meta: drop the discharge cycles removed above (< {MIN_ROWS} samples)", n, len(meta))

# ---------- charge ----------
ch = pd.read_csv(DATA / "charge.csv", engine="pyarrow")
n = len(ch)
ch = ch.dropna(subset=["voltage_measured", "current_measured", "temperature_measured"])
note("charge: drop rows with missing sensor values", n, len(ch))

# ---------- impedance ----------
imp = pd.read_csv(DATA / "impedance.csv")
n = len(imp)
imp = imp.merge(meta.loc[meta.cycle_type == "impedance", KEYS], on=KEYS)
note("impedance: drop rows of incomplete cycles", n, len(imp))
z = np.array([complex(s) for s in imp.pop("Battery_impedance")])
imp["z_real"], imp["z_imag"], imp["z_abs"] = z.real, z.imag, np.abs(z)
for c in ["sense_current", "battery_current", "Current_ratio"]:
    v = np.array([complex(s) for s in imp.pop(c)])
    imp[f"{c}_real"], imp[f"{c}_imag"] = v.real, v.imag
n = len(imp)
imp = imp[imp["z_abs"] <= R_MAX]
note(f"impedance: drop spectra points with |Z| > {R_MAX} ohm", n, len(imp))
n = len(meta)
meta = keep_cycles(meta, "impedance", imp)
note("meta: drop impedance cycles with no valid spectrum point left", n, len(meta))

# ---------- cycles_left check ----------
for name, df in [("discharge", dis), ("charge", ch)]:
    check((df["cycles_left"] == expected_cycles_left(df)).all(), f"cycles_left formula mismatch in {name}")
neg = int((ch["cycles_left"] < 0).sum())
log.append(("charge: rows with cycles_left = -1 (final charge after last discharge, kept)", neg, None, None))

# ---------- cycle-level table for visualization / ML ----------
agg = dis.groupby(KEYS).agg(
    cycle_number=("cycle_number", "first"),
    cycles_left=("cycles_left", "first"),
    duration_s=("elapsed_seconds", "max"),
    v_min=("voltage_measured", "min"),
    t_max=("temperature_measured", "max"),
).reset_index()
cycles = agg.merge(meta[KEYS + ["ambient_temperature", "start_time", "capacity_ah"]], on=KEYS)
cycles = cycles.sort_values(["battery_id", "cycle_number"]).reset_index(drop=True)
check(cycles["capacity_ah"].gt(0).all() and cycles["cycles_left"].ge(0).all(), "invalid capacity or cycles_left")
impedance_cycles = meta.loc[meta.cycle_type == "impedance",
                            KEYS + ["ambient_temperature", "start_time", "est_electrolyte_res", "est_charge_trans_res"]]
# every output must list the same cycles
check(len(cycles) == (meta.cycle_type == "discharge").sum() == dis.groupby(KEYS).ngroups, "discharge cycle counts differ")
check(len(impedance_cycles) == imp.groupby(KEYS).ngroups, "impedance cycle counts differ")

# ---------- save ----------
OUT.mkdir(exist_ok=True)
meta.to_csv(OUT / "meta_clean.csv", index=False)
cycles.to_csv(OUT / "discharge_cycles.csv", index=False)
impedance_cycles.to_csv(OUT / "impedance_cycles.csv", index=False)
dis.to_parquet(OUT / "discharge_clean.parquet", index=False)
ch.to_parquet(OUT / "charge_clean.parquet", index=False)
imp.to_parquet(OUT / "impedance_clean.parquet", index=False)

print(pd.DataFrame(log, columns=["step", "before", "after", "removed"]).to_string(index=False))
print(f"\nbatteries: {cycles.battery_id.nunique()}, valid discharge cycles: {len(cycles)}, "
      f"impedance cycles: {len(impedance_cycles)}, charge cycles: {ch.groupby(KEYS).ngroups}")
print(cycles.groupby("ambient_temperature").battery_id.nunique().rename("batteries per ambient T").to_string())
