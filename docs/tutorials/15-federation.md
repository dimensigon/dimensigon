# Tutorial 15: Multi-Dimension Federation

Connect multiple Dimensigon dimensions for cross-environment orchestration, shared templates, and unified management.

---

## Overview

Federation enables separate Dimensigon dimensions to establish trust and work together. A "dimension" is an independent Dimensigon deployment -- typically corresponding to an environment like production, staging, or disaster recovery. With federation, you can execute orchestrations across dimensions, share template libraries, and route traffic through peer dimensions when direct routes are unavailable.

All cross-dimension traffic is fully encrypted regardless of the `SECURIZER_MODE` setting on either side.

## Prerequisites

- Two or more Dimensigon 3.0 instances, each running as an independent dimension
- Network connectivity between the dimensions (the peering endpoint must be reachable)
- Administrator access on both dimensions
- SQLAlchemy 2.x migration completed (Feature 01)
- Security Layer Simplification applied (Feature 02)

---

## Key Concepts

### Dimensions

A dimension is a self-contained Dimensigon deployment with its own servers, orchestrations, vault, and configuration. Each dimension has a unique dimension ID.

### Peers

A peer is a remote dimension that your dimension has established a trust relationship with. Peers can exchange orchestration commands, share templates, and provide routing paths.

### Federation Links

Each peer relationship includes one or more link types that define what is shared:

| Link Type | Description |
|-----------|-------------|
| `execution` | Execute orchestration steps on servers in the peer dimension |
| `templates` | Subscribe to and use orchestration templates from the peer dimension |
| `routing` | Include the peer dimension's network paths in routing calculations |

---

## Peering Lifecycle

Federation peering follows a four-state lifecycle:

```
initiate --> accept --> connected --> revoke
                           |
                           +--> revoke
```

| State | Description |
|-------|-------------|
| `initiated` | One dimension has sent a peering request. Waiting for the other side to accept. |
| `connected` | Both sides have accepted. Cross-dimension operations are active. |
| `revoked` | One or both sides have revoked the peering. All cross-dimension operations stop immediately. |

---

## Step-by-Step: Establishing a Federation Peer

This walkthrough connects two dimensions: **production** and **staging**.

### Step 1: Initiate Peering (from Production)

On the production dimension, send a peering request to the staging dimension.

**POST** `/dm-webmanager/api/federation/peers`

```bash
curl -X POST https://prod.example.com:5000/dm-webmanager/api/federation/peers \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "staging",
    "endpoint": "https://staging.example.com:5000"
  }'
```

#### Response (201 Created)

```json
{
  "id": "peer-a1b2c3d4",
  "name": "staging",
  "endpoint": "https://staging.example.com:5000",
  "status": "initiated",
  "direction": "outbound",
  "initiated_at": "2026-04-07T14:00:00Z",
  "links": []
}
```

At this point, the staging dimension sees an inbound peering request.

### Step 2: Accept Peering (from Staging)

On the staging dimension, list pending peering requests and accept the one from production.

First, list peers to find the request:

```bash
curl -X GET https://staging.example.com:5000/dm-webmanager/api/federation/peers \
  -H "Authorization: Bearer $STAGING_TOKEN" | jq .
```

```json
{
  "peers": [
    {
      "id": "peer-e5f6g7h8",
      "name": "production",
      "endpoint": "https://prod.example.com:5000",
      "status": "initiated",
      "direction": "inbound",
      "initiated_at": "2026-04-07T14:00:00Z"
    }
  ]
}
```

Accept the request:

**POST** `/dm-webmanager/api/federation/peers/<id>/accept`

```bash
curl -X POST https://staging.example.com:5000/dm-webmanager/api/federation/peers/peer-e5f6g7h8/accept \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (200 OK)

```json
{
  "id": "peer-e5f6g7h8",
  "name": "production",
  "endpoint": "https://prod.example.com:5000",
  "status": "connected",
  "direction": "inbound",
  "connected_at": "2026-04-07T14:05:00Z",
  "links": [
    {"type": "execution", "active": true},
    {"type": "templates", "active": true},
    {"type": "routing", "active": true}
  ]
}
```

Both dimensions are now connected. By default, all three link types are activated on acceptance.

### Step 3: Verify Connection (from Either Side)

Check the peer status from the production side:

```bash
curl -X GET https://prod.example.com:5000/dm-webmanager/api/federation/peers/peer-a1b2c3d4 \
  -H "Authorization: Bearer $PROD_TOKEN" | jq .
```

```json
{
  "id": "peer-a1b2c3d4",
  "name": "staging",
  "endpoint": "https://staging.example.com:5000",
  "dimension_id": "dim-staging-001",
  "status": "connected",
  "direction": "outbound",
  "connected_at": "2026-04-07T14:05:00Z",
  "last_seen": "2026-04-07T14:06:12Z",
  "latency_ms": 23,
  "links": [
    {"type": "execution", "active": true},
    {"type": "templates", "active": true},
    {"type": "routing", "active": true}
  ]
}
```

---

## Listing All Peers

**GET** `/dm-webmanager/api/federation/peers`

Returns all peers with their current status.

```bash
curl -X GET https://prod.example.com:5000/dm-webmanager/api/federation/peers \
  -H "Authorization: Bearer $PROD_TOKEN" | jq .
```

```json
{
  "peers": [
    {
      "id": "peer-a1b2c3d4",
      "name": "staging",
      "endpoint": "https://staging.example.com:5000",
      "status": "connected",
      "last_seen": "2026-04-07T14:06:12Z",
      "links": [
        {"type": "execution", "active": true},
        {"type": "templates", "active": true},
        {"type": "routing", "active": true}
      ]
    },
    {
      "id": "peer-i9j0k1l2",
      "name": "dr-site",
      "endpoint": "https://dr.example.com:5000",
      "status": "connected",
      "last_seen": "2026-04-07T14:05:45Z",
      "links": [
        {"type": "execution", "active": true},
        {"type": "templates", "active": false},
        {"type": "routing", "active": true}
      ]
    }
  ],
  "total": 2
}
```

---

## Getting Peer Details

**GET** `/dm-webmanager/api/federation/peers/<id>`

Returns detailed information about a specific peer, including link status, latency, and dimension metadata.

```bash
curl -X GET https://prod.example.com:5000/dm-webmanager/api/federation/peers/peer-a1b2c3d4 \
  -H "Authorization: Bearer $PROD_TOKEN" | jq .
```

The response format is shown in Step 3 of the peering walkthrough above.

---

## Revoking a Peer

**POST** `/dm-webmanager/api/federation/peers/<id>/revoke`

Revoke an active peering. This immediately stops all cross-dimension operations. The revocation is propagated to the remote dimension.

```bash
curl -X POST https://prod.example.com:5000/dm-webmanager/api/federation/peers/peer-a1b2c3d4/revoke \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (200 OK)

```json
{
  "id": "peer-a1b2c3d4",
  "name": "staging",
  "status": "revoked",
  "revoked_at": "2026-04-07T15:00:00Z",
  "revoked_by": "admin",
  "message": "Peering revoked. All cross-dimension operations stopped."
}
```

After revocation:

- Cross-dimension execution requests are rejected immediately.
- Shared templates from the revoked peer are no longer accessible (but previously imported copies remain).
- Routing paths through the revoked peer are removed from calculations.

---

## Federation Link Types in Detail

### Execution Links

With execution links active, orchestration steps can target servers in the peer dimension. When you run an orchestration, you can include remote servers in the target mapping:

```bash
dm> run deploy_app --target web-01 --target staging:web-staging-01
```

The prefix `staging:` tells the system to route the step through the federation link to the staging dimension's `web-staging-01` server.

### Template Links

With template links active, orchestration templates published in the peer dimension appear in your local template browser with a "federated" badge. You can use these templates directly or clone them into your local library.

### Routing Links

With routing links active, the dimension's routing algorithm considers paths through the peer dimension when calculating optimal routes. This is useful when a direct route to a server is unavailable but a path exists through a federated peer.

---

## Security

Federation enforces strict security policies:

- **Full encryption**: All cross-dimension traffic uses TLS with mutual certificate verification, regardless of either dimension's `SECURIZER_MODE` setting. Plaintext federation is never permitted.
- **Key exchange**: During the peering handshake, both dimensions exchange public keys. All subsequent requests are signed and verified.
- **Scoped access**: Federation links only grant the specific capabilities enabled (execution, templates, routing). A peer with only template links cannot execute commands on your servers.
- **Instant revocation**: Revoking a peer immediately invalidates its keys. In-flight requests from the revoked peer are rejected.

---

## Federation Dashboard View

The WebManager dashboard includes a federation panel accessible from the sidebar under **Federation**.

The panel shows:

- A list of all peers with their status (connected, initiated, revoked)
- Health indicators: latency, last seen timestamp, link types
- A world/network map visualization showing peer connections
- Quick actions: accept, revoke, view details

---

## Use Cases

### Production/Staging Peering

Connect production and staging dimensions to test orchestrations in staging before promoting them to production. Use template links to share a unified orchestration library.

### Disaster Recovery Failover

Connect a primary dimension to a DR dimension with execution and routing links. If the primary dimension's routes degrade, traffic can be routed through the DR dimension. In a full failover scenario, orchestrations can be executed directly on DR servers.

### Shared Template Library

A central "templates" dimension publishes validated orchestration templates. Production, staging, and development dimensions peer with it using template-only links to access a curated library without granting execution access.

---

## Complete curl Lifecycle Example

This script demonstrates the full peering lifecycle between two dimensions.

```bash
# === Setup: Authenticate on both dimensions ===

PROD_TOKEN=$(curl -s -X POST https://prod.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "prod_password"}' \
  | jq -r '.access_token')

STAGING_TOKEN=$(curl -s -X POST https://staging.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "staging_password"}' \
  | jq -r '.access_token')

# === Step 1: Initiate peering from production ===

echo "=== Initiating peering ==="
PEER_RESPONSE=$(curl -s -X POST https://prod.example.com:5000/dm-webmanager/api/federation/peers \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "staging", "endpoint": "https://staging.example.com:5000"}')

echo "$PEER_RESPONSE" | jq .
PROD_PEER_ID=$(echo "$PEER_RESPONSE" | jq -r '.id')

# === Step 2: Accept peering from staging ===

echo "=== Listing pending requests on staging ==="
STAGING_PEERS=$(curl -s -X GET https://staging.example.com:5000/dm-webmanager/api/federation/peers \
  -H "Authorization: Bearer $STAGING_TOKEN")

echo "$STAGING_PEERS" | jq .
STAGING_PEER_ID=$(echo "$STAGING_PEERS" | jq -r '.peers[0].id')

echo "=== Accepting peering ==="
curl -s -X POST "https://staging.example.com:5000/dm-webmanager/api/federation/peers/$STAGING_PEER_ID/accept" \
  -H "Authorization: Bearer $STAGING_TOKEN" \
  -H "Content-Type: application/json" | jq .

# === Step 3: Verify connection ===

echo "=== Verifying from production ==="
curl -s -X GET "https://prod.example.com:5000/dm-webmanager/api/federation/peers/$PROD_PEER_ID" \
  -H "Authorization: Bearer $PROD_TOKEN" | jq .

echo "=== Verifying from staging ==="
curl -s -X GET "https://staging.example.com:5000/dm-webmanager/api/federation/peers/$STAGING_PEER_ID" \
  -H "Authorization: Bearer $STAGING_TOKEN" | jq .

# === Step 4: Use the federation (run cross-dimension orchestration) ===

echo "=== Running cross-dimension health check ==="
curl -s -X POST https://prod.example.com:5000/dm-webmanager/api/ai/execute \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "orchestration_id": "orch-health-001",
    "targets": ["web-01", "staging:web-staging-01"],
    "params": {},
    "confirmed": true
  }' | jq .

# === Step 5: Revoke peering (when no longer needed) ===

echo "=== Revoking peering ==="
curl -s -X POST "https://prod.example.com:5000/dm-webmanager/api/federation/peers/$PROD_PEER_ID/revoke" \
  -H "Authorization: Bearer $PROD_TOKEN" \
  -H "Content-Type: application/json" | jq .

# === Verify revocation ===

echo "=== Verifying revocation ==="
curl -s -X GET "https://prod.example.com:5000/dm-webmanager/api/federation/peers/$PROD_PEER_ID" \
  -H "Authorization: Bearer $PROD_TOKEN" | jq '.status'
# Output: "revoked"
```

---

## Tips

- **Start with template-only links**: When first peering with a new dimension, enable only template links. Add execution and routing links after you are confident in the connection.
- **Monitor latency**: The federation dashboard shows peer latency. High latency (>500ms) can affect cross-dimension orchestration performance.
- **Revoke immediately on compromise**: If a peer dimension is compromised, revoke the peering instantly from your side. Revocation takes effect in real time.
- **Routing cost**: Cross-dimension routing hops carry a configurable cost penalty. The routing algorithm prefers intra-dimension paths unless they are unavailable or significantly slower.
- **Audit trail**: All federation actions (initiate, accept, revoke, cross-dimension executions) are recorded in the audit log (Feature 16).

---

## Next Steps

- [Tutorial 16: Audit Log](16-audit-log.md) -- Track all federation and system actions
- [Tutorial 08: Server Topology Visualization](08-server-topology.md) -- Visualize servers across federated dimensions
