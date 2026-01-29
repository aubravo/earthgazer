# EarthGazer Helm Chart

Helm chart for deploying EarthGazer - a satellite image processing and analysis platform - on Kubernetes.

## Overview

This Helm chart deploys a complete EarthGazer stack including:

- **PostgreSQL Database** (official postgres:15-alpine image) - Stores metadata and task information
- **Redis** (official redis:7-alpine image) - Message broker for Celery task queue
- **Celery Workers** - Three types of workers for different workloads:
  - I/O Workers: Optimized for download/upload tasks
  - CPU Workers: Optimized for computation-intensive tasks
  - Default Workers: Handle miscellaneous tasks
- **Flower** - Web-based monitoring UI for Celery
- **Persistent Storage** - Shared volume for satellite imagery data

**Note**: This chart uses official Docker Hub images for PostgreSQL and Redis instead of Bitnami charts, ensuring free and open access without licensing concerns.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure
- **ReadWriteMany (RWX) storage class** for shared data access across multiple workers
- Optional: Ingress controller for external access to Flower

## Installing the Chart

### 1. Create Secrets

Create a Kubernetes secret with your Google Cloud service account credentials:

```bash
# Base64-encode your service account JSON
export GCLOUD_SA=$(cat /path/to/service-account.json | base64 -w 0)

# Create the secret
kubectl create secret generic gcloud-credentials \
  --from-literal=service-account.json="${GCLOUD_SA}"
```

Create secrets for database and Redis passwords (for production):

```bash
kubectl create secret generic postgresql-credentials \
  --from-literal=postgres-password=YOUR_POSTGRES_PASSWORD

kubectl create secret generic redis-credentials \
  --from-literal=redis-password=YOUR_REDIS_PASSWORD

kubectl create secret generic flower-credentials \
  --from-literal=password=YOUR_FLOWER_PASSWORD
```

### 2. Install the Chart

#### Development Installation

```bash
helm install earthgazer . -f values-dev.yaml \
  --set gcloud.serviceAccount="$(cat /path/to/service-account.json | base64 -w 0)" \
  --set gcloud.bucketName="your-dev-bucket"
```

#### Production Installation

```bash
helm install earthgazer . -f values-prod.yaml \
  --set image.registry=your-registry.io \
  --set image.tag=1.0.0 \
  --set gcloud.existingSecret=gcloud-credentials \
  --set gcloud.bucketName=your-prod-bucket \
  --set postgresql.auth.existingSecret=postgresql-credentials \
  --set redis.auth.existingSecret=redis-credentials \
  --set flower.auth.existingSecret=flower-credentials
```

### 3. Verify Installation

Check that all pods are running:

```bash
kubectl get pods -l app.kubernetes.io/name=earthgazer
```

Check the status of the release:

```bash
helm status earthgazer
```

## Configuration

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `image.registry` | Container image registry | `docker.io` |
| `image.repository` | Container image repository | `earthgazer/earthgazer` |
| `image.tag` | Container image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `imagePullSecrets` | Image pull secrets | `[]` |

### Persistence

| Parameter | Description | Default |
|-----------|-------------|---------|
| `persistence.enabled` | Enable persistent storage | `true` |
| `persistence.storageClass` | Storage class name (must support RWX) | `""` (cluster default) |
| `persistence.accessMode` | Access mode (must be ReadWriteMany) | `ReadWriteMany` |
| `persistence.size` | Storage size | `50Gi` |
| `persistence.annotations` | PVC annotations | `{}` |

**Important**: The storage class must support `ReadWriteMany` (RWX) access mode since multiple worker pods need to read/write the same data.

Common RWX storage solutions:
- NFS-based storage (nfs-client, nfs-subdir-external-provisioner)
- Cloud provider file storage (AWS EFS, Azure Files, GCP Filestore)
- Distributed file systems (CephFS, GlusterFS)

### Google Cloud Configuration

| Parameter | Description | Default |
|-----------|-------------|---------|
| `gcloud.serviceAccount` | Base64-encoded service account JSON | `""` |
| `gcloud.bucketName` | GCS bucket name | `""` |
| `gcloud.existingSecret` | Existing secret with service account | `""` |

### PostgreSQL Configuration

Uses Bitnami PostgreSQL chart. See [full configuration options](https://github.com/bitnami/charts/tree/main/bitnami/postgresql).

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Enable PostgreSQL | `true` |
| `postgresql.auth.username` | Database username | `earthgazer` |
| `postgresql.auth.password` | Database password | `""` |
| `postgresql.auth.database` | Database name | `earthgazer` |
| `postgresql.auth.existingSecret` | Existing secret with password | `""` |
| `postgresql.primary.persistence.size` | Database storage size | `50Gi` |

### Redis Configuration

Uses Bitnami Redis chart. See [full configuration options](https://github.com/bitnami/charts/tree/main/bitnami/redis).

| Parameter | Description | Default |
|-----------|-------------|---------|
| `redis.enabled` | Enable Redis | `true` |
| `redis.auth.enabled` | Enable authentication | `true` |
| `redis.auth.password` | Redis password | `""` |
| `redis.auth.existingSecret` | Existing secret with password | `""` |
| `redis.master.persistence.size` | Redis storage size | `10Gi` |

### Workers Configuration

#### I/O Workers (Download/Upload Tasks)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `workers.io.enabled` | Enable I/O workers | `true` |
| `workers.io.replicaCount` | Number of replicas | `2` |
| `workers.io.concurrency` | Tasks per worker | `8` |
| `workers.io.autoscaling.enabled` | Enable HPA | `true` |
| `workers.io.autoscaling.minReplicas` | Minimum replicas | `2` |
| `workers.io.autoscaling.maxReplicas` | Maximum replicas | `10` |
| `workers.io.autoscaling.targetCPUUtilizationPercentage` | Target CPU % | `70` |

#### CPU Workers (Computation Tasks)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `workers.cpu.enabled` | Enable CPU workers | `true` |
| `workers.cpu.replicaCount` | Number of replicas | `3` |
| `workers.cpu.concurrency` | Tasks per worker | `4` |
| `workers.cpu.autoscaling.enabled` | Enable HPA | `true` |
| `workers.cpu.autoscaling.minReplicas` | Minimum replicas | `3` |
| `workers.cpu.autoscaling.maxReplicas` | Maximum replicas | `20` |
| `workers.cpu.autoscaling.targetCPUUtilizationPercentage` | Target CPU % | `80` |

#### Default Workers (Miscellaneous Tasks)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `workers.default.enabled` | Enable default workers | `true` |
| `workers.default.replicaCount` | Number of replicas | `1` |

### Flower Monitoring UI

| Parameter | Description | Default |
|-----------|-------------|---------|
| `flower.enabled` | Enable Flower | `true` |
| `flower.auth.username` | Basic auth username | `admin` |
| `flower.auth.password` | Basic auth password | `""` |
| `flower.auth.existingSecret` | Existing secret with password | `""` |
| `flower.ingress.enabled` | Enable ingress | `false` |
| `flower.ingress.className` | Ingress class name | `nginx` |
| `flower.ingress.hosts` | Ingress hosts configuration | See values.yaml |

### Network Policy

| Parameter | Description | Default |
|-----------|-------------|---------|
| `networkPolicy.enabled` | Enable network policies | `false` |
| `networkPolicy.policyTypes` | Policy types | `["Ingress", "Egress"]` |

## Usage Examples

### Accessing Flower UI

#### Without Ingress (Development)

Port-forward to access Flower locally:

```bash
kubectl port-forward svc/earthgazer-flower 5555:5555
```

Then open http://localhost:5555 in your browser.

#### With Ingress (Production)

Configure ingress in `values-prod.yaml`:

```yaml
flower:
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: flower.earthgazer.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: flower-tls
        hosts:
          - flower.earthgazer.example.com
```

### Scaling Workers

#### Manual Scaling

```bash
# Scale I/O workers to 5 replicas
kubectl scale deployment earthgazer-worker-io --replicas=5

# Scale CPU workers to 10 replicas
kubectl scale deployment earthgazer-worker-cpu --replicas=10
```

#### Adjust Autoscaling

Update the Helm values:

```bash
helm upgrade earthgazer . \
  --set workers.cpu.autoscaling.maxReplicas=50 \
  --reuse-values
```

### Viewing Logs

```bash
# View logs from all I/O workers
kubectl logs -l app.kubernetes.io/component=worker-io --tail=100 -f

# View logs from specific worker
kubectl logs earthgazer-worker-cpu-abc123-xyz --tail=100 -f

# View Flower logs
kubectl logs -l app.kubernetes.io/component=flower --tail=100 -f
```

### Monitoring Workers

```bash
# Get worker status
kubectl get pods -l app.kubernetes.io/name=earthgazer

# Check HPA status
kubectl get hpa

# View HPA metrics
kubectl describe hpa earthgazer-worker-cpu-hpa
```

### Database Operations

#### Connect to PostgreSQL

```bash
# Get PostgreSQL password
export POSTGRES_PASSWORD=$(kubectl get secret earthgazer-postgresql \
  -o jsonpath="{.data.postgres-password}" | base64 --decode)

# Connect to database
kubectl run earthgazer-postgresql-client --rm --tty -i --restart='Never' \
  --image docker.io/bitnami/postgresql:15 \
  --env="PGPASSWORD=$POSTGRES_PASSWORD" \
  --command -- psql --host earthgazer-postgresql -U earthgazer -d earthgazer
```

#### Backup Database

```bash
kubectl exec -it earthgazer-postgresql-0 -- bash
pg_dump -U earthgazer earthgazer > /tmp/backup.sql
```

### Redis Operations

#### Connect to Redis

```bash
# Get Redis password
export REDIS_PASSWORD=$(kubectl get secret earthgazer-redis \
  -o jsonpath="{.data.redis-password}" | base64 --decode)

# Connect to Redis
kubectl run earthgazer-redis-client --rm --tty -i --restart='Never' \
  --image docker.io/bitnami/redis:7 \
  --env="REDISCLI_AUTH=$REDIS_PASSWORD" \
  --command -- redis-cli -h earthgazer-redis-master
```

## Upgrading

### Upgrade to New Version

```bash
# Update dependencies first
helm dependency update

# Upgrade release
helm upgrade earthgazer . -f values-prod.yaml \
  --set image.tag=1.1.0
```

### Rollback

```bash
# View revision history
helm history earthgazer

# Rollback to previous revision
helm rollback earthgazer

# Rollback to specific revision
helm rollback earthgazer 2
```

## Uninstalling

```bash
# Uninstall the release
helm uninstall earthgazer

# Optionally delete PVCs (this will delete all data!)
kubectl delete pvc -l app.kubernetes.io/name=earthgazer
kubectl delete pvc data-earthgazer-postgresql-0
kubectl delete pvc redis-data-earthgazer-redis-master-0
```

**Warning**: Deleting PVCs will permanently delete all stored data including satellite imagery, database, and Redis cache.

## Troubleshooting

### Workers Not Starting

Check if PVC is bound:

```bash
kubectl get pvc earthgazer-data
```

If PVC is `Pending`, check storage class:

```bash
kubectl describe pvc earthgazer-data
```

Ensure your cluster has a storage class that supports ReadWriteMany.

### Database Connection Issues

Check PostgreSQL pod status:

```bash
kubectl get pods -l app.kubernetes.io/name=postgresql
kubectl logs -l app.kubernetes.io/name=postgresql
```

Verify connection string in ConfigMap:

```bash
kubectl get configmap earthgazer-config -o yaml
```

### Redis Connection Issues

Check Redis pod status:

```bash
kubectl get pods -l app.kubernetes.io/name=redis
kubectl logs -l app.kubernetes.io/name=redis
```

Test Redis connection:

```bash
export REDIS_PASSWORD=$(kubectl get secret earthgazer-redis \
  -o jsonpath="{.data.redis-password}" | base64 --decode)

kubectl run redis-test --rm -i --tty --image=redis:alpine -- \
  redis-cli -h earthgazer-redis-master -a $REDIS_PASSWORD ping
```

### Autoscaling Not Working

Check if metrics-server is installed:

```bash
kubectl top nodes
kubectl top pods
```

If metrics are not available, install metrics-server:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

### Flower Not Accessible

Check Flower service and pod:

```bash
kubectl get svc earthgazer-flower
kubectl get pods -l app.kubernetes.io/component=flower
kubectl logs -l app.kubernetes.io/component=flower
```

If using ingress, check ingress status:

```bash
kubectl get ingress earthgazer-flower
kubectl describe ingress earthgazer-flower
```

## Production Considerations

### Storage

- Use high-performance storage class for PostgreSQL (SSD-backed)
- Use network file storage (NFS, EFS, Filestore) for data PVC
- Size storage appropriately (1TB+ for production workloads)
- Configure backup strategy for PVCs

### Security

- Enable network policies to restrict pod-to-pod communication
- Use existing secrets for all sensitive data
- Enable TLS for Flower ingress
- Configure RBAC appropriately
- Regularly rotate passwords and credentials

### Resources

- Set appropriate resource requests and limits based on workload
- Monitor resource usage and adjust accordingly
- Use node affinity to place CPU workers on compute-optimized nodes
- Consider using dedicated node pools for different worker types

### Monitoring

- Integrate with Prometheus for metrics collection
- Set up alerts for worker failures, queue backlogs
- Monitor storage usage
- Track task execution times and success rates

### High Availability

- Run multiple replicas of workers
- Enable autoscaling for handling variable workloads
- Use anti-affinity rules to spread workers across nodes
- Configure pod disruption budgets
- Use StatefulSets with replicas for PostgreSQL (if needed)

## License

This Helm chart follows the same license as the EarthGazer project.

## Support

For issues, questions, or contributions, please refer to the main EarthGazer repository.
