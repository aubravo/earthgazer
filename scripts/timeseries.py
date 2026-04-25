#!/usr/bin/env python3
"""
Local time series analysis script for EarthGazer processed imagery.

Reads processed NDVI and RGB GeoTIFFs from the features directory,
queries capture metadata from the Kubernetes-hosted PostgreSQL database,
and produces:

  timeseries/
  ├── rgb_timeseries.mp4          Time-lapse RGB video
  ├── ndvi_timeseries.mp4         Time-lapse NDVI video (RdYlGn colormap)
  ├── ndvi_timeseries_plot.png    Mean NDVI over time + rolling mean + Sen slope
  ├── ndvi_seasonal_profile.png   Monthly climatology + sinusoidal fit
  ├── ndvi_yearly_distribution.png Per-year violin distributions
  ├── ndvi_anomaly.png            Departure from monthly climatological baseline
  ├── ndvi_spatial_analysis.png   6-panel: slope, R², p-value, mean, std, CV maps
  ├── metadata.csv                Per-capture stats
  └── validation_metrics.json     All model validation metrics

Usage:
  python scripts/timeseries.py [OPTIONS]

Options:
  --data-dir PATH           Features directory
                            [default: /media/main_storage/earthgazer-data/features]
  --out-dir PATH            Output directory [default: timeseries]
  --cloud-max FLOAT         Max cloud cover % included in videos [default: 30]
  --fps INT                 Video frames per second [default: 4]
  --video-width INT         Video frame width in pixels [default: 1920]
  --map-width INT           Spatial map width in pixels [default: 640]
  --rolling-window INT      Window size for rolling mean [default: 6]
  --trend-min-samples INT   Min captures for pixel trend fit [default: 5]
  --db-host HOST            Postgres host [default: 127.0.0.1]
  --db-port INT             Local port for kubectl port-forward [default: 15432]
  --db-name NAME            Database name [default: earthgazer_dev]
  --db-user USER            Database user [default: earthgazer]
  --db-password PASS        Database password [default: devpassword]
  --db-pod POD              Kubernetes pod name [default: earthgazer-postgresql-0]
  --db-namespace NS         Kubernetes namespace [default: default]
  --no-portforward          Skip kubectl port-forward
  --skip-video              Skip video generation
  --skip-spatial            Skip spatial regression maps (expensive)
"""

import argparse
import csv
import json
import signal
import subprocess
import sys
import time
import warnings
from contextlib import contextmanager
from pathlib import Path

import cv2
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import psycopg2
import rasterio
from matplotlib.colors import Normalize, TwoSlopeNorm
from rasterio.enums import Resampling
from scipy import stats
from scipy.optimize import curve_fit

warnings.filterwarnings("ignore", category=RuntimeWarning)
plt.rcParams.update({"font.size": 10, "figure.dpi": 150})


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

@contextmanager
def postgres_connection(host, port, dbname, user, password,
                        pod, namespace, use_portforward=True):
    proc = None
    if use_portforward:
        print(f"[db] kubectl port-forward {pod} {port}:5432 ...")
        proc = subprocess.Popen(
            ["kubectl", "port-forward", "-n", namespace, pod, f"{port}:5432"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(2)

    conn = None
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        print(f"[db] Connected to {dbname}@{host}:{port}")
        yield conn
    finally:
        if conn:
            conn.close()
        if proc:
            proc.send_signal(signal.SIGTERM)
            proc.wait()
            print("[db] Port-forward closed")


def fetch_capture_metadata(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, sensing_time, cloud_cover, mission_id
            FROM earthgazer.capture_data
            WHERE backed_up = true
            ORDER BY sensing_time
        """)
        rows = cur.fetchall()
    return [
        {"id": r[0], "sensing_time": r[1], "cloud_cover": r[2] or 0.0,
         "mission_id": r[3]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_captures_with_imagery(data_dir: Path, captures: list) -> list:
    result = []
    for cap in captures:
        folder = data_dir / str(cap["id"])
        ndvi = folder / "ndvi.tif"
        rgb = folder / "rgb.tif"
        if ndvi.exists() and rgb.exists():
            result.append({**cap, "ndvi_path": ndvi, "rgb_path": rgb})
    result.sort(key=lambda x: x["sensing_time"])
    print(f"[discovery] {len(result)} captures with NDVI + RGB on disk")
    return result


def compute_ndvi_stats(captures: list) -> list:
    print(f"[stats] Computing per-capture mean NDVI and missing-data fraction ...")
    for i, cap in enumerate(captures):
        with rasterio.open(cap["ndvi_path"]) as src:
            ndvi = src.read(1).astype(np.float32)
        total = ndvi.size
        valid_mask = (ndvi > -1.0) & (ndvi < 1.0)
        valid = ndvi[valid_mask]
        cap["mean_ndvi"] = float(np.nanmean(valid)) if valid.size else float("nan")
        cap["missing_pct"] = 100.0 * (1.0 - valid_mask.sum() / total) if total else 100.0
        if (i + 1) % 50 == 0 or (i + 1) == len(captures):
            print(f"  {i + 1}/{len(captures)}")
    return captures


# ---------------------------------------------------------------------------
# Mann-Kendall + Sen's slope
# ---------------------------------------------------------------------------

def mann_kendall_test(y: np.ndarray) -> dict:
    """Non-parametric monotonic trend test."""
    n = len(y)
    s = int(np.sum([np.sign(y[j] - y[i]) for i in range(n - 1)
                    for j in range(i + 1, n)]))
    var_s = n * (n - 1) * (2 * n + 5) / 18
    z = (s - np.sign(s)) / np.sqrt(var_s) if s != 0 else 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    tau = s / (n * (n - 1) / 2)
    trend = "increasing" if tau > 0 else ("decreasing" if tau < 0 else "no trend")
    return {"S": s, "tau": round(tau, 4), "z": round(z, 4),
            "p_value": round(p, 6), "trend": trend}


def sens_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Theil-Sen median slope estimator."""
    slopes = [(y[j] - y[i]) / (x[j] - x[i])
              for i in range(len(x) - 1)
              for j in range(i + 1, len(x))
              if x[j] != x[i]]
    return float(np.median(slopes)) if slopes else 0.0


# ---------------------------------------------------------------------------
# Seasonal sinusoidal model
# ---------------------------------------------------------------------------

def _sinusoid(t, A, phi, C):
    return A * np.sin(2 * np.pi * t / 12 + phi) + C


def fit_seasonal_sinusoid(months: np.ndarray, means: np.ndarray) -> dict:
    """Fit A·sin(2π·t/12 + φ) + C to monthly means. Returns params + metrics."""
    A0 = max((means.max() - means.min()) / 2, 0.01)
    C0 = means.mean()
    try:
        popt, _ = curve_fit(_sinusoid, months, means,
                            p0=[A0, 0.0, C0],
                            bounds=([0, -np.pi, -1.0], [1.0, np.pi, 1.0]),
                            maxfev=5000)
        A, phi, C = popt
        fitted = _sinusoid(months, *popt)
        ss_res = float(np.sum((means - fitted) ** 2))
        ss_tot = float(np.sum((means - means.mean()) ** 2))
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
        rmse = float(np.sqrt(np.mean((means - fitted) ** 2)))
        # Peak month (1-based)
        t_fine = np.linspace(1, 12, 1000)
        peak_month = float(t_fine[np.argmax(_sinusoid(t_fine, A, phi, C))])
        return {"A": round(A, 4), "phi": round(phi, 4), "C": round(C, 4),
                "r2": round(r2, 4), "rmse": round(rmse, 6),
                "peak_month": round(peak_month, 1), "popt": popt.tolist()}
    except Exception as e:
        print(f"  [seasonal] Sinusoid fit failed: {e}")
        return {"r2": float("nan"), "rmse": float("nan"), "popt": None}


# ---------------------------------------------------------------------------
# Anomaly analysis
# ---------------------------------------------------------------------------

def compute_anomaly(captures: list) -> dict:
    """
    Subtract monthly climatological baseline from each capture's mean NDVI.
    Returns anomaly series + validation metrics.
    """
    from collections import defaultdict
    monthly = defaultdict(list)
    for c in captures:
        m = c["sensing_time"].month
        if not np.isnan(c["mean_ndvi"]):
            monthly[m].append(c["mean_ndvi"])

    clim = {m: float(np.mean(v)) for m, v in monthly.items()}

    anomalies = []
    for c in captures:
        m = c["sensing_time"].month
        anomaly = c["mean_ndvi"] - clim[m] if m in clim else float("nan")
        anomalies.append(anomaly)

    arr = np.array([a for a in anomalies if not np.isnan(a)])
    raw = np.array([c["mean_ndvi"] for c in captures
                    if not np.isnan(c["mean_ndvi"])])

    seasonal_component = np.array([clim.get(c["sensing_time"].month, np.nan)
                                   for c in captures])
    var_seasonal = float(np.nanvar(seasonal_component))
    var_total = float(np.nanvar(raw))
    explained_var = var_seasonal / var_total if var_total > 0 else float("nan")
    seasonal_rmse = float(np.sqrt(np.nanmean(
        (seasonal_component - float(np.nanmean(raw))) ** 2
    )))
    anomaly_rmse = float(np.sqrt(np.mean(arr ** 2))) if arr.size else float("nan")

    return {
        "anomalies": anomalies,
        "climatology": clim,
        "metrics": {
            "explained_variance_ratio": round(explained_var, 4),
            "seasonal_rmse": round(seasonal_rmse, 6),
            "anomaly_rmse": round(anomaly_rmse, 6),
        }
    }


# ---------------------------------------------------------------------------
# Spatial analysis
# ---------------------------------------------------------------------------

def load_ndvi_stack(captures: list, map_width: int) -> tuple[np.ndarray, np.ndarray]:
    """Load all NDVI rasters at reduced resolution. Returns (stack, frac_years)."""
    # Determine output height from native aspect ratio
    with rasterio.open(captures[0]["ndvi_path"]) as src:
        native_h, native_w = src.shape
    map_height = int(native_h * map_width / native_w)

    print(f"[spatial] Loading {len(captures)} NDVI rasters at {map_width}×{map_height} ...")
    stack = np.full((len(captures), map_height, map_width), np.nan, dtype=np.float32)

    for i, cap in enumerate(captures):
        with rasterio.open(cap["ndvi_path"]) as src:
            data = src.read(1, out_shape=(map_height, map_width),
                            resampling=Resampling.average).astype(np.float32)
        data[(data <= -1.0) | (data >= 1.0)] = np.nan
        stack[i] = data
        if (i + 1) % 50 == 0 or (i + 1) == len(captures):
            print(f"  {i + 1}/{len(captures)}")

    times = np.array([
        c["sensing_time"].year + (c["sensing_time"].timetuple().tm_yday - 1) / 365.25
        for c in captures
    ], dtype=np.float64)

    return stack, times


def compute_spatial_stats(stack: np.ndarray) -> dict:
    """Pixel-wise mean, std, and coefficient of variation."""
    mean_map = np.nanmean(stack, axis=0)
    std_map = np.nanstd(stack, axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        cv_map = np.where(np.abs(mean_map) > 1e-6, std_map / np.abs(mean_map), np.nan)
    return {"mean": mean_map, "std": std_map, "cv": cv_map}


def compute_pixel_regression(stack: np.ndarray, times: np.ndarray,
                              min_samples: int) -> dict:
    """
    Pixel-wise OLS linear regression of NDVI vs fractional year.
    Processed in row strips to control memory usage.
    Returns slope, R², p-value maps with validation metrics.
    """
    N, H, W = stack.shape
    X = times - times.mean()  # centred fractional years

    slope_map = np.full((H, W), np.nan, dtype=np.float32)
    r2_map = np.full((H, W), np.nan, dtype=np.float32)
    pval_map = np.full((H, W), np.nan, dtype=np.float32)

    strip_size = 40
    print(f"[spatial] Pixel-wise regression ({H}×{W}) ...")

    for r0 in range(0, H, strip_size):
        r1 = min(r0 + strip_size, H)
        strip = stack[:, r0:r1, :]             # (N, sh, W)
        valid = ~np.isnan(strip)               # (N, sh, W)
        nv = valid.sum(axis=0).astype(np.float32)  # (sh, W)
        enough = nv >= min_samples

        y = np.where(valid, strip, 0.0)

        # Regression components
        XY = (X[:, None, None] * y).sum(axis=0)
        SS_xx = ((X ** 2)[:, None, None] * valid).sum(axis=0)
        Y_sum = y.sum(axis=0)

        with np.errstate(invalid="ignore", divide="ignore"):
            s = np.where(enough & (SS_xx > 0), XY / SS_xx, np.nan)
            Y_mean = np.where(nv > 0, Y_sum / nv, np.nan)

        Y_pred = s[None] * X[:, None, None] + Y_mean[None]
        resid = np.where(valid, strip - Y_pred, 0.0)
        SSE = (resid ** 2).sum(axis=0)
        dev = np.where(valid, strip - Y_mean[None], 0.0)
        SS_tot = (dev ** 2).sum(axis=0)

        with np.errstate(invalid="ignore", divide="ignore"):
            r2 = np.where(enough & (SS_tot > 0), 1.0 - SSE / SS_tot, np.nan)
            df = nv - 2
            MSE = np.where(df > 0, SSE / df, np.nan)
            SE_s = np.where(SS_xx > 0, np.sqrt(MSE / SS_xx), np.nan)
            t_stat = np.where(SE_s > 0, s / SE_s, np.nan)

        pval = np.full_like(t_stat, np.nan)
        ok = ~np.isnan(t_stat) & enough
        if ok.any():
            pval[ok] = 2.0 * stats.t.sf(np.abs(t_stat[ok]), df=df[ok])

        slope_map[r0:r1] = s
        r2_map[r0:r1] = r2
        pval_map[r0:r1] = pval

        if r0 % (strip_size * 5) == 0:
            print(f"  row {r0}/{H}")

    valid_slope = slope_map[~np.isnan(slope_map)]
    sig_mask = (~np.isnan(pval_map)) & (pval_map < 0.05)
    metrics = {
        "mean_r2": round(float(np.nanmean(r2_map)), 4),
        "median_r2": round(float(np.nanmedian(r2_map)), 4),
        "pct_significant_pixels_alpha05": round(
            100.0 * sig_mask.sum() / (~np.isnan(pval_map)).sum(), 2
        ) if (~np.isnan(pval_map)).sum() > 0 else float("nan"),
        "mean_slope_per_year": round(float(np.nanmean(valid_slope)), 6),
        "median_slope_per_year": round(float(np.nanmedian(valid_slope)), 6),
    }
    return {"slope": slope_map, "r2": r2_map, "pvalue": pval_map, "metrics": metrics}


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def _frac_year(captures):
    return np.array([
        c["sensing_time"].year + (c["sensing_time"].timetuple().tm_yday - 1) / 365.25
        for c in captures
    ])


def plot_timeseries(captures: list, out_path: Path, rolling_window: int) -> dict:
    """Mean NDVI over time with rolling mean, Sen slope, Mann-Kendall metrics."""
    dates = [c["sensing_time"] for c in captures]
    ndvi = np.array([c["mean_ndvi"] for c in captures])
    fx = _frac_year(captures)

    # Rolling mean
    import pandas as pd
    series = pd.Series(ndvi)
    rolled = series.rolling(window=rolling_window, center=True, min_periods=2).mean()
    rolled_arr = rolled.values

    # Rolling mean validation
    mask = ~np.isnan(rolled_arr) & ~np.isnan(ndvi)
    mae_rolling = float(np.mean(np.abs(ndvi[mask] - rolled_arr[mask])))
    residual_std = float(np.std(ndvi[mask] - rolled_arr[mask]))

    # Mann-Kendall
    mk = mann_kendall_test(ndvi[~np.isnan(ndvi)])
    ss = sens_slope(fx[~np.isnan(ndvi)], ndvi[~np.isnan(ndvi)])

    # Sen slope line
    fx_valid = fx[~np.isnan(ndvi)]
    ndvi_valid = ndvi[~np.isnan(ndvi)]
    intercept = float(np.median(ndvi_valid) - ss * np.median(fx_valid))
    trend_y = ss * np.array([fx.min(), fx.max()]) + intercept

    fig, ax = plt.subplots(figsize=(15, 5))
    ax.scatter(dates, ndvi, s=18, color="steelblue", alpha=0.6, zorder=3, label="Mean NDVI")
    ax.plot(dates, ndvi, lw=0.8, color="steelblue", alpha=0.4)
    ax.plot(dates, rolled_arr, lw=2, color="darkorange",
            label=f"Rolling mean (w={rolling_window})", zorder=4)

    # Convert frac years back to approximate datetime for trend line
    import datetime
    def fy_to_date(fy):
        y = int(fy)
        d = (fy - y) * 365.25
        return datetime.datetime(y, 1, 1) + datetime.timedelta(days=d)

    trend_dates = [fy_to_date(fx.min()), fy_to_date(fx.max())]
    ax.plot(trend_dates, trend_y, "--", lw=1.8, color="crimson",
            label=f"Sen slope: {ss * 10:.4f}/decade", zorder=4)

    mk_text = (f"Mann-Kendall: τ={mk['tau']}, p={mk['p_value']:.4f} "
               f"({'*' if mk['p_value'] < 0.05 else 'ns'})  |  "
               f"Trend: {mk['trend']}  |  "
               f"Rolling MAE={mae_rolling:.4f}  σ_resid={residual_std:.4f}")
    ax.set_title(f"Mean NDVI Over Time  —  {mk_text}", fontsize=10)
    ax.set_ylabel("Mean NDVI")
    ax.set_ylim(-0.05, 0.85)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] Time series → {out_path}")

    return {
        "mann_kendall": mk,
        "sens_slope_per_year": round(ss, 6),
        "rolling_mean": {
            "window": rolling_window,
            "mae": round(mae_rolling, 6),
            "residual_std": round(residual_std, 6),
        }
    }


def plot_seasonal_profile(captures: list, out_path: Path) -> dict:
    """Monthly climatology + sinusoidal fit with R² and RMSE."""
    from collections import defaultdict
    monthly = defaultdict(list)
    for c in captures:
        m = c["sensing_time"].month
        if not np.isnan(c["mean_ndvi"]):
            monthly[m].append(c["mean_ndvi"])

    months_with_data = sorted(monthly.keys())
    means = np.array([np.mean(monthly[m]) for m in months_with_data])
    stds = np.array([np.std(monthly[m]) for m in months_with_data])
    month_arr = np.array(months_with_data, dtype=float)

    fit = fit_seasonal_sinusoid(month_arr, means)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(month_arr, means, color="seagreen", alpha=0.55,
           yerr=stds, capsize=3, label="Monthly mean ± std")

    if fit.get("popt") is not None:
        t_fine = np.linspace(1, 12, 300)
        ax.plot(t_fine, _sinusoid(t_fine, *fit["popt"]), "-",
                color="tomato", lw=2,
                label=(f"Sinusoidal fit  R²={fit['r2']:.3f}  "
                       f"RMSE={fit['rmse']:.4f}  "
                       f"Peak≈month {fit['peak_month']:.1f}"))

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)
    ax.set_ylabel("Mean NDVI")
    ax.set_title("Seasonal NDVI Profile")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35, axis="y")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] Seasonal profile → {out_path}")

    return {"sinusoidal_fit": {k: v for k, v in fit.items() if k != "popt"}}


def plot_yearly_distribution(captures: list, out_path: Path):
    """Per-year violin plots of mean NDVI."""
    from collections import defaultdict
    yearly = defaultdict(list)
    for c in captures:
        y = c["sensing_time"].year
        if not np.isnan(c["mean_ndvi"]):
            yearly[y].append(c["mean_ndvi"])

    years = sorted(k for k, v in yearly.items() if len(v) >= 2)
    data = [yearly[y] for y in years]

    fig, ax = plt.subplots(figsize=(max(10, len(years) * 0.8), 5))
    parts = ax.violinplot(data, positions=range(len(years)),
                          showmedians=True, showextrema=True)
    for pc in parts["bodies"]:
        pc.set_facecolor("steelblue")
        pc.set_alpha(0.6)

    ax.set_xticks(range(len(years)))
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right")
    ax.set_ylabel("Mean NDVI")
    ax.set_title("NDVI Distribution by Year")
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] Yearly distribution → {out_path}")


def plot_anomaly(captures: list, out_path: Path) -> dict:
    """Anomaly departure from monthly climatological baseline."""
    result = compute_anomaly(captures)
    anomalies = result["anomalies"]
    dates = [c["sensing_time"] for c in captures]
    m = result["metrics"]

    colors = ["seagreen" if a >= 0 else "tomato" for a in anomalies]

    fig, ax = plt.subplots(figsize=(15, 4))
    ax.bar(dates, anomalies, color=colors, alpha=0.75, width=20)
    ax.axhline(0, color="black", lw=1)

    metrics_text = (f"Explained variance (seasonal): {m['explained_variance_ratio']:.3f}  |  "
                    f"Seasonal RMSE: {m['seasonal_rmse']:.4f}  |  "
                    f"Anomaly RMSE: {m['anomaly_rmse']:.4f}")
    ax.set_title(f"NDVI Anomaly (departure from monthly climatology)  —  {metrics_text}",
                 fontsize=10)
    ax.set_ylabel("NDVI Anomaly")
    ax.grid(True, alpha=0.35, axis="y")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] Anomaly → {out_path}")

    return {"anomaly": m}


def plot_spatial_analysis(reg: dict, stats_maps: dict, times: np.ndarray,
                          out_path: Path) -> dict:
    """
    6-panel figure:
      Row 1: Trend slope (significance-masked) | R² | p-value
      Row 2: Mean NDVI | Std dev | CV
    """
    slope = reg["slope"]
    r2 = reg["r2"]
    pval = reg["pvalue"]
    mean_m = stats_maps["mean"]
    std_m = stats_maps["std"]
    cv_m = stats_maps["cv"]

    # Significance mask: grey out non-significant pixels on slope map
    slope_disp = slope.copy()
    insig = (~np.isnan(pval)) & (pval >= 0.05)
    slope_disp[insig] = np.nan

    year_min, year_max = int(times.min()), int(times.max())
    vabs = np.nanpercentile(np.abs(slope[~np.isnan(slope)]), 98) if (~np.isnan(slope)).any() else 0.01

    fig = plt.figure(figsize=(18, 10))
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.35, wspace=0.3)

    def ishow(ax, data, title, cmap, vmin=None, vmax=None, norm=None):
        im = ax.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax,
                       norm=norm, aspect="auto", interpolation="nearest")
        ax.set_title(title, fontsize=10)
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        return im

    ax0 = fig.add_subplot(gs[0, 0])
    norm_slope = TwoSlopeNorm(vmin=-vabs, vcenter=0, vmax=vabs)
    ishow(ax0, slope_disp,
          f"NDVI Trend (slope/yr)  {year_min}–{year_max}\n"
          f"[α<0.05 only, grey=not significant]",
          "RdYlGn", norm=norm_slope)

    ax1 = fig.add_subplot(gs[0, 1])
    ishow(ax1, r2, "R² (OLS fit quality)", "YlOrRd", vmin=0, vmax=1)

    ax2 = fig.add_subplot(gs[0, 2])
    # p-value: show log scale for readability
    with np.errstate(divide="ignore"):
        log_p = np.where(~np.isnan(pval) & (pval > 0), -np.log10(pval), np.nan)
    ishow(ax2, log_p, "−log₁₀(p-value)\n[darker = more significant]",
          "Blues", vmin=0, vmax=max(3.0, float(np.nanpercentile(log_p[~np.isnan(log_p)], 99))))

    ax3 = fig.add_subplot(gs[1, 0])
    ishow(ax3, mean_m, "Mean NDVI", "YlGn", vmin=0, vmax=0.8)

    ax4 = fig.add_subplot(gs[1, 1])
    ishow(ax4, std_m, "Std Dev NDVI", "Oranges", vmin=0)

    ax5 = fig.add_subplot(gs[1, 2])
    cv_clip = np.clip(cv_m, 0, np.nanpercentile(cv_m[~np.isnan(cv_m)], 98)) \
        if (~np.isnan(cv_m)).any() else cv_m
    ishow(ax5, cv_clip, "Coefficient of Variation (σ/μ)", "Purples", vmin=0)

    fig.suptitle(f"NDVI Spatial Analysis  |  {len(times)} captures  "
                 f"|  {year_min}–{year_max}", fontsize=13, y=0.98)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] Spatial analysis → {out_path}")

    return {"pixel_regression": reg["metrics"]}


# ---------------------------------------------------------------------------
# Video helpers
# ---------------------------------------------------------------------------

def _target_size(path: Path, width: int) -> tuple[int, int]:
    with rasterio.open(path) as src:
        h, w = src.shape
    new_h = int(h * width / w)
    # Ensure even dimensions (required by most video codecs)
    return (width if width % 2 == 0 else width + 1,
            new_h if new_h % 2 == 0 else new_h + 1)


def _add_overlay(frame: np.ndarray, cap: dict) -> np.ndarray:
    """Burn a date stamp in the bottom-left corner and a slim info line at top."""
    frame = frame.copy()
    h, w = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX

    # ── Bottom-left date stamp ───────────────────────────────────────────────
    date_str = cap["sensing_time"].strftime("%Y-%m-%d")
    date_scale = max(1.4, w / 1400)
    thickness = max(2, int(date_scale * 1.8))
    (tw, th), baseline = cv2.getTextSize(date_str, font, date_scale, thickness)
    pad = 14
    x0, y0 = pad, h - pad - baseline
    overlay = frame.copy()
    cv2.rectangle(overlay,
                  (x0 - 8, y0 - th - 6),
                  (x0 + tw + 8, y0 + baseline + 4),
                  (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
    cv2.putText(frame, date_str, (x0, y0),
                font, date_scale, (255, 255, 255), thickness, cv2.LINE_AA)

    # ── Top info strip (cloud %, mission, ID) ────────────────────────────────
    info = (f"Cloud: {cap['cloud_cover']:.1f}%  |  "
            f"{cap['mission_id']}  |  ID: {cap['id']}")
    info_scale = max(0.65, w / 3000)
    (iw, ih), ibase = cv2.getTextSize(info, font, info_scale, 1)
    bar_h = ih + ibase + 12
    overlay2 = frame.copy()
    cv2.rectangle(overlay2, (0, 0), (w, bar_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay2, 0.45, frame, 0.55, 0, frame)
    cv2.putText(frame, info, (10, ih + 6),
                font, info_scale, (210, 210, 210), 1, cv2.LINE_AA)

    return frame


def _load_rgb_frame(path: Path, tw: int, th: int) -> np.ndarray:
    with rasterio.open(path) as src:
        rgb = src.read()
    rgb = np.clip(rgb, 0.0, 1.0)
    frame = (np.transpose(rgb, (1, 2, 0)) * 255).astype(np.uint8)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    return cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)


def _load_ndvi_frame(path: Path, tw: int, th: int) -> np.ndarray:
    with rasterio.open(path) as src:
        ndvi = src.read(1).astype(np.float32)
    ndvi = np.clip(ndvi, -1.0, 1.0)
    norm = Normalize(vmin=-0.2, vmax=0.8)
    rgba = plt.colormaps["RdYlGn"](norm(ndvi))
    frame = (rgba[:, :, :3] * 255).astype(np.uint8)
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    frame = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_AREA)
    return _add_ndvi_colorbar(frame)


def _add_ndvi_colorbar(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    bar_w, label_w, pad = 50, 50, 8
    bar_h = h - 2 * pad

    gradient = np.linspace(0.8, -0.2, bar_h).reshape(-1, 1)
    norm = Normalize(vmin=-0.2, vmax=0.8)
    bar_rgb = (plt.colormaps["RdYlGn"](norm(gradient))[:, :, :3] * 255).astype(np.uint8)
    bar_bgr = cv2.cvtColor(np.repeat(bar_rgb, bar_w, axis=1), cv2.COLOR_RGB2BGR)

    bar_col = np.zeros((h, bar_w, 3), dtype=np.uint8)
    bar_col[pad:pad + bar_h] = bar_bgr

    label_col = np.zeros((h, label_w, 3), dtype=np.uint8)
    for val, frac in [(0.8, 0.0), (0.5, 0.375), (0.2, 0.75), (-0.2, 1.0)]:
        y = int(pad + frac * bar_h)
        cv2.putText(label_col, f"{val:.1f}", (2, min(y + 5, h - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (210, 210, 210), 1, cv2.LINE_AA)

    return np.hstack([frame, bar_col, label_col])


def write_video(captures: list, out_path: Path, kind: str,
                video_width: int, fps: int, cloud_max: float, missing_max: float):
    filtered = [
        c for c in captures
        if c["cloud_cover"] <= cloud_max and c.get("missing_pct", 0.0) <= missing_max
    ]
    excluded_cloud = sum(1 for c in captures if c["cloud_cover"] > cloud_max)
    excluded_miss = sum(
        1 for c in captures
        if c["cloud_cover"] <= cloud_max and c.get("missing_pct", 0.0) > missing_max
    )
    print(f"[video:{kind}] {len(filtered)}/{len(captures)} captures pass filters "
          f"(excluded {excluded_cloud} cloud>{cloud_max}%, {excluded_miss} missing>{missing_max}%)")
    if not filtered:
        print(f"  No frames — skipping")
        return

    # Pre-compute target frame size (add colorbar width for NDVI)
    tw, th = _target_size(filtered[0]["ndvi_path" if kind == "ndvi" else "rgb_path"],
                          video_width)
    if kind == "ndvi":
        tw += 100  # colorbar columns

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (tw, th))

    for i, cap in enumerate(filtered):
        if kind == "rgb":
            frame = _load_rgb_frame(cap["rgb_path"], tw, th)
        else:
            frame = _load_ndvi_frame(cap["ndvi_path"], tw - 100, th)
        frame = _add_overlay(frame, cap)
        writer.write(frame)
        if (i + 1) % 20 == 0 or (i + 1) == len(filtered):
            print(f"  {i + 1}/{len(filtered)} frames")

    writer.release()
    print(f"[video:{kind}] → {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir",
                   default="/media/main_storage/earthgazer-data/features")
    p.add_argument("--out-dir", default="timeseries")
    p.add_argument("--cloud-max", type=float, default=30.0)
    p.add_argument("--missing-max", type=float, default=10.0,
                   help="Max missing data %% per frame included in videos (default: 10)")
    p.add_argument("--fps", type=int, default=4)
    p.add_argument("--video-width", type=int, default=1920)
    p.add_argument("--map-width", type=int, default=640,
                   help="Pixel width for spatial analysis maps (default: 640)")
    p.add_argument("--rolling-window", type=int, default=6)
    p.add_argument("--trend-min-samples", type=int, default=5)
    p.add_argument("--db-host", default="127.0.0.1")
    p.add_argument("--db-port", type=int, default=15432)
    p.add_argument("--db-name", default="earthgazer_dev")
    p.add_argument("--db-user", default="earthgazer")
    p.add_argument("--db-password", default="devpassword")
    p.add_argument("--db-pod", default="earthgazer-postgresql-0")
    p.add_argument("--db-namespace", default="default")
    p.add_argument("--no-portforward", action="store_true")
    p.add_argument("--skip-video", action="store_true")
    p.add_argument("--skip-spatial", action="store_true",
                   help="Skip spatial regression (saves time/memory)")
    return p.parse_args()


def main():
    args = parse_args()
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Fetch DB metadata ────────────────────────────────────────────────
    with postgres_connection(
        host=args.db_host, port=args.db_port, dbname=args.db_name,
        user=args.db_user, password=args.db_password,
        pod=args.db_pod, namespace=args.db_namespace,
        use_portforward=not args.no_portforward,
    ) as conn:
        captures_db = fetch_capture_metadata(conn)
    print(f"[db] {len(captures_db)} backed-up capture records")

    # ── 2. Match to disk files ──────────────────────────────────────────────
    captures = find_captures_with_imagery(data_dir, captures_db)
    if not captures:
        print("ERROR: No captures with both ndvi.tif and rgb.tif. Exiting.")
        sys.exit(1)

    # ── 3. Per-capture NDVI mean ────────────────────────────────────────────
    captures = compute_ndvi_stats(captures)

    # ── 4. Metadata CSV ─────────────────────────────────────────────────────
    csv_path = out_dir / "metadata.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "sensing_time", "mission_id",
                                          "cloud_cover", "mean_ndvi"])
        w.writeheader()
        for c in captures:
            w.writerow({"id": c["id"],
                        "sensing_time": c["sensing_time"].isoformat(),
                        "mission_id": c["mission_id"],
                        "cloud_cover": c["cloud_cover"],
                        "mean_ndvi": f"{c['mean_ndvi']:.6f}"})
    print(f"[csv] → {csv_path}")

    # ── 5. Time series plots ─────────────────────────────────────────────────
    all_metrics = {}

    all_metrics["timeseries"] = plot_timeseries(
        captures, out_dir / "ndvi_timeseries_plot.png", args.rolling_window
    )
    all_metrics["seasonal"] = plot_seasonal_profile(
        captures, out_dir / "ndvi_seasonal_profile.png"
    )
    plot_yearly_distribution(captures, out_dir / "ndvi_yearly_distribution.png")
    all_metrics["anomaly"] = plot_anomaly(
        captures, out_dir / "ndvi_anomaly.png"
    )

    # ── 6. Spatial analysis ──────────────────────────────────────────────────
    if not args.skip_spatial:
        stack, times = load_ndvi_stack(captures, args.map_width)
        stats_maps = compute_spatial_stats(stack)
        reg = compute_pixel_regression(stack, times, args.trend_min_samples)
        all_metrics["spatial"] = plot_spatial_analysis(
            reg, stats_maps, times, out_dir / "ndvi_spatial_analysis.png"
        )
    else:
        print("[spatial] Skipped (--skip-spatial)")

    # ── 7. Save validation metrics ───────────────────────────────────────────
    metrics_path = out_dir / "validation_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(all_metrics, f, indent=2, default=str)
    print(f"[metrics] → {metrics_path}")

    # ── 8. Videos ────────────────────────────────────────────────────────────
    if not args.skip_video:
        write_video(captures, out_dir / "rgb_timeseries.mp4",
                    kind="rgb", video_width=args.video_width,
                    fps=args.fps, cloud_max=args.cloud_max,
                    missing_max=args.missing_max)
        write_video(captures, out_dir / "ndvi_timeseries.mp4",
                    kind="ndvi", video_width=args.video_width,
                    fps=args.fps, cloud_max=args.cloud_max,
                    missing_max=args.missing_max)
    else:
        print("[video] Skipped (--skip-video)")

    print(f"\n[done] All outputs in: {out_dir.resolve()}")


if __name__ == "__main__":
    main()
