# Tutorial 07: Orchestration Builder

## Overview

The Orchestration Builder is a visual interface in DM-WebManager that lets
operators design orchestrations by adding steps from the action template
palette, configuring step properties, defining execution dependencies, and
validating the resulting DAG -- all without writing JSON by hand.

This tutorial walks through the builder UI and the backing API endpoints.

## Prerequisites

- A running Dimensigon 3.0 instance.
- An operator or administrator account with access to DM-WebManager.
- At least one action template defined in the system (the builder palette draws
  from the `ActionTemplate` table).
- For API examples: `curl` and `jq`.

## 1. Accessing the Builder View

1. Log in to DM-WebManager at `http://<host>:5000/dm-webmanager/dashboard`.
2. Click **Orchestrations** in the left-hand navigation.
3. Click the **New Orchestration** button to open a blank canvas, or click the
   **Edit** icon on an existing orchestration to import it into the builder.

The builder opens in a full-screen layout with three regions:

| Region            | Description                                              |
|-------------------|----------------------------------------------------------|
| **Template Palette** | Left sidebar listing available action templates.      |
| **Canvas**           | Center area where you arrange steps and draw edges.   |
| **Properties Panel** | Right sidebar showing the selected step's properties. |

## 2. Adding Steps from the Action Template Palette

The palette lists every action template registered in Dimensigon, grouped by
action type (SHELL, ORCHESTRATION, SOFTWARE_SEND, etc.).

### To add a step

1. Find the desired template in the palette.  Use the search box at the top of
   the palette to filter by name.
2. Drag the template onto the canvas, or click it once to append a new step at
   the bottom of the graph.
3. A new node appears on the canvas with the template name. The step is
   automatically assigned a temporary ID (e.g., `s1`, `s2`).

### API: List action templates

```
GET /dm-webmanager/api/builder/action-templates
```

**curl example:**

```bash
curl -s -b cookies.txt http://localhost:5000/dm-webmanager/api/builder/action-templates | jq .
```

**Response:**

```json
[
  {
    "id": "00000000-0000-0000-000a-000000000011",
    "name": "Shell Command",
    "version": 1,
    "action_type": "SHELL"
  },
  {
    "id": "00000000-0000-0000-000a-000000000012",
    "name": "File Transfer",
    "version": 1,
    "action_type": "SHELL"
  }
]
```

## 3. Configuring Step Properties

Click a step node on the canvas to open its configuration in the Properties
Panel.

### Editable properties

| Property              | Type       | Description                                                |
|-----------------------|------------|------------------------------------------------------------|
| `action_template_id`  | UUID       | The action template this step executes. Pre-filled from the palette. |
| `target`              | `string[]` | List of server names or the special value `["all"]`.       |
| `parents`             | `string[]` | IDs of steps that must complete before this step starts.   |
| `children`            | `string[]` | IDs of steps that depend on this step.                     |
| `undo`                | `boolean`  | Whether this step is an undo (rollback) step.              |
| `stop_on_error`       | `boolean`  | Whether to halt the orchestration if this step fails.      |

### Setting the target

Enter one or more server names separated by commas, or type `all` to target
every server in the cluster. The builder validates that at least one target is
specified before saving.

### Marking a step as undo

Toggle the **Undo** switch in the Properties Panel. Undo steps run only when a
preceding step fails and the orchestration is configured with
`undo_on_error: true`. They appear on the canvas with a dashed border to
distinguish them from normal steps.

## 4. Defining Execution Dependencies

Dependencies determine the order steps execute in. A step does not start until
all of its parent steps have completed.

### Drawing edges on the canvas

1. Hover over a step node. A small connector dot appears on its bottom edge.
2. Click and drag from the connector dot to another step node.
3. An arrow is drawn from the source (parent) to the destination (child).
4. Both the `children` list of the parent and the `parents` list of the child
   are updated automatically.

### Removing an edge

Click on an edge arrow to select it, then press the **Delete** key or click the
**Remove Edge** button in the toolbar.

### Parallel steps

Steps that share no dependency edges run in parallel. To explicitly run two
steps concurrently, give them the same parent but do not connect them to each
other.

Example: steps B and C both depend on step A, but have no edge between them.
When A completes, B and C start simultaneously.

```
    A
   / \
  B   C
   \ /
    D
```

## 5. Validating the DAG

Before saving, click the **Validate** button in the toolbar. The builder sends
the current graph to the validation endpoint and reports any errors.

### What validation checks

- **Cycle detection:** The graph must be a Directed Acyclic Graph. Cycles are
  reported as errors.
- **Required fields:** Every step must have an `action_template_id`.
- **Orphan steps:** Steps with no parents and no children (isolated nodes)
  generate a warning.
- **Name required:** The orchestration must have a non-empty name.

### API: Validate

```
POST /dm-webmanager/api/builder/validate
Content-Type: application/json
```

**Request body:**

```json
{
  "name": "deploy-app",
  "steps": [
    {
      "id": "s1",
      "action_template_id": "00000000-0000-0000-000a-000000000011",
      "parents": [],
      "children": ["s2"]
    },
    {
      "id": "s2",
      "action_template_id": "00000000-0000-0000-000a-000000000012",
      "parents": ["s1"],
      "children": []
    }
  ]
}
```

**curl example:**

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/api/builder/validate \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "deploy-app",
    "steps": [
      {"id":"s1","action_template_id":"00000000-0000-0000-000a-000000000011","parents":[],"children":["s2"]},
      {"id":"s2","action_template_id":"00000000-0000-0000-000a-000000000012","parents":["s1"],"children":[]}
    ]
  }' | jq .
```

**Response (valid):**

```json
{
  "valid": true,
  "errors": []
}
```

**Response (cycle detected):**

```json
{
  "valid": false,
  "errors": [
    "Cycle detected in step dependencies"
  ]
}
```

**Response (missing required field):**

```json
{
  "valid": false,
  "errors": [
    "Step 's1' is missing required field 'action_template_id'"
  ]
}
```

## 6. Saving the Orchestration

Once validation passes, click the **Save** button. The builder submits the
orchestration definition to the server, which persists it and returns the new
orchestration ID.

### API: Save

```
POST /dm-webmanager/api/builder/save
Content-Type: application/json
```

**Request body:**

```json
{
  "name": "My New Orch",
  "description": "Built visually",
  "stop_on_error": true,
  "steps": [
    {
      "id": "s1",
      "action_template_id": "00000000-0000-0000-000a-000000000011",
      "target": ["web-server-01"],
      "parents": [],
      "children": ["s2"],
      "undo": false
    },
    {
      "id": "s2",
      "action_template_id": "00000000-0000-0000-000a-000000000012",
      "target": ["db-server-01"],
      "parents": ["s1"],
      "children": [],
      "undo": false
    }
  ]
}
```

**curl example:**

```bash
curl -s -X POST http://localhost:5000/dm-webmanager/api/builder/save \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "name": "My New Orch",
    "description": "Built visually",
    "stop_on_error": true,
    "steps": [
      {"id":"s1","action_template_id":"00000000-0000-0000-000a-000000000011","target":["web-server-01"],"parents":[],"children":["s2"],"undo":false},
      {"id":"s2","action_template_id":"00000000-0000-0000-000a-000000000012","target":["db-server-01"],"parents":["s1"],"children":[],"undo":false}
    ]
  }' | jq .
```

**Response (201 Created):**

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "name": "My New Orch",
  "version": 1,
  "message": "Orchestration saved successfully"
}
```

**Response (400 Bad Request):**

```json
{
  "error": "Orchestration name is required",
  "errors": ["Orchestration name is required"]
}
```

## 7. Importing an Existing Orchestration for Editing

### From the dashboard

1. Go to **Orchestrations** and find the orchestration you want to edit.
2. Click the **Edit** icon. The builder loads the existing orchestration's steps
   and dependencies onto the canvas.
3. Make changes and click **Save** to create a new version.

### API: Load an orchestration

Use the standard orchestration detail endpoint to retrieve the full definition
including steps and dependencies:

```
GET /api/1.0/orchestrations/<orchestration_id>
```

**curl example:**

```bash
curl -s -b cookies.txt \
  http://localhost:5000/api/1.0/orchestrations/f47ac10b-58cc-4372-a567-0e02b2c3d479 | jq .
```

The response includes the `steps` array with `parent_step_ids` and
`children_step_ids`, which the builder uses to reconstruct the graph.

## 8. Tips and Best Practices

### Naming conventions

- Use lowercase kebab-case names for orchestrations: `deploy-app`, `backup-db`,
  `restart-cluster`.
- Name steps descriptively: `checkout-code`, `run-migrations`, `restart-nginx`.

### Undo steps

- For every critical step, create a corresponding undo step that reverses the
  action (e.g., `rollback-migrations`).
- Set `undo_on_error: true` on the orchestration so undo steps run automatically
  on failure.
- Undo steps execute in reverse order of the forward steps.

### Parallel steps

- Identify steps that are independent and can run concurrently. Connect them to
  the same parent but not to each other.
- The DAG engine runs all steps whose parents have completed, maximizing
  parallelism.
- Use a fan-out / fan-in pattern: one parent fans out to N parallel steps, then
  a single join step depends on all N.

### Validation before deployment

- Always validate before saving. The validate endpoint catches cycles, missing
  fields, and structural issues that would cause runtime failures.
- Review the canvas visually. Look for disconnected subgraphs -- steps that are
  not reachable from the root may never execute.

## 9. Configuration Options

| Setting               | Default | Description                                      |
|-----------------------|---------|--------------------------------------------------|
| `MAX_STEPS_PER_ORCH`  | `100`   | Maximum number of steps allowed in a single orchestration. |
| `BUILDER_AUTO_SAVE`   | `false` | Enable auto-save drafts every 60 seconds.        |

## Related Features

- [Tutorial 06: Real-Time Monitoring](06-realtime-monitoring.md) -- watch your orchestrations execute live.
- [Tutorial 09: Execution History and Diff](09-execution-history-diff.md) -- compare runs of orchestrations built with the builder.
- [Tutorial 08: Topology Visualization](08-topology-visualization.md) -- see which servers are available as step targets.
