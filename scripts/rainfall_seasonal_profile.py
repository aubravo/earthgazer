#!/usr/bin/env python3
"""
Seasonal rainfall profile from a CONAGUA monthly statistics report.

Reads the "LLUVIA TOTAL MENSUAL" section of a text file (e.g. mes15007.txt),
computes per-month mean and standard deviation across all available years,
fits a sinusoidal climatological curve, and saves a bar-chart figure styled
after ndvi_seasonal_profile.png produced by scripts/timeseries.py.

Usage:
  python scripts/rainfall_seasonal_profile.py [OPTIONS]

Options:
  --input PATH    Path to the CONAGUA .txt report  [default: mes15007.txt]
  --out PATH      Output PNG path                  [default: timeseries/rainfall_seasonal_profile.png]
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

plt.rcParams.update({"font.size": 10, "figure.dpi": 150})

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

HEADER = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
          "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_lluvia_total_mensual(path: Path) -> dict[int, list[float]]:
    """
    Extract monthly total-rainfall values from a CONAGUA estadística mensual
    report.  Returns {month_number (1–12): [valid float values]}.
    """
    text = path.read_text(encoding="latin-1")
    lines = text.splitlines()

    # Locate the section header
    start = None
    for i, line in enumerate(lines):
        if "LLUVIA TOTAL MENSUAL" in line:
            start = i
            break
    if start is None:
        raise ValueError("Section 'LLUVIA TOTAL MENSUAL' not found in file.")

    # Verify the column header line (contains month abbreviations)
    header_line = lines[start + 1].strip()
    if "ENE" not in header_line or "DIC" not in header_line:
        raise ValueError(f"Expected header after section title, got: {header_line!r}")

    monthly: dict[int, list[float]] = {m: [] for m in range(1, 13)}

    skip_keywords = {"AÑO", "MÍNIMA", "MÁXIMA", "MEDIA", "DESV.ST", ""}

    for line in lines[start + 2:]:
        # Stop at the next section (blank line followed by a new section title)
        stripped = line.strip()
        if not stripped:
            continue
        first = stripped.split()[0] if stripped.split() else ""
        if first in skip_keywords:
            continue
        # Stop when a new ALL-CAPS section starts (e.g. EVAPORACIÓN …)
        if first.isupper() and not first.isdigit():
            break

        parts = stripped.split("\t")
        if len(parts) < 2:
            parts = stripped.split()
        if not parts:
            continue

        # First column is the year (4-digit integer)
        try:
            int(parts[0])
        except ValueError:
            continue

        # Columns 1-12 are monthly values; may be empty strings
        for col_idx in range(1, 13):
            if col_idx >= len(parts):
                continue
            cell = parts[col_idx].strip()
            if not cell:
                continue
            try:
                monthly[col_idx].append(float(cell))
            except ValueError:
                pass

    return monthly


# ---------------------------------------------------------------------------
# Sinusoidal fit (same model as timeseries.py)
# ---------------------------------------------------------------------------

def _sinusoid(t, A, phi, C):
    return A * np.sin(2 * np.pi * t / 12 + phi) + C


def fit_seasonal_sinusoid(months: np.ndarray, means: np.ndarray) -> dict:
    A0 = max((means.max() - means.min()) / 2, 0.01)
    C0 = means.mean()
    try:
        popt, _ = curve_fit(
            _sinusoid, months, means,
            p0=[A0, 0.0, C0],
            bounds=([0, -np.pi, 0], [means.max() * 2, np.pi, means.max() * 2]),
            maxfev=10000,
        )
        A, phi, C = popt
        fitted = _sinusoid(months, *popt)
        ss_res = float(np.sum((means - fitted) ** 2))
        ss_tot = float(np.sum((means - means.mean()) ** 2))
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
        rmse = float(np.sqrt(np.mean((means - fitted) ** 2)))
        t_fine = np.linspace(1, 12, 1000)
        peak_month = float(t_fine[np.argmax(_sinusoid(t_fine, A, phi, C))])
        return {"A": round(A, 2), "phi": round(phi, 4), "C": round(C, 2),
                "r2": round(r2, 4), "rmse": round(rmse, 4),
                "peak_month": round(peak_month, 1), "popt": popt.tolist()}
    except Exception as e:
        print(f"  [seasonal] Sinusoid fit failed: {e}")
        return {"r2": float("nan"), "rmse": float("nan"), "popt": None}


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def plot_rainfall_seasonal_profile(monthly: dict, out_path: Path,
                                   station_name: str = "") -> None:
    months_with_data = sorted(m for m, v in monthly.items() if len(v) >= 2)
    means = np.array([np.mean(monthly[m]) for m in months_with_data])
    stds = np.array([np.std(monthly[m], ddof=1) for m in months_with_data])
    counts = np.array([len(monthly[m]) for m in months_with_data])
    month_arr = np.array(months_with_data, dtype=float)

    fit = fit_seasonal_sinusoid(month_arr, means)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(month_arr, means, color="steelblue", alpha=0.55,
           yerr=stds, capsize=3, label="Monthly mean ± std")

    if fit.get("popt") is not None:
        t_fine = np.linspace(1, 12, 300)
        ax.plot(t_fine, _sinusoid(t_fine, *fit["popt"]), "-",
                color="tomato", lw=2,
                label=(f"Sinusoidal fit  R²={fit['r2']:.3f}  "
                       f"RMSE={fit['rmse']:.1f} mm  "
                       f"Peak≈month {fit['peak_month']:.1f}"))

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(MONTH_LABELS)
    ax.set_ylabel("Total Monthly Rainfall (mm)")
    title = "Seasonal Rainfall Profile"
    if station_name:
        title += f"  —  {station_name}"
    ax.set_title(title)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.35, axis="y")
    footnote = (f"n = {counts.min()}–{counts.max()} years per month  "
                f"({counts.min()} min, all months ≥ 80 % of {counts.max()} available years)")
    fig.text(0.5, -0.02, footnote, ha="center", fontsize=8, color="gray")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[plot] Seasonal rainfall profile → {out_path}")

    # Print summary
    print("\nMonthly summary (mm):")
    print(f"{'Month':<6} {'Mean':>8} {'Std':>8} {'N':>4}")
    for m, mean, std, n in zip(months_with_data, means, stds, counts):
        print(f"{MONTH_LABELS[m-1]:<6} {mean:>8.1f} {std:>8.1f} {n:>4}")
    if fit.get("popt"):
        print(f"\nSinusoidal fit: A={fit['A']} mm, peak≈month {fit['peak_month']}, "
              f"R²={fit['r2']}, RMSE={fit['rmse']} mm")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="mes15007.txt",
                   help="Path to the CONAGUA report text file")
    p.add_argument("--out", default="timeseries/rainfall_seasonal_profile.png",
                   help="Output PNG path")
    p.add_argument("--station", default="Amecameca de Juárez (15007)",
                   help="Station label for the plot title")
    return p.parse_args()


def main():
    args = parse_args()
    monthly = parse_lluvia_total_mensual(Path(args.input))
    plot_rainfall_seasonal_profile(monthly, Path(args.out), station_name=args.station)


if __name__ == "__main__":
    main()
