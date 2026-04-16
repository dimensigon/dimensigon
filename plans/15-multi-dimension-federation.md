# Multi-Dimension Federation

- **Priority:** 15
- **Category:** New Feature
- **Effort:** 7-10 days
- **Dependencies:** #1 (SQLAlchemy 2.x Migration), #2 (Security Layer Simplification)

## Context

Currently each dimension operates in isolation. Organizations with multiple environments
(production, staging, DR) cannot orchestrate across them or share templates. Federation
enables cross-dimension execution for disaster recovery scenarios, unified template libraries,
and centralized monitoring of all dimensions from a single pane of glass.

## Scope

- Dimension peering: establish trust between two dimensions via key exchange.
- Cross-dimension orchestration: execute steps on nodes in a remote dimension.
- Shared template library: subscribe to templates from a peer dimension.
- Cross-dimension routing: find optimal paths when direct routes are unavailable.
- Federation dashboard: view peer dimensions, their health, and shared resources.
- Security: all cross-dimension traffic uses full encryption regardless of SECURIZER_MODE.

## Files to Modify

- `dimensigon/use_cases/federation.py` (new: peering, cross-dimension dispatch)
- `dimensigon/domain/entities/federation.py` (new: Peer, FederationLink entities)
- `dimensigon/web/api_2_0/federation.py` (new: peering API, cross-dimension proxy)
- `dimensigon/web/decorators.py` (enforce encryption for federated requests)
- `dimensigon/use_cases/routing.py` (extend routing to include cross-dimension hops)
- DB migration for federation tables.

## Implementation Steps

1. Define `Peer` entity: id, name, dimension_id, endpoint, public_key, status, last_seen.
2. Define `FederationLink` entity: peer_id, link_type (execution|templates|routing), active.
3. Create DB migration.
4. Build peering handshake: POST request exchange with mutual key verification.
5. Implement cross-dimension request proxy: forward requests to peer's API with full encryption.
6. Extend routing algorithm to consider cross-dimension hops with configurable cost penalty.
7. Build template subscription: pull templates from peer on schedule, flag as "federated".
8. Build federation dashboard page: list peers, health status, link types, latency.
9. Add security enforcement: reject plain-mode for any cross-dimension traffic.
10. Write integration tests: two dimensions, peer them, execute cross-dimension orchestration.

## Verification

- Peer two test dimensions: handshake completes, both show each other as "connected".
- Execute an orchestration that targets a node in the peer dimension: completes successfully.
- Subscribe to peer templates: templates appear in local library marked as federated.
- Revoke peering: cross-dimension requests are rejected immediately.

## Breaking Changes

- Routing cost calculations change when federation is enabled, which may alter route selection
  for existing intra-dimension traffic if cost thresholds overlap.
