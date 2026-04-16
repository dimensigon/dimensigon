# Visual Orchestration Builder

- **Priority:** 7
- **Category:** WebManager
- **Effort:** 5-7 days
- **Dependencies:** #5 (Authentication Flow Rework)

## Context

Building orchestrations currently requires hand-writing JSON, which is error-prone and has a
steep learning curve. A visual drag-and-drop DAG editor lets operators construct orchestrations
graphically, lowering the barrier to entry and reducing configuration mistakes.

## Scope

- Drag-and-drop canvas where users can place step nodes from a palette.
- Node palette with all action types: shell, script, file transfer, conditional, etc.
- Arrow connections between nodes to define execution dependencies.
- Click a node to open an editor panel: code/command, target server, input schema, timeout.
- Auto-generate valid orchestration JSON from the visual graph.
- Import existing orchestration JSON and render it as a graph for editing.
- DAG validation: detect cycles, warn on disconnected nodes, verify required fields.
- Save button that PUTs the generated JSON to the orchestration API.

## Files to Modify

- `templates/admin/dashboard.html` (builder section within the SPA)
- `templates/admin/orch-builder.html` (new: standalone builder component if needed)
- `dimensigon/web/admin/routes.py` (save/load endpoints for builder state)
- `dimensigon/web/api_1_0/resources/orchestration.py` (ensure PUT accepts builder output)

## Implementation Steps

1. Evaluate and integrate a JS DAG editor library (e.g., rete.js, react-flow, or custom d3).
2. Build the node palette UI with categorized action types.
3. Implement drag-from-palette-to-canvas functionality.
4. Implement arrow drawing between node ports for dependency definition.
5. Build the node editor side panel: fields vary by action type.
6. Implement JSON generation: walk the graph, produce orchestration JSON.
7. Implement JSON import: parse orchestration, lay out nodes using dagre auto-layout.
8. Add DAG validation (cycle detection via topological sort, required field checks).
9. Wire save button to `PUT /api/v1.0/orchestrations/<id>`.
10. Write tests: build a 5-step DAG visually, export JSON, verify structure.

## Verification

- Drag 3 nodes onto canvas, connect them, fill in fields, click Save: valid JSON created.
- Import an existing complex orchestration: graph renders with correct dependencies.
- Attempt to create a cycle: validation prevents save with a clear error message.
- Generated JSON matches the schema expected by the execution engine.

## Breaking Changes

- None. The builder is a new UI surface; existing JSON-based workflows remain fully supported.
