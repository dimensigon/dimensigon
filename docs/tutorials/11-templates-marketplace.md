# Tutorial 11: Orchestration Templates Marketplace

## Overview

The Templates Marketplace in Dimensigon 3.0 provides a shared repository of reusable orchestration templates. Users can browse, search, filter, rate, and use templates to quickly populate the orchestration builder with pre-built workflows. Templates cover common operational patterns such as deployments, monitoring setups, maintenance tasks, security hardening, and network configuration.

Each template stores a full orchestration definition as JSON, including steps, action template references, targets, and dependency chains. Using a template loads its content directly into the orchestration builder, giving you a ready-made starting point that you can customize for your environment.

---

## Prerequisites

- A running Dimensigon 3.0 instance with DM-WebManager accessible
- A user account with at least **operator** privileges
- Browser access to the DM-WebManager dashboard (`https://<server>:20194/dm-webmanager/dashboard`)

---

## Step-by-Step Instructions

### Step 1: Browse Templates in the Dashboard

1. Navigate to the DM-WebManager dashboard.
2. Click **Templates** in the main navigation bar.
3. The Templates page displays a list of available templates, each showing:
   - **Name** -- The template title
   - **Description** -- A brief summary of what the template does
   - **Category** -- The operational category (e.g., deployment, monitoring)
   - **Tags** -- Descriptive labels for filtering
   - **Rating** -- Community rating score
   - **Created** -- When the template was shared

### Step 2: Search for Templates

Use the search bar at the top of the Templates page to find templates by name, description, or tags.

**Search examples:**

| Search query | What it matches |
|---|---|
| `nginx` | Templates with "nginx" in the name, description, or tags |
| `PostgreSQL` | Templates related to PostgreSQL database operations |
| `backup` | Backup and recovery related templates |

The search is case-insensitive and matches against the template name, description, and tag values.

### Step 3: Filter by Category

Use the category dropdown or filter buttons to narrow results. The six supported categories are:

| Category | Description | Example templates |
|---|---|---|
| **deployment** | Application deployment workflows | "Deploy Nginx", "Blue-Green Deployment" |
| **monitoring** | Health checks and alerting | "Cluster Health Check", "Disk Space Monitor" |
| **maintenance** | System upkeep and cleanup | "Log Rotation", "Patch Management" |
| **security** | Security hardening and auditing | "SSL Certificate Renewal", "Firewall Rules Sync" |
| **networking** | Network configuration tasks | "DNS Update", "Load Balancer Config" |
| **custom** | User-created templates that do not fit other categories | Any custom workflow |

### Step 4: Sort by Rating

Click the **Rating** column header to sort templates by their community rating. Higher-rated templates appear first. The rating is calculated as the sum of upvotes (+1) and downvotes (-1) divided by the total number of votes.

### Step 5: Use a Template

1. Find the template you want to use.
2. Click the **Use** button on the template card.
3. The template's orchestration JSON is loaded into the orchestration builder.
4. The builder displays all steps, dependencies, and targets defined in the template.
5. Customize the template for your environment:
   - Update target server names to match your cluster
   - Adjust action template references if needed
   - Modify step parameters
   - Add or remove steps
6. Save the orchestration.

### Step 6: Rate a Template

After using a template, you can rate it to help other users:

1. Open the template detail page by clicking on the template name.
2. Click the **thumbs up** button to upvote (+1) or the **thumbs down** button to downvote (-1).
3. Multiple votes are counted (there is no per-user vote limit in the current implementation).
4. The rating updates immediately.

### Step 7: Share Your Own Template

Create a template from the UI to share your orchestrations with the team:

1. Navigate to the **Templates** page.
2. Click **Create Template** (or **Share**).
3. Fill in the template details:

   | Field | Required | Description |
   |---|---|---|
   | **Name** | Yes | A descriptive name (up to 200 characters) |
   | **Description** | No | What the template does and when to use it |
   | **Category** | Yes | One of: `deployment`, `monitoring`, `maintenance`, `security`, `networking`, `custom` |
   | **Tags** | No | A list of descriptive tags (e.g., `["nginx", "web", "deploy"]`) |
   | **JSON Content** | Yes | The full orchestration JSON definition |

4. Click **Save** to publish the template.

The template becomes immediately available to all users in the marketplace.

---

## Configuration

The templates marketplace is enabled by default in Dimensigon 3.0. No additional configuration is required.

Templates are stored in the `L_orch_template` database table with the following schema:

| Column | Type | Description |
|---|---|---|
| `id` | UUID | Unique template identifier (auto-generated) |
| `name` | String(200) | Template name |
| `description` | Text | Optional description |
| `category` | String(40) | One of the six valid categories |
| `tags` | JSON | List of string tags |
| `json_content` | JSON | Full orchestration definition |
| `rating_sum` | Integer | Sum of all vote values (+1/-1) |
| `rating_count` | Integer | Total number of votes cast |
| `created_at` | DateTime(UTC) | Timestamp of template creation |

---

## API Reference

All template API endpoints are under the DM-WebManager blueprint and require authentication.

### GET /dm-webmanager/api/templates

List orchestration templates with optional search, category filter, sort by rating, and pagination.

**Authentication:** Required

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search` | string | -- | Search term to match against name, description, and tags |
| `category` | string | -- | Filter by category (must be one of the six valid categories) |
| `sort` | string | -- | Set to `rating` to sort by rating descending |
| `page` | integer | 1 | Page number for pagination |
| `per_page` | integer | 20 | Number of templates per page |

**Response (200 OK):**

```json
{
  "templates": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Deploy Nginx",
      "description": "Deploy Nginx to target servers",
      "category": "deployment",
      "tags": ["nginx", "web", "deploy"],
      "rating": 0.75,
      "rating_sum": 3,
      "rating_count": 4,
      "created_at": "2026-04-01T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

Note: The list endpoint does **not** include `json_content` by default (to keep responses lightweight). Use the single-template endpoint to retrieve the full content.

---

### GET /dm-webmanager/api/templates/<id>

Get a single orchestration template with its full `json_content`.

**Authentication:** Required

**Response (200 OK):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Deploy Nginx",
  "description": "Deploy Nginx to target servers",
  "category": "deployment",
  "tags": ["nginx", "web", "deploy"],
  "rating": 0.75,
  "rating_sum": 3,
  "rating_count": 4,
  "created_at": "2026-04-01T10:30:00Z",
  "json_content": {
    "name": "Deploy Nginx",
    "steps": [
      {
        "action_template_id": "at-1",
        "action_name": "Install Nginx",
        "target": ["web1"]
      },
      {
        "action_template_id": "at-2",
        "action_name": "Start Nginx",
        "target": ["web1"],
        "parents": ["step-1"]
      }
    ]
  }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `404` | Template not found |

---

### POST /dm-webmanager/api/templates

Create (share) a new orchestration template.

**Authentication:** Required

**Request Body:**

```json
{
  "name": "Deploy Nginx",
  "description": "Deploy Nginx to target servers with health checks",
  "category": "deployment",
  "tags": ["nginx", "web", "deploy"],
  "json_content": {
    "name": "Deploy Nginx",
    "steps": [
      {
        "action_template_id": "at-1",
        "action_name": "Install Nginx",
        "target": ["web1"]
      },
      {
        "action_template_id": "at-2",
        "action_name": "Start Nginx",
        "target": ["web1"],
        "parents": ["step-1"]
      },
      {
        "action_template_id": "at-3",
        "action_name": "Health Check",
        "target": ["web1"],
        "parents": ["step-2"]
      }
    ]
  }
}
```

**Validation rules:**

| Field | Rule |
|---|---|
| `name` | Required, must not be empty |
| `category` | Required, must be one of: `deployment`, `monitoring`, `maintenance`, `security`, `networking`, `custom` |
| `json_content` | Required, must not be null |
| `description` | Optional |
| `tags` | Optional, defaults to empty list |

**Response (201 Created):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Deploy Nginx",
  "description": "Deploy Nginx to target servers with health checks",
  "category": "deployment",
  "tags": ["nginx", "web", "deploy"],
  "rating": 0,
  "rating_sum": 0,
  "rating_count": 0,
  "created_at": "2026-04-07T14:00:00Z",
  "json_content": { ... }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Name is empty, invalid category, or json_content is null |

---

### POST /dm-webmanager/api/templates/<id>/rate

Rate a template with a thumbs up or thumbs down.

**Authentication:** Required

**Request Body:**

```json
{
  "rating": 1
}
```

| Value | Meaning |
|---|---|
| `1` | Thumbs up (upvote) |
| `-1` | Thumbs down (downvote) |

**Response (200 OK):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "rating": 0.75,
  "rating_sum": 3,
  "rating_count": 4
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `400` | Rating value is not `1` or `-1` |
| `404` | Template not found |

---

### POST /dm-webmanager/api/templates/<id>/use

Load a template's orchestration content for use in the builder. Returns the template metadata along with the full `json_content`.

**Authentication:** Required

**Request Body:** None required.

**Response (200 OK):**

```json
{
  "template_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Deploy Nginx",
  "json_content": {
    "name": "Deploy Nginx",
    "steps": [
      {
        "action_template_id": "at-1",
        "action_name": "Install Nginx",
        "target": ["web1"]
      },
      {
        "action_template_id": "at-2",
        "action_name": "Start Nginx",
        "target": ["web1"],
        "parents": ["step-1"]
      }
    ]
  }
}
```

**Error Responses:**

| Status | Condition |
|---|---|
| `404` | Template not found |

---

## curl Examples

### Log in and capture session cookie

```bash
curl -k -c cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your_password"}'
```

### List all templates

```bash
curl -k -b cookies.txt \
  https://localhost:20194/dm-webmanager/api/templates
```

### Search templates by name

```bash
curl -k -b cookies.txt \
  "https://localhost:20194/dm-webmanager/api/templates?search=nginx"
```

### Filter by category

```bash
curl -k -b cookies.txt \
  "https://localhost:20194/dm-webmanager/api/templates?category=deployment"
```

### Search and filter combined with pagination

```bash
curl -k -b cookies.txt \
  "https://localhost:20194/dm-webmanager/api/templates?search=deploy&category=deployment&page=1&per_page=10"
```

### Sort by rating

```bash
curl -k -b cookies.txt \
  "https://localhost:20194/dm-webmanager/api/templates?sort=rating"
```

### Get a specific template with full content

```bash
curl -k -b cookies.txt \
  https://localhost:20194/dm-webmanager/api/templates/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### Create a new template

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cluster Health Check",
    "description": "Check disk, memory, and CPU on all servers",
    "category": "monitoring",
    "tags": ["health", "monitoring", "cluster"],
    "json_content": {
      "name": "Cluster Health Check",
      "steps": [
        {
          "action_template_id": "at-disk-check",
          "action_name": "Check Disk Space",
          "target": ["all"]
        },
        {
          "action_template_id": "at-mem-check",
          "action_name": "Check Memory Usage",
          "target": ["all"]
        },
        {
          "action_template_id": "at-cpu-check",
          "action_name": "Check CPU Load",
          "target": ["all"]
        }
      ]
    }
  }'
```

### Rate a template (upvote)

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/templates/a1b2c3d4-e5f6-7890-abcd-ef1234567890/rate \
  -H "Content-Type: application/json" \
  -d '{"rating": 1}'
```

### Rate a template (downvote)

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/templates/a1b2c3d4-e5f6-7890-abcd-ef1234567890/rate \
  -H "Content-Type: application/json" \
  -d '{"rating": -1}'
```

### Use a template (load into builder)

```bash
curl -k -b cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/api/templates/a1b2c3d4-e5f6-7890-abcd-ef1234567890/use
```

### Full workflow: create, rate, and use a template

```bash
# Step 1: Log in
curl -k -c cookies.txt -X POST \
  https://localhost:20194/dm-webmanager/login \
  -H "Content-Type: application/json" \
  -d '{"username": "root", "password": "your_password"}'

# Step 2: Create a template
TEMPLATE_ID=$(curl -k -b cookies.txt -s -X POST \
  https://localhost:20194/dm-webmanager/api/templates \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Log Rotation",
    "description": "Rotate and compress logs on all servers",
    "category": "maintenance",
    "tags": ["logs", "maintenance", "cleanup"],
    "json_content": {
      "name": "Log Rotation",
      "steps": [
        {"action_template_id": "at-rotate", "action_name": "Rotate Logs", "target": ["all"]},
        {"action_template_id": "at-compress", "action_name": "Compress Old Logs", "target": ["all"], "parents": ["step-1"]}
      ]
    }
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Created template: $TEMPLATE_ID"

# Step 3: Upvote the template
curl -k -b cookies.txt -X POST \
  "https://localhost:20194/dm-webmanager/api/templates/$TEMPLATE_ID/rate" \
  -H "Content-Type: application/json" \
  -d '{"rating": 1}'

# Step 4: Use the template
curl -k -b cookies.txt -X POST \
  "https://localhost:20194/dm-webmanager/api/templates/$TEMPLATE_ID/use"
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Template list is empty | No templates have been created yet. Create your first template using the Create Template form or API. |
| Search returns no results | Try broader search terms or remove category filters. Search matches against name, description, and tags. |
| 400 error on create | Check that `name` is not empty, `category` is one of the six valid values, and `json_content` is not null. |
| 400 error on rate | The `rating` value must be exactly `1` or `-1`. Other values are rejected. |
| Rating shows 0 | No votes have been cast yet, or upvotes and downvotes cancel out. |
| Template JSON does not load in builder | Ensure the `json_content` follows the expected orchestration format with steps, action template references, and targets. |

---

**Document Version**: 1.0.0
**Last Updated**: 2026-04-07
**Dimensigon Version**: 3.0
