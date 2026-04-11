# Tutorial 08: Topology Visualization

## Overview

The Topology view in DM-WebManager renders a live graph of every server
(node) in the Dimensigon cluster, their network gates, routes, and reachability
status. Operators use this view to understand cluster layout, diagnose
connectivity issues, and verify that target servers are reachable before
launching orchestrations.

## Prerequisites

- A running Dimensigon 3.0 cluster with two or more nodes.
- An operator or administrator account.
- Access to DM-WebManager at `http://<host>:5000/dm-webmanager/dashboard`.
- For API examples: `curl` and `jq`.

## 1. Accessing the Topology View

1. Log in to DM-WebManager.
2. Click **Topology** in the left-hand navigation menu.
3. The topology graph loads and renders all servers and their routes.

The graph is rendered using vis.js and supports zoom, pan, and click
interactions.

## 2. Node Color Codes

Each server node in the graph is colored to indicate its status:

| Color      | Meaning                                                    |
|------------|------------------------------------------------------------|
| **Cyan**   | The local node -- the server you are connected to (`me: true`). |
| **Green**  | A remote node that is reachable (has at least one route with finite cost). |
| **Grey**   | A remote node that is unreachable (no route or route cost is null). |

### How reachability is determined

A node is considered reachable if there exists at least one `Route` entry with a
finite `cost` value pointing to it. The local node (where Dimensigon is running)
is always shown in cyan regardless of route information.

## 3. Searching and Filtering Nodes

For large clusters, use the search bar at the top of the Topology view:

- Type a server name or IP address to highlight matching nodes.
- Non-matching nodes are dimmed but remain visible.
- Clear the search to restore the full view.

Filtering options:

| Filter          | Description                                |
|-----------------|--------------------------------------------|
| **All**         | Show every node (default).                 |
| **Reachable**   | Show only green and cyan nodes.            |
| **Unreachable** | Show only grey nodes.                      |

## 4. Click-to-Inspect Detail Panel

Click on any node in the graph to open the detail panel on the right side of
the screen. The detail panel shows:

### Server information

| Field        | Description                              |
|--------------|------------------------------------------|
| **Name**     | Server hostname.                         |
| **ID**       | Server UUID.                             |
| **IP/DNS**   | The `dns_or_ip` address.                 |
| **Port**     | Dimensigon listen port (default: 20194). |
| **Local**    | Whether this is the local node (`me`).   |

### Gates

A table listing every gate (network endpoint) for the selected server:

| Column    | Description                     |
|-----------|---------------------------------|
| **IP**    | Gate IP address or DNS name.    |
| **Port**  | Gate port number.               |

### Routes

A table listing every known route to (or through) the selected server:

| Column          | Description                                           |
|-----------------|-------------------------------------------------------|
| **Destination** | The server this route reaches.                        |
| **Proxy**       | The gate or intermediate server used to reach it.     |
| **Cost**        | Route cost (0 = direct neighbor, higher = more hops). |

## 5. Auto-Refresh and Manual Refresh

The topology view supports two refresh modes:

### Auto-refresh

Auto-refresh is enabled by default and polls the topology API every 30 seconds.
A small indicator in the top-right corner shows the countdown to the next
refresh. Toggle auto-refresh on or off with the **Auto** button.

### Manual refresh

Click the **Refresh** button (circular arrow icon) in the toolbar to fetch the
latest topology data immediately. This is useful after making infrastructure
changes such as adding a new server or updating routes.

## 6. API Reference

### GET /dm-webmanager/api/topology

Returns the full cluster topology as a list of nodes and edges.

**Authentication:** Requires a valid session (JWT cookie or Authorization header).

**curl example:**

```bash
curl -s -b cookies.txt http://localhost:5000/dm-webmanager/api/topology | jq .
```

### Response format

```json
{
  "nodes": [
    {
      "id": "00000000-0000-0000-0001-000000000001",
      "name": "node-local",
      "dns_or_ip": "10.0.0.1",
      "port": 20194,
      "me": true,
      "gates": [
        {
          "ip": "10.0.0.1",
          "port": 20194
        }
      ]
    },
    {
      "id": "00000000-0000-0000-0001-000000000002",
      "name": "node-remote",
      "dns_or_ip": "10.0.0.2",
      "port": 20194,
      "me": false,
      "gates": [
        {
          "ip": "10.0.0.2",
          "port": 20194
        }
      ]
    }
  ],
  "edges": [
    {
      "destination_id": "00000000-0000-0000-0001-000000000002",
      "proxy_server_id": null,
      "gate_ip": "10.0.0.2",
      "gate_port": 20194,
      "cost": 0
    }
  ]
}
```

### Response fields

**nodes[] fields:**

| Field      | Type       | Description                           |
|------------|------------|---------------------------------------|
| `id`       | `string`   | Server UUID.                          |
| `name`     | `string`   | Server name.                          |
| `dns_or_ip`| `string`   | Server address.                       |
| `port`     | `integer`  | Dimensigon listen port.               |
| `me`       | `boolean`  | Whether this is the local node.       |
| `gates`    | `object[]` | List of network endpoints (ip, port). |

**edges[] fields:**

| Field              | Type      | Description                                       |
|--------------------|-----------|---------------------------------------------------|
| `destination_id`   | `string`  | UUID of the destination server.                   |
| `proxy_server_id`  | `string`  | UUID of the proxy server (null for direct routes). |
| `gate_ip`          | `string`  | IP of the gate used for this route.               |
| `gate_port`        | `integer` | Port of the gate used for this route.             |
| `cost`             | `integer` | Route cost. 0 means direct neighbor.              |

### Error responses

| Status | Meaning                                          |
|--------|--------------------------------------------------|
| 302    | Not authenticated -- redirected to login page.   |
| 401    | Invalid or expired token.                        |
| 500    | Internal server error (check Dimensigon logs).   |

## 7. Understanding the Graph Layout

The vis.js graph uses a hierarchical layout by default:

- The **local node** (cyan) is placed at the center.
- **Direct neighbors** (cost = 0) are placed in the first ring.
- **Multi-hop nodes** (cost > 0) are placed in outer rings, with distance
  proportional to route cost.

Edges are drawn as arrows from the local node toward destinations. Thicker edges
indicate lower cost (better routes). Dashed edges indicate high-cost or
unreliable routes.

## 8. Common Use Cases

### Before launching an orchestration

Check the topology to confirm that all target servers are green (reachable).
If a target appears grey, investigate the route before proceeding.

### After adding a new server to the cluster

1. Register the server via the Dimensigon CLI or API.
2. Open the Topology view and click **Refresh**.
3. Verify the new node appears and routes are established.

### Diagnosing connectivity issues

1. Open the Topology view.
2. Look for grey nodes -- these servers are unreachable.
3. Click the grey node to inspect its gates and routes.
4. Check whether the gate IP and port are correct.
5. Verify network connectivity between the local node and the target.

## 9. Configuration Options

| Setting                       | Default | Description                             |
|-------------------------------|---------|-----------------------------------------|
| `TOPOLOGY_REFRESH_INTERVAL`   | `30`    | Auto-refresh interval in seconds.       |
| `TOPOLOGY_MAX_NODES_DISPLAY`  | `200`   | Max nodes rendered before grouping.     |

## Related Features

- [Tutorial 06: Real-Time Monitoring](06-realtime-monitoring.md) -- see which nodes are executing steps.
- [Tutorial 07: Orchestration Builder](07-orchestration-builder.md) -- select target servers when building orchestrations.
- [Tutorial 24: Prometheus Metrics](24-prometheus-metrics.md) -- monitor `dm_cluster_nodes_alive`.
