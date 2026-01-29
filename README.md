# EARTHGAZER

Commiting everything back in from scratch because I no longer remember how any of this works.

## What's this repo?

This is my master's thesis project.
It's an hyperspectral-satellite-image multi-tool that allows monitoring of available images, storage, tracking, preprocessing, and post-processing of said images with the intent of generating a dataset for training models for image processing.

## Configuration

### Data Storage Path

EarthGazer stores satellite imagery data in a configurable directory. You can specify where this data should be stored using the `DATA_PATH` environment variable in Docker Compose.

#### Production Environment

1. Copy the example environment file:
   ```bash
   cp .env.prod.example .env.prod
   ```

2. Edit `.env.prod` and set the `DATA_PATH` variable:
   ```bash
   # Option 1: Relative path (default)
   DATA_PATH=./data

   # Option 2: Absolute path to external storage
   DATA_PATH=/mnt/storage/earthgazer-data

   # Option 3: User home directory
   DATA_PATH=~/earthgazer-data

   # Option 4: Named Docker volume
   DATA_PATH=earthgazer-data
   ```

3. If using a named volume, uncomment the volume definition in `docker-compose.prod.yml`:
   ```yaml
   volumes:
     earthgazer-data:
       driver: local
   ```

4. Start the services:
   ```bash
   docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
   ```

#### Development Environment

1. Copy the example environment file (optional - defaults work out of the box):
   ```bash
   cp .devcontainer/.env.example .devcontainer/.env
   ```

2. Optionally customize `DATA_PATH` in `.devcontainer/.env`:
   ```bash
   # Custom data path for development
   DATA_PATH=/path/to/your/dev/data
   ```

3. Rebuild and restart the development container through VS Code.

#### Data Directory Structure

The data directory will contain:
```
data/
├── raw/              # Downloaded raw satellite imagery
├── processed/        # Intermediate processed data
└── features/         # Generated features (NDVI, RGB composites)
```

#### Storage Recommendations

- **Development**: Default `./data` directory (a few GB)
- **Production**: External SSD/HDD with 100GB+ capacity
- **Large-scale**: Network-attached storage (NAS) with multiple TB

**Note**: Ensure the specified path has sufficient space for satellite imagery data. A typical Sentinel-2 capture requires ~1-2 GB of storage.

