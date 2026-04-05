# EarthGazer Processing Workflow

## Full Pipeline Diagram

```mermaid
flowchart TD
    %% ── External Data Sources ──────────────────────────────────────────
    BQ[(Google BigQuery\nSatellite Catalog)]
    GCS_PUB[(GCS – Public Bucket\nSentinel / Landsat scenes)]
    GCS_PRV[(GCS – Project Bucket\nBackup + Processed outputs)]

    %% ── Persistent State ───────────────────────────────────────────────
    PG[(PostgreSQL\nearthgazer schema)]
    FS[("Local Filesystem\ndata/raw/{capture_id}/\ndata/features/{capture_id}/")]

    %% ── Celery Infrastructure ──────────────────────────────────────────
    REDIS[(Redis\nBroker + Result Backend)]

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 1 – DISCOVERY  [io_queue]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph DISCOVERY["① Discovery  •  io_queue"]
        D1["discover_images_task\n─────────────────\nQuery BigQuery for captures\nthat overlap Location bounding boxes\n(date range + spatial filter)"]
        D2[/"New CaptureData rows\nstored in PostgreSQL"/]
    end

    BQ -->|"BigQuery SQL\n(per Location × Platform)"| D1
    PG -->|"Active Locations\n(bounds, date range)"| D1
    D1 --> D2
    D2 -->|"INSERT CaptureData\n(backed_up=False)"| PG

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 2 – BACKUP  [io_queue, parallel per capture]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph BACKUP["② Backup  •  io_queue  •  parallel per capture"]
        B1["backup_single_capture_task\n─────────────────\nCopy scene files from\npublic GCS → project bucket"]
        B2[/"backed_up=True\nbackup_location updated"/]
    end

    D2 -->|"capture_ids (group)"| B1
    GCS_PUB -->|"Source scene files"| B1
    B1 --> GCS_PRV
    B1 --> B2
    B2 -->|"UPDATE CaptureData"| PG

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 3 – DOWNLOAD BANDS  [io_queue, parallel per capture]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph DOWNLOAD["③ Download Bands  •  io_queue  •  parallel per capture"]
        DL1["download_bands_task\n─────────────────\nDownload B02, B03, B04, B08\nfrom project GCS bucket\nto local filesystem"]
    end

    B2 -->|"backed-up capture_ids"| DL1
    GCS_PRV -->|"Band .tif files"| DL1
    DL1 -->|"data/raw/{capture_id}/*.tif"| FS

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 4 – STACK & CROP  [cpu_queue, per capture]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph STACK["④ Stack & Crop  •  cpu_queue  •  per capture"]
        SC1["stack_and_crop_task\n─────────────────\nLoad bands → stack into ndarray\nCrop to bounding box\nNormalize\nSave stacked.npz"]
        SC_CACHE{{"Cached?\n(ProcessedImage\nlookup)"}}
    end

    FS -->|"Raw band .tif files"| SC_CACHE
    SC_CACHE -->|"No – process"| SC1
    SC_CACHE -->|"Yes – return path"| SC_OUT
    SC1 -->|"data/features/{id}/stacked.npz"| FS
    SC1 -->|"Upload stacked.npz"| GCS_PRV
    SC1 -->|"Register ProcessedImage\n(type=stacked)"| PG
    SC1 --> SC_OUT(["stacked.npz ready"])

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 5 – FEATURE EXTRACTION  [cpu_queue, parallel NDVI + RGB]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph FEATURES["⑤ Feature Extraction  •  cpu_queue  •  parallel NDVI ‖ RGB"]
        FE_NDVI["compute_ndvi_task\n─────────────────\nB08 (NIR) – B04 (Red)\n─────────────────────\nB08 (NIR) + B04 (Red)\nSave ndvi.tif (GeoTIFF)"]
        FE_RGB["generate_rgb_task\n─────────────────\nStack B04→R, B03→G, B02→B\nContrast stretch\nSave rgb.tif (GeoTIFF)"]
        FE_NDVI_CACHE{{"NDVI\nCached?"}}
        FE_RGB_CACHE{{"RGB\nCached?"}}
    end

    SC_OUT -->|"group()"| FE_NDVI_CACHE
    SC_OUT -->|"group()"| FE_RGB_CACHE

    FE_NDVI_CACHE -->|"No"| FE_NDVI
    FE_RGB_CACHE -->|"No"| FE_RGB

    FS -->|"stacked.npz"| FE_NDVI
    FS -->|"stacked.npz"| FE_RGB

    FE_NDVI -->|"data/features/{id}/ndvi.tif"| FS
    FE_RGB -->|"data/features/{id}/rgb.tif"| FS
    FE_NDVI -->|"Upload ndvi.tif"| GCS_PRV
    FE_RGB -->|"Upload rgb.tif"| GCS_PRV
    FE_NDVI -->|"Register ProcessedImage\n(type=ndvi)"| PG
    FE_RGB -->|"Register ProcessedImage\n(type=rgb)"| PG

    FE_NDVI --> FEAT_DONE(["Features ready"])
    FE_NDVI_CACHE -->|"Yes"| FEAT_DONE
    FE_RGB --> FEAT_DONE
    FE_RGB_CACHE -->|"Yes"| FEAT_DONE

    %% ═══════════════════════════════════════════════════════════════════
    %% STAGE 6 – TEMPORAL ANALYSIS  [cpu_queue, chord callback]
    %% ═══════════════════════════════════════════════════════════════════
    subgraph ANALYSIS["⑥ Temporal Analysis  •  cpu_queue  •  chord callback (all captures done)"]
        TA1["temporal_analysis_task\n─────────────────\nNDVI time-series statistics\nLinear trend per pixel\nGenerate plots"]
        TA2[/"ndvi_over_time.png\nndvi_trend_map.png"/]
    end

    FEAT_DONE -->|"chord() – wait for\nall captures"| TA1
    FS -->|"data/features/*/ndvi.tif"| TA1
    TA1 --> TA2

    %% ── Celery routing note ────────────────────────────────────────────
    REDIS -.->|"Task routing\n& result storage"| D1
    REDIS -.->|"Task routing\n& result storage"| B1
    REDIS -.->|"Task routing\n& result storage"| DL1
    REDIS -.->|"Task routing\n& result storage"| SC1
    REDIS -.->|"Task routing\n& result storage"| FE_NDVI
    REDIS -.->|"Task routing\n& result storage"| FE_RGB
    REDIS -.->|"Task routing\n& result storage"| TA1

    %% ── Styling ────────────────────────────────────────────────────────
    classDef datastore fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef task fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef decision fill:#fef9c3,stroke:#ca8a04,color:#713f12
    classDef output fill:#f3e8ff,stroke:#7c3aed,color:#3b0764
    classDef infra fill:#f1f5f9,stroke:#94a3b8,color:#334155

    class BQ,GCS_PUB,GCS_PRV,PG,FS datastore
    class D1,B1,DL1,SC1,FE_NDVI,FE_RGB,TA1 task
    class SC_CACHE,FE_NDVI_CACHE,FE_RGB_CACHE decision
    class D2,B2,TA2,SC_OUT,FEAT_DONE output
    class REDIS infra
```

## Workflow Summary

| Stage | Task | Queue | Parallelism | Input | Output |
|-------|------|-------|-------------|-------|--------|
| ① Discovery | `discover_images_task` | `io_queue` | Single | BigQuery + Locations DB | CaptureData rows in PG |
| ② Backup | `backup_single_capture_task` | `io_queue` | Per capture | Public GCS | Project GCS bucket |
| ③ Download | `download_bands_task` | `io_queue` | Per capture | Project GCS | `data/raw/{id}/*.tif` |
| ④ Stack & Crop | `stack_and_crop_task` | `cpu_queue` | Per capture | Raw `.tif` files | `stacked.npz` |
| ⑤a NDVI | `compute_ndvi_task` | `cpu_queue` | Parallel with RGB | `stacked.npz` | `ndvi.tif` |
| ⑤b RGB | `generate_rgb_task` | `cpu_queue` | Parallel with NDVI | `stacked.npz` | `rgb.tif` |
| ⑥ Analysis | `temporal_analysis_task` | `cpu_queue` | Chord callback | All `ndvi.tif` files | Trend plots |

### Celery Composition Primitives Used

- **`chain`** — sequential steps within a single capture (download → stack → features)
- **`group`** — parallel execution of NDVI and RGB tasks, or parallel backup/download across captures
- **`chord`** — waits for all per-capture processing to finish before triggering temporal analysis
