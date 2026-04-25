# EarthGazer Time Series Analysis — Findings

**Study area:** Sentinel-2A captures stored in `earthgazer_dev`
**Period:** 2015–2026
**Total captures analysed:** 271 (with both NDVI and RGB processed imagery)
**Video frames included:** 171 captures passing cloud ≤ 30% and missing data ≤ 10% filters

---

## 1. Mann-Kendall Trend Test + Sen's Slope

Non-parametric test for monotonic trend in mean NDVI over time.
Sen's slope is the median of all pairwise slopes — robust to outliers and non-normality.

| Metric | Value |
|---|---|
| Kendall's τ | −0.211 |
| S statistic | −7,643 |
| z-score | −5.15 |
| p-value | ~0 |
| Trend direction | **Decreasing** |
| Sen's slope | −0.0156 NDVI / year (≈ −0.16 / decade) |

**Interpretation:** There is a statistically significant and consistent long-term decline in
vegetation health across the study area. With a z-score of −5.15 and a p-value
indistinguishable from zero, this result is extremely unlikely to be due to chance.
The Sen's slope magnitude of −0.016 NDVI units per year is ecologically meaningful
over an 11-year span: it represents a cumulative loss of roughly 0.17 NDVI units,
which is substantial for a scene with a working range of approximately 0.1–0.8.

---

## 2. Rolling Mean (window = 6 captures)

Applied to the mean NDVI time series as a smoothing baseline.
Metrics describe series noise rather than predictive model error.

| Metric | Value |
|---|---|
| Window size | 6 captures |
| MAE (raw vs. smoothed) | 0.073 |
| Residual std | 0.093 |

**Interpretation:** Individual captures deviate from the smoothed trend by ~0.07 NDVI
units on average (~10% of the working range). This is expected: even captures that
pass the cloud cover filter can carry residual atmospheric scattering, partial cloud
shadow, or strong within-season variation. The residual standard deviation (0.093)
being close to the MAE (0.073) indicates the deviations are roughly symmetric —
no systematic bias above or below the smoothed line.

---

## 3. Seasonal Sinusoidal Model

A single-harmonic sinusoid — `A · sin(2π·t/12 + φ) + C` — fitted to monthly mean NDVI
values to characterise the seasonal cycle.

| Metric | Value |
|---|---|
| Amplitude (A) | 0.054 |
| Offset / mean level (C) | 0.225 |
| R² | 0.767 |
| RMSE | 0.021 |
| Peak month | ~November (month 11.2) |

**Interpretation:** The sinusoid explains 77% of the month-to-month variance in the
seasonal profile — a good fit for a single-harmonic model. The tight RMSE of 0.021
confirms the monthly means are well-captured. However, the amplitude of only 0.054
indicates the seasonal swing is weak in absolute terms: vegetation in this area does
not experience dramatic green-up and brown-down cycles between seasons. The November
peak is consistent with a subtropical study area (Puebla region, Mexico) where the
end of the rainy season and onset of cooler, drier, clearer conditions can coincide
with peak or late-season vegetation response.

---

## 4. Anomaly Model (departure from monthly climatology)

For each capture, the anomaly is computed as the deviation of its mean NDVI from the
long-term average of all captures in the same calendar month (the climatological
baseline). This isolates inter-annual variability from the seasonal cycle.

| Metric | Value |
|---|---|
| Explained variance ratio | 0.141 |
| Seasonal model RMSE | 0.044 |
| Anomaly RMSE | 0.107 |

**Interpretation:** The seasonal baseline accounts for only **14% of total variance**
in the time series. This is the most significant finding from this model: the dominant
driver of capture-to-capture NDVI differences is not the calendar month, but
year-to-year variation — drought intensity, wet season strength, land use change, or
multi-year climate anomalies. The anomaly RMSE of 0.107 is roughly **double** the
seasonal amplitude (0.054), meaning that unusual years deviate from their monthly
baseline by more than the entire seasonal swing. This points to high inter-annual
instability in the vegetation signal across the study period.

---

## 5. Pixel-wise OLS Spatial Regression

Ordinary least squares linear regression of NDVI vs. fractional year fitted
independently to every pixel in the scene (at 640 × 441 px resolution).
Significance tested via two-tailed t-test on the regression slope (α = 0.05).
Spatial outputs: slope map, R² map, −log₁₀(p-value) map, mean, std, and CV maps.

| Metric | Value |
|---|---|
| Mean R² | 0.047 |
| Median R² | 0.041 |
| Significant pixels (α = 0.05) | **86.2%** |
| Mean slope | −0.0145 NDVI / year |
| Median slope | −0.0145 NDVI / year |

**Interpretation:** The apparent contradiction between a low R² (~5%) and high
spatial significance (86%) is a feature of large-sample statistics: with 271 time
points, even a weak but consistent linear signal becomes detectable above noise.
The trend is real and spatially pervasive — it is not being driven by a localised
hotspot. The near-identical mean and median slopes confirm a symmetric distribution
of pixel trends with no extreme outliers pulling the spatial average; the entire
scene declines at approximately the same rate. The low R² reflects the fact that
high-frequency noise (residual cloud effects, within-season variation, inter-annual
climate swings) dominates the temporal variance at the pixel level — which is
consistent with the anomaly model finding that 86% of total variance is
non-seasonal and non-linear.

---

## Summary

All four models converge on the same conclusion: **the study area shows a
statistically significant and spatially consistent decline in vegetation health
of approximately −0.015 NDVI units per year over the 2015–2026 period.** The
decline is not explained by a seasonal shift (the seasonal cycle is stable and weak)
but by a persistent long-term signal that affects the vast majority of the scene.
Inter-annual variability is high, suggesting the trend sits on top of considerable
year-to-year noise, likely driven by variable rainfall and land use pressures.

| Model | Key validation metric | Result |
|---|---|---|
| Mann-Kendall | p-value | ~0 (highly significant) |
| Sen's slope | Magnitude | −0.016 NDVI/year |
| Rolling mean | MAE | 0.073 (moderate noise) |
| Sinusoidal seasonal fit | R² | 0.767 (good fit) |
| Anomaly model | Explained variance | 14% (inter-annual dominates) |
| Pixel OLS regression | % significant pixels | 86.2% |
