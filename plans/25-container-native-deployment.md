# Container-Native Deployment

- **Priority:** 25
- **Category:** Infrastructure
- **Effort:** 3-4 days
- **Dependencies:** #4 (Lightweight Health Endpoint)

## Context

dimensigon was designed for traditional server deployments and does not integrate well with
container orchestrators like Docker Swarm or Kubernetes. Containers are ephemeral, IP addresses
change, and nodes come and go. Container-native deployment adapts dimensigon to this reality
with auto-discovery, health-based readiness, and graceful lifecycle management.

## Scope

- Service discovery via DNS: new nodes discover peers using DNS SRV or A records instead
  of static configuration.
- Auto-join on startup: a new container automatically registers with the mesh and receives
  its configuration from peers.
- Health-based readiness probe: Kubernetes/Docker HEALTHCHECK uses `/health` endpoint to
  determine when a node is ready to receive traffic.
- Graceful shutdown: on SIGTERM, the node notifies peers of departure, drains active
  executions, and deregisters from the mesh.
- Environment-based configuration: all settings configurable via environment variables
  with sensible defaults for container deployment.
- Docker Compose and Kubernetes manifests for reference deployments.

## Files to Modify

- `dimensigon/bootstrap.py` (auto-join logic, DNS-based discovery)
- `dimensigon/core.py` (graceful shutdown handler, signal trapping)
- `docker-entrypoint.sh` (new or updated: container startup script)
- `Dockerfile` (add HEALTHCHECK directive)
- `docker-compose.yml` (reference multi-node deployment)
- `dimensigon/web/config.py` (environment variable configuration mapping)

## Implementation Steps

1. Add DNS-based service discovery: on startup, resolve a configurable DNS name
   (e.g., `dimensigon-nodes.local`) to find peer IPs.
2. Implement auto-join: new node contacts discovered peers, exchanges keys, and joins the mesh.
3. Add HEALTHCHECK to Dockerfile: `HEALTHCHECK CMD curl -f http://localhost:5000/health || exit 1`.
4. Implement readiness logic: `/health` returns 503 until node has joined the mesh and
   completed initial sync.
5. Implement graceful shutdown: register SIGTERM handler in `core.py`.
6. On SIGTERM: set health to "draining", wait for active executions to complete (with timeout),
   notify peers of departure, deregister, exit.
7. Map all configuration keys to environment variables with `DM_` prefix.
8. Create `docker-entrypoint.sh`: validate environment, run migrations if needed, start app.
9. Update `docker-compose.yml` with a 3-node reference deployment using DNS discovery.
10. Create `kubernetes/` directory with Deployment, Service, and ConfigMap manifests.
11. Write tests: start 3 containers, verify auto-join, kill one, verify graceful departure.

## Verification

- `docker-compose up --scale dimensigon=3`: three nodes discover each other and form a mesh.
- `docker-compose stop dimensigon-2`: remaining nodes detect departure within 30 seconds.
- Restart the stopped node: it auto-joins without manual intervention.
- Kubernetes deployment: pods pass readiness checks and receive traffic only after mesh join.

## Breaking Changes

- `bootstrap.py` changes may affect existing bare-metal startup flows. Static peer
  configuration remains supported alongside DNS discovery.
- New environment variables with `DM_` prefix may conflict with custom env vars in
  existing deployments (unlikely but should be documented).
