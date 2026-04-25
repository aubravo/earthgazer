# earthgazer

![earthgazer logo](https://github.com/aubravo/earthgazer/blob/main/docs/earthgazer.png?raw=true)


## What's this repo?

This is my master's thesis project.
It's an hyperspectral-satellite-image multi-tool that allows monitoring of available images, storage, tracking, preprocessing, and post-processing of said images with the intent of generating a dataset for training models for image processing.

## Why "earthgazer"

The idea behind the project is to allow us to gaze at Earth geo-locations.
The name is inspired by one of my favorite bands "Sungazer". If you like Jazz, EDM and/or experimental music I highly recommend you go give them a check.

## Deployment

### Prerequisites

**Docker Compose:**
- [Docker Engine](https://docs.docker.com/engine/install/) 20.10+
- [Docker Compose](https://docs.docker.com/compose/install/) v2.0+

**Helm (Kubernetes):**
- Kubernetes 1.19+
- [Helm](https://helm.sh/docs/intro/install/) 3.2.0+
- `kubectl` configured against your cluster
- A storage class with **ReadWriteMany** support (NFS, AWS EFS, GCP Filestore, Azure Files, CephFS, etc.) for shared worker data access

---

### Google Cloud Service Account

EarthGazer requires a Google Cloud service account to discover satellite captures via BigQuery and to store/retrieve imagery via Cloud Storage.

#### Required permissions

| Service | Role | Purpose |
|---------|------|---------|
| BigQuery | `roles/bigquery.jobUser` on your GCP project | Run discovery queries against the public satellite index |
| Cloud Storage | `roles/storage.objectAdmin` on your GCS bucket | Upload, download, and manage satellite imagery backups |

> **Note:** The satellite index tables in `bigquery-public-data.cloud_storage_geo_index` are publicly readable. `bigquery.jobUser` on your own project is sufficient to run queries against them.

Once you have the service account key file (`service-account.json`), keep it out of version control.

---

### Docker Compose

#### 1. Clone and configure

```bash
git clone https://github.com/aubravo/earthgazer.git
cd earthgazer
cp .env.prod.example .env.prod
```

Edit `.env.prod` and fill in every value, in particular:

- `DB_PASSWORD`, `REDIS_PASSWORD`, `FLOWER_PASSWORD` — use strong, unique passwords
- `GCLOUD_BUCKET_NAME` — your GCS bucket name
- `GCLOUD_SERVICE_ACCOUNT` — base64-encoded service account key:
  ```bash
  base64 -w 0 service-account.json
  ```

#### 2. Start services

```bash
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

This brings up PostgreSQL, Redis, the app container, three Celery worker types (io, cpu, default), and Flower.

#### 3. Run database migrations

```bash
docker-compose -f docker-compose.prod.yml --env-file .env.prod \
  exec app alembic upgrade head
```

#### 4. Verify

```bash
docker-compose -f docker-compose.prod.yml --env-file .env.prod ps
docker-compose -f docker-compose.prod.yml --env-file .env.prod \
  exec app earthgazer status
```

Flower is available at **http://localhost:5555** (log in with `FLOWER_USER` / `FLOWER_PASSWORD`).

---

### Helm (Kubernetes)

#### 1. Create a secrets override file

```bash
cd helm/earthgazer
cp values-secrets.example.yaml values-secrets.yaml
```

Edit `values-secrets.yaml` and fill in all sensitive values — paste the full contents of `service-account.json` under `gcloud.serviceAccount`:

```yaml
gcloud:
  serviceAccount: |
    {
      "type": "service_account",
      "project_id": "your-project-id",
      ...
    }
  bucketName: "your-earthgazer-bucket"

postgresql:
  auth:
    password: "strong-password"

redis:
  auth:
    password: "strong-password"

flower:
  auth:
    password: "strong-password"
```

`values-secrets.yaml` is gitignored and helmignored — it will never be committed or bundled into a chart package.

#### 2. Install the chart

**Development:**

```bash
helm install earthgazer helm/earthgazer -f helm/earthgazer/values-dev.yaml \
  -f helm/earthgazer/values-secrets.yaml
```

**Production:**

```bash
helm install earthgazer helm/earthgazer -f helm/earthgazer/values-prod.yaml \
  -f helm/earthgazer/values-secrets.yaml \
  --set image.tag=latest
```

#### 3. Run database migrations

Wait for the app pod to be `Running`, then:

```bash
kubectl exec -it deployment/earthgazer-app -- alembic upgrade head
```

#### 4. Verify

```bash
kubectl get pods -l app.kubernetes.io/name=earthgazer
kubectl exec -it deployment/earthgazer-app -- earthgazer status

# Access Flower without ingress
kubectl port-forward svc/earthgazer-flower 5555:5555
```

See [`helm/earthgazer/README.md`](helm/earthgazer/README.md) for the full parameter reference, scaling, and troubleshooting.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. **Fork** the repository and clone your fork locally.
2. **Create a branch** from `main` with a descriptive name:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Enable the versioned git hooks** (required once after cloning):
   ```bash
   git config core.hooksPath .githooks
   ```
   This installs two hooks:
   - `pre-commit` — runs `ruff check --fix` and `ruff format`, then re-stages any changes automatically.
   - `pre-push` — updates the build number in `earthgazer/__init__.py` to the current commit hash.
4. **Install the package** in editable mode and apply database migrations:
   ```bash
   pip install -e .
   alembic upgrade head
   ```
5. **Make your changes.** The pre-commit hook handles linting and formatting automatically, but you can also run ruff manually:
   ```bash
   ruff check .
   ruff format .
   ```
6. **Commit** your changes with a clear, descriptive message.
7. **Push** your branch and open a **Pull Request** against `main`. Describe what the PR does and why.

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

