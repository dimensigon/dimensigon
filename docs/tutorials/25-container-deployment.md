# Tutorial 25: Container Deployment

Deploy and operate Dimensigon 3.0 in containerized environments. This tutorial covers Docker configuration, environment variables, service discovery, graceful shutdown, multi-node compose deployments, and Kubernetes considerations.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Docker HEALTHCHECK Configuration](#docker-healthcheck-configuration)
4. [Environment Variables](#environment-variables)
5. [DNS-Based Service Discovery](#dns-based-service-discovery)
6. [Auto-Join on Startup](#auto-join-on-startup)
7. [Graceful Shutdown](#graceful-shutdown)
8. [Docker Compose Reference Deployment](#docker-compose-reference-deployment)
9. [Scaling with Docker Compose](#scaling-with-docker-compose)
10. [Kubernetes Deployment Notes](#kubernetes-deployment-notes)
11. [Configuration Reference](#configuration-reference)
12. [Related Features](#related-features)

---

## Overview

Dimensigon 3.0 is designed to run natively in containerized environments. The container image supports:

- Health checking for orchestrator-managed restarts
- Environment-variable-driven configuration (no config files required)
- DNS-based discovery for automatic cluster formation
- Auto-join so new nodes register themselves on startup
- Graceful shutdown with connection draining on SIGTERM

Whether you are running a simple Docker Compose stack or a full Kubernetes deployment, this tutorial provides the patterns you need.

---

## Prerequisites

- Docker 20.10+ or a compatible container runtime
- Docker Compose v2 (for multi-node examples)
- Basic understanding of Docker networking
- For Kubernetes sections: kubectl and a running cluster

---

## Docker HEALTHCHECK Configuration

The Dimensigon container image includes a built-in health endpoint. Configure your container orchestrator to use it for liveness and readiness checks.

### Default HEALTHCHECK in the Dockerfile

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1
```

### Health Endpoint Response

The `/health` endpoint returns the node's status:

```bash
curl -s http://localhost:5000/health | jq .
```

```json
{
  "status": "healthy",
  "node": "dimensigon-01",
  "uptime_seconds": 86420,
  "cluster_size": 3,
  "version": "3.0.0"
}
```

### Customizing the Health Check

Override the default health check in your `docker-compose.yml` or `docker run` command:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 15s
  timeout: 5s
  start_period: 45s
  retries: 5
```

### Health Check Parameters

| Parameter      | Default | Description                                      |
|----------------|---------|--------------------------------------------------|
| `interval`     | 30s     | Time between health checks                       |
| `timeout`      | 10s     | Maximum time for a health check to respond       |
| `start_period` | 60s     | Grace period during startup before checks count  |
| `retries`      | 3       | Consecutive failures before marking as unhealthy |

---

## Environment Variables

All Dimensigon container configuration is driven through environment variables prefixed with `DM_`. No configuration files are required.

### Core Variables

| Variable                         | Required | Default           | Description                                    |
|----------------------------------|----------|-------------------|------------------------------------------------|
| `DM_NODE_NAME`                   | No       | Container hostname| Human-readable name for this node              |
| `DM_SECRET_KEY`                  | Yes      | --                | Secret key for JWT signing and encryption. Must be the same across all cluster nodes |
| `DM_DATABASE_URL`                | No       | `sqlite:///dm.db` | Database connection string                     |
| `DM_DISCOVERY_DNS`               | No       | --                | DNS name used for service discovery            |
| `DM_AUTO_JOIN`                   | No       | `true`            | Automatically join the cluster on startup      |
| `DM_GRACEFUL_SHUTDOWN_TIMEOUT`   | No       | `30`              | Seconds to wait for connections to drain on shutdown |

### Setting Variables with Docker Run

```bash
docker run -d \
  --name dimensigon-01 \
  -e DM_NODE_NAME=node-01 \
  -e DM_SECRET_KEY=your-cluster-secret-key-min-32-chars \
  -e DM_DATABASE_URL=postgresql://dm:password@db:5432/dimensigon \
  -e DM_DISCOVERY_DNS=dimensigon.local \
  -e DM_AUTO_JOIN=true \
  -e DM_GRACEFUL_SHUTDOWN_TIMEOUT=30 \
  -p 5000:5000 \
  dimensigon/dimensigon:3.0
```

### DM_SECRET_KEY

The secret key is used for:

- JWT token signing and verification
- Inter-node communication encryption
- Session management

All nodes in a cluster **must** use the same `DM_SECRET_KEY`. Use a strong, random value of at least 32 characters:

```bash
# Generate a secure secret key
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

### DM_DATABASE_URL

Supported database backends:

| Backend    | Connection String Format                                  |
|------------|-----------------------------------------------------------|
| SQLite     | `sqlite:///path/to/dm.db`                                 |
| PostgreSQL | `postgresql://user:pass@host:5432/dbname`                 |
| MySQL      | `mysql+pymysql://user:pass@host:3306/dbname`              |

For production multi-node clusters, use PostgreSQL or MySQL so all nodes share the same database.

### DM_NODE_NAME

If not set, defaults to the container hostname. In Docker Compose, this is the service name plus a numeric suffix (e.g., `dimensigon-1`). Setting an explicit name makes logs and the node registry easier to read:

```bash
-e DM_NODE_NAME=web-cluster-node-01
```

---

## DNS-Based Service Discovery

In containerized environments, DNS-based service discovery allows Dimensigon nodes to find each other automatically without hardcoding IP addresses.

### How It Works

1. Set `DM_DISCOVERY_DNS` to a DNS name that resolves to all Dimensigon nodes.
2. On startup, each node queries the DNS name and receives a list of IP addresses.
3. The node attempts to contact each IP to register itself with the cluster.
4. The DNS query is repeated periodically to discover newly added nodes.

### Docker Compose DNS

In Docker Compose, the service name automatically acts as a DNS name that resolves to all containers for that service:

```yaml
services:
  dimensigon:
    image: dimensigon/dimensigon:3.0
    environment:
      DM_DISCOVERY_DNS: dimensigon
```

When you run `docker-compose up --scale dimensigon=3`, the DNS name `dimensigon` resolves to all three container IPs.

### Custom DNS Configuration

For environments with external DNS (Consul, CoreDNS, or cloud-managed DNS):

```bash
-e DM_DISCOVERY_DNS=dimensigon.service.consul
```

---

## Auto-Join on Startup

When `DM_AUTO_JOIN=true` (the default), a Dimensigon node will automatically:

1. Start its local services
2. Query `DM_DISCOVERY_DNS` for peer addresses
3. Attempt to join the existing cluster
4. If no peers are found, initialize as the first node (becomes the leader)
5. Register itself in the cluster node registry

### Startup Sequence

```
[INFO] Starting Dimensigon 3.0.0
[INFO] Node name: node-01
[INFO] Auto-join enabled, discovering peers via DNS: dimensigon.local
[INFO] DNS resolved to: [10.0.1.2, 10.0.1.3]
[INFO] Contacting peer 10.0.1.2:5000... connected
[INFO] Successfully joined cluster (3 nodes total)
[INFO] Listening on 0.0.0.0:5000
```

### Disabling Auto-Join

For manual cluster management, disable auto-join:

```bash
-e DM_AUTO_JOIN=false
```

With auto-join disabled, you must manually register nodes using the API:

```bash
curl -X POST http://localhost:5000/dm-webmanager/api/nodes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "node-03",
    "address": "10.0.1.4",
    "port": 5000
  }'
```

---

## Graceful Shutdown

When a Dimensigon container receives a SIGTERM signal (the standard container stop signal), it performs a graceful shutdown sequence.

### Shutdown Sequence

1. **Stop accepting new requests.** The node immediately stops accepting new incoming connections.
2. **Drain active connections.** In-progress requests are allowed to complete within the drain timeout.
3. **Notify cluster peers.** The node sends a departure notification so peers update their node registry.
4. **Stop running executions.** Any orchestration steps running on this node are paused (not terminated) and can be resumed by another node.
5. **Close database connections.** All database connections are cleanly closed.
6. **Exit.** The process exits with code 0.

### Configuring the Drain Timeout

The `DM_GRACEFUL_SHUTDOWN_TIMEOUT` variable controls how long the node waits for in-progress requests to complete before forcing a shutdown:

```bash
# Wait up to 60 seconds for connections to drain
-e DM_GRACEFUL_SHUTDOWN_TIMEOUT=60
```

| Value | Behavior                                                     |
|-------|--------------------------------------------------------------|
| `0`   | Immediate shutdown (not recommended for production)          |
| `30`  | Default: 30 seconds to drain                                |
| `60`  | Recommended for production with long-running orchestrations  |
| `120` | Maximum reasonable value for very long operations            |

### Docker Stop Timeout

Ensure your Docker stop timeout is equal to or greater than the drain timeout:

```bash
# Stop with a 60-second timeout (matching DM_GRACEFUL_SHUTDOWN_TIMEOUT=60)
docker stop --time 60 dimensigon-01
```

In Docker Compose:

```yaml
services:
  dimensigon:
    stop_grace_period: 60s
```

---

## Docker Compose Reference Deployment

The following `docker-compose.yml` defines a production-ready 3-node Dimensigon cluster with a shared PostgreSQL database.

### docker-compose.yml

```yaml
version: "3.8"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dimensigon
      POSTGRES_USER: dm
      POSTGRES_PASSWORD: secure-db-password
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dm -d dimensigon"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dm-network

  dimensigon-01:
    image: dimensigon/dimensigon:3.0
    environment:
      DM_NODE_NAME: node-01
      DM_SECRET_KEY: your-cluster-secret-key-at-least-32-characters-long
      DM_DATABASE_URL: postgresql://dm:secure-db-password@db:5432/dimensigon
      DM_DISCOVERY_DNS: dimensigon-01
      DM_AUTO_JOIN: "true"
      DM_GRACEFUL_SHUTDOWN_TIMEOUT: "60"
    ports:
      - "5001:5000"
    depends_on:
      db:
        condition: service_healthy
    stop_grace_period: 65s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3
    networks:
      - dm-network

  dimensigon-02:
    image: dimensigon/dimensigon:3.0
    environment:
      DM_NODE_NAME: node-02
      DM_SECRET_KEY: your-cluster-secret-key-at-least-32-characters-long
      DM_DATABASE_URL: postgresql://dm:secure-db-password@db:5432/dimensigon
      DM_DISCOVERY_DNS: dimensigon-01
      DM_AUTO_JOIN: "true"
      DM_GRACEFUL_SHUTDOWN_TIMEOUT: "60"
    ports:
      - "5002:5000"
    depends_on:
      db:
        condition: service_healthy
      dimensigon-01:
        condition: service_healthy
    stop_grace_period: 65s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3
    networks:
      - dm-network

  dimensigon-03:
    image: dimensigon/dimensigon:3.0
    environment:
      DM_NODE_NAME: node-03
      DM_SECRET_KEY: your-cluster-secret-key-at-least-32-characters-long
      DM_DATABASE_URL: postgresql://dm:secure-db-password@db:5432/dimensigon
      DM_DISCOVERY_DNS: dimensigon-01
      DM_AUTO_JOIN: "true"
      DM_GRACEFUL_SHUTDOWN_TIMEOUT: "60"
    ports:
      - "5003:5000"
    depends_on:
      db:
        condition: service_healthy
      dimensigon-01:
        condition: service_healthy
    stop_grace_period: 65s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3
    networks:
      - dm-network

volumes:
  db-data:

networks:
  dm-network:
    driver: bridge
```

### Launch the Cluster

```bash
# Start all services
docker-compose up -d

# Watch the logs
docker-compose logs -f

# Check cluster health
curl -s http://localhost:5001/health | jq .
curl -s http://localhost:5002/health | jq .
curl -s http://localhost:5003/health | jq .
```

### Verify Cluster Formation

```bash
TOKEN=$(curl -s -X POST http://localhost:5001/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  | jq -r '.access_token')

# List all nodes in the cluster
curl -s http://localhost:5001/dm-webmanager/api/nodes \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected output showing all 3 nodes:

```json
{
  "total": 3,
  "nodes": [
    {"name": "node-01", "status": "online", "address": "10.0.1.2:5000"},
    {"name": "node-02", "status": "online", "address": "10.0.1.3:5000"},
    {"name": "node-03", "status": "online", "address": "10.0.1.4:5000"}
  ]
}
```

---

## Scaling with Docker Compose

For dynamic scaling using a single service definition, use the `--scale` flag.

### Scalable Compose File

```yaml
version: "3.8"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: dimensigon
      POSTGRES_USER: dm
      POSTGRES_PASSWORD: secure-db-password
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dm -d dimensigon"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - dm-network

  dimensigon:
    image: dimensigon/dimensigon:3.0
    environment:
      DM_SECRET_KEY: your-cluster-secret-key-at-least-32-characters-long
      DM_DATABASE_URL: postgresql://dm:secure-db-password@db:5432/dimensigon
      DM_DISCOVERY_DNS: dimensigon
      DM_AUTO_JOIN: "true"
      DM_GRACEFUL_SHUTDOWN_TIMEOUT: "60"
    depends_on:
      db:
        condition: service_healthy
    stop_grace_period: 65s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 3
    networks:
      - dm-network

volumes:
  db-data:

networks:
  dm-network:
    driver: bridge
```

### Scale Up

```bash
# Start with 3 nodes
docker-compose up -d --scale dimensigon=3

# Scale to 5 nodes
docker-compose up -d --scale dimensigon=5

# Scale back down to 2 nodes
docker-compose up -d --scale dimensigon=2
```

When scaling up, new containers discover existing nodes via DNS and auto-join the cluster. When scaling down, removed containers go through the graceful shutdown sequence.

> **Note:** When using `--scale`, you cannot map fixed host ports. Remove the `ports` mapping or use a reverse proxy/load balancer in front of the service.

---

## Kubernetes Deployment Notes

For Kubernetes environments, the same environment variables and discovery mechanisms apply with Kubernetes-native abstractions.

### StatefulSet Deployment

Use a StatefulSet for stable network identities and ordered startup:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: dimensigon
spec:
  serviceName: dimensigon
  replicas: 3
  selector:
    matchLabels:
      app: dimensigon
  template:
    metadata:
      labels:
        app: dimensigon
    spec:
      terminationGracePeriodSeconds: 65
      containers:
        - name: dimensigon
          image: dimensigon/dimensigon:3.0
          ports:
            - containerPort: 5000
          env:
            - name: DM_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: dimensigon-secrets
                  key: secret-key
            - name: DM_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: dimensigon-secrets
                  key: database-url
            - name: DM_DISCOVERY_DNS
              value: "dimensigon-headless.default.svc.cluster.local"
            - name: DM_AUTO_JOIN
              value: "true"
            - name: DM_GRACEFUL_SHUTDOWN_TIMEOUT
              value: "60"
          livenessProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 60
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /health
              port: 5000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 3
```

### Headless Service for DNS Discovery

```yaml
apiVersion: v1
kind: Service
metadata:
  name: dimensigon-headless
spec:
  clusterIP: None
  selector:
    app: dimensigon
  ports:
    - port: 5000
      targetPort: 5000
```

The headless service creates DNS A records for each pod, enabling `DM_DISCOVERY_DNS` to resolve to all pod IPs.

### Kubernetes Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dimensigon-secrets
type: Opaque
data:
  secret-key: <base64-encoded-secret-key>
  database-url: <base64-encoded-database-url>
```

### Key Kubernetes Considerations

| Concern              | Recommendation                                          |
|----------------------|---------------------------------------------------------|
| Storage              | Use an external database (PostgreSQL) rather than SQLite |
| Secrets              | Store DM_SECRET_KEY and DM_DATABASE_URL in Kubernetes Secrets |
| Scaling              | Use `kubectl scale statefulset dimensigon --replicas=N` |
| Rolling updates      | Set `maxUnavailable: 1` to maintain cluster quorum      |
| Pod disruption budget| Set `minAvailable: 2` for 3+ node clusters              |
| Network policy       | Allow TCP 5000 between pods in the dimensigon namespace |
| Termination          | Set `terminationGracePeriodSeconds` >= `DM_GRACEFUL_SHUTDOWN_TIMEOUT` + 5 |

---

## Configuration Reference

### Complete Environment Variable Reference

| Variable                       | Required | Default           | Description                              |
|--------------------------------|----------|-------------------|------------------------------------------|
| `DM_NODE_NAME`                 | No       | Hostname          | Node display name                        |
| `DM_SECRET_KEY`                | Yes      | --                | Cluster secret for JWT and encryption    |
| `DM_DATABASE_URL`              | No       | `sqlite:///dm.db` | Database connection string               |
| `DM_DISCOVERY_DNS`             | No       | --                | DNS name for peer discovery              |
| `DM_AUTO_JOIN`                 | No       | `true`            | Auto-join cluster on startup             |
| `DM_GRACEFUL_SHUTDOWN_TIMEOUT` | No       | `30`              | Seconds to drain on shutdown             |
| `DM_LOG_LEVEL`                 | No       | `INFO`            | Log verbosity (DEBUG, INFO, WARNING, ERROR) |
| `DM_PORT`                      | No       | `5000`            | Port to listen on                        |
| `DM_BIND_ADDRESS`              | No       | `0.0.0.0`         | Address to bind to                       |

### Production Checklist

- [ ] Set a strong, unique `DM_SECRET_KEY` (32+ characters)
- [ ] Use PostgreSQL or MySQL for multi-node clusters (not SQLite)
- [ ] Configure `DM_DISCOVERY_DNS` for automatic peer discovery
- [ ] Set `DM_GRACEFUL_SHUTDOWN_TIMEOUT` >= 30 seconds
- [ ] Ensure container `stop_grace_period` >= `DM_GRACEFUL_SHUTDOWN_TIMEOUT` + 5 seconds
- [ ] Configure health checks with appropriate `start_period` for your environment
- [ ] Use the same `DM_SECRET_KEY` across all nodes in the cluster
- [ ] Mount database volumes for data persistence (if using SQLite for testing)

---

## Related Features

- [Tutorial 12: Webhooks](12-webhooks.md) -- Receive `node.online` and `node.offline` events as containers scale up and down
- [Tutorial 13: Scheduled Orchestrations](13-scheduled-orchestrations.md) -- The scheduler runs on the leader node; leadership transfers automatically during scaling events
- [Tutorial 14: Orchestration Versioning](14-orchestration-versioning.md) -- Version history is stored in the shared database and persists across container restarts
- [Tutorial 16: Audit Log](16-audit-log.md) -- Container startup and shutdown events are recorded in the audit log
