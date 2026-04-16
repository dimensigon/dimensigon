# Tutorial 20: Training Data Feedback Loop

Manage AI training by reviewing, approving, and rejecting AI-generated orchestration candidates.

---

## Overview

The Training Data Feedback Loop continuously improves Dimensigon's AI by capturing successful AI-generated orchestrations and incorporating them into the training dataset. When an AI-created orchestration runs successfully multiple times, it becomes a training candidate. Administrators review these candidates for quality, approve or reject them, and approved candidates are added to the training set for future model improvement.

This tutorial covers the feedback loop mechanics, the quality scoring system, the review queue, and the API for managing candidates.

## Prerequisites

- Dimensigon 3.0 installed with AI features enabled (Feature 17: Context-Aware AI)
- Administrator role (the review queue requires admin access)
- At least one AI-generated orchestration that has been executed (to see candidates in the queue)

---

## How the Feedback Loop Works

The feedback loop operates in three stages:

### Stage 1: AI Generates an Orchestration

When a user creates an orchestration through the AI assistant (via the dashboard or DShell), the system tags it with `source=ai_generated` metadata. This tag is invisible to the user but allows the system to track AI-created content separately from manually authored orchestrations.

### Stage 2: Successful Execution Threshold

Each time an AI-generated orchestration executes successfully (exit code 0 on all steps), its internal success counter increments. When the counter reaches the configured threshold (default: 3 successful runs), the orchestration automatically becomes a training candidate with status `pending`.

```
Execution 1: health_check_ai ... SUCCESS  (count: 1/3)
Execution 2: health_check_ai ... SUCCESS  (count: 2/3)
Execution 3: health_check_ai ... SUCCESS  (count: 3/3) --> Candidate created
```

The threshold is configurable in the Dimensigon settings:

```yaml
# dimensigon.yml
ai:
  training:
    success_threshold: 3    # Number of successful runs before candidacy
```

### Stage 3: Candidate Appears in Review Queue

Once the threshold is reached, the candidate appears in the administrator review queue with a quality score. Administrators review the candidate and approve or reject it.

---

## Quality Scoring

Each candidate receives a quality score between 0.0 and 1.0, calculated from five criteria worth 0.2 points each:

| Criterion | Points | What It Checks |
|-----------|--------|----------------|
| Error handling | 0.2 | Steps include error handling (e.g., `on_error`, conditional logic, or `set -e`) |
| Timeout configuration | 0.2 | Steps have explicit timeout values defined |
| Variable usage | 0.2 | Uses variables and parameters instead of hardcoded values (IPs, paths, credentials) |
| Documentation | 0.2 | Orchestration has a description and steps have meaningful names |
| Reasonable step count | 0.2 | Total step count is between 1 and 20 (not empty, not excessively complex) |

### Score Interpretation

| Score Range | Meaning |
|-------------|---------|
| 0.8 - 1.0 | High quality. Likely safe to approve. |
| 0.6 - 0.8 | Acceptable. Review the missing criteria before approving. |
| 0.4 - 0.6 | Marginal. Significant quality gaps. Consider rejecting or requesting improvements. |
| 0.0 - 0.4 | Low quality. Likely should be rejected. |

### Example Scoring

An AI-generated orchestration `deploy_app_ai` with the following properties:

- Has `on_error: rollback` on deployment steps (error handling: 0.2)
- Has `timeout: 300` on all steps (timeout: 0.2)
- Uses `{{ app_version }}` variable but hardcodes the path `/opt/app` (variable usage: 0.1)
- Has a description but step names are generic like "step_1" (documentation: 0.1)
- Has 5 steps (reasonable step count: 0.2)

**Total score: 0.8**

---

## Using the Review Queue in the Dashboard

### Step 1: Access the Review Queue

1. Log in as an administrator.
2. Navigate to **AI** in the sidebar, then select **Training Queue**.
3. The queue displays pending candidates sorted by quality score (highest first).

### Step 2: Review a Candidate

Click on a candidate to see its details:

- **Orchestration name** and description
- **Quality score** with a breakdown of each criterion
- **Success count** (how many times it ran successfully)
- **Orchestration definition** (full step-by-step preview)
- **Execution history** (links to the successful runs)

### Step 3: Approve or Reject

- Click **Approve** to add the orchestration to the training dataset.
- Click **Reject** to discard it. Rejected candidates are not re-queued unless they are modified and reach the success threshold again.

---

## API Reference

All training management endpoints require administrator access (JWT token from an admin user).

### List the Review Queue

**GET** `/dm-webmanager/api/training/queue`

Returns all pending training candidates, sorted by quality score descending.

#### Request

```bash
curl -X GET https://dm.example.com:5000/dm-webmanager/api/training/queue \
  -H "Authorization: Bearer $TOKEN"
```

#### Response (200 OK)

```json
{
  "candidates": [
    {
      "id": "tc-a1b2c3d4",
      "orchestration_id": "orch-7f3a9b12",
      "orchestration_name": "health_check_ai",
      "source": "ai_generated",
      "success_count": 5,
      "quality_score": 0.9,
      "quality_breakdown": {
        "error_handling": 0.2,
        "timeout_config": 0.2,
        "variable_usage": 0.2,
        "documentation": 0.1,
        "step_count": 0.2
      },
      "status": "pending",
      "created_at": "2026-04-05T10:00:00Z"
    },
    {
      "id": "tc-e5f6g7h8",
      "orchestration_id": "orch-3c4d5e67",
      "orchestration_name": "backup_databases_ai",
      "source": "ai_generated",
      "success_count": 3,
      "quality_score": 0.7,
      "quality_breakdown": {
        "error_handling": 0.2,
        "timeout_config": 0.0,
        "variable_usage": 0.2,
        "documentation": 0.1,
        "step_count": 0.2
      },
      "status": "pending",
      "created_at": "2026-04-06T08:15:00Z"
    }
  ],
  "total": 2
}
```

---

### Approve a Candidate

**POST** `/dm-webmanager/api/training/<id>/approve`

Approve a candidate, adding it to the training dataset.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/training/tc-a1b2c3d4/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
```

#### Response (200 OK)

```json
{
  "id": "tc-a1b2c3d4",
  "orchestration_name": "health_check_ai",
  "status": "approved",
  "reviewer": "admin",
  "reviewed_at": "2026-04-07T14:30:00Z",
  "message": "Candidate added to training dataset."
}
```

---

### Reject a Candidate

**POST** `/dm-webmanager/api/training/<id>/reject`

Reject a candidate. It is removed from the queue and not added to the training dataset.

#### Request

```bash
curl -X POST https://dm.example.com:5000/dm-webmanager/api/training/tc-e5f6g7h8/reject \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "Missing timeout configuration on critical steps"
  }'
```

The `reason` field is optional but recommended for audit purposes.

#### Response (200 OK)

```json
{
  "id": "tc-e5f6g7h8",
  "orchestration_name": "backup_databases_ai",
  "status": "rejected",
  "reviewer": "admin",
  "reviewed_at": "2026-04-07T14:35:00Z",
  "reason": "Missing timeout configuration on critical steps",
  "message": "Candidate rejected and removed from queue."
}
```

#### Error Response (403 Forbidden)

```json
{
  "error": "Insufficient permissions",
  "message": "Administrator role required to manage training candidates."
}
```

#### Error Response (404 Not Found)

```json
{
  "error": "Candidate not found",
  "message": "Training candidate 'tc-invalid' does not exist."
}
```

---

## Complete curl Workflow Example

This example walks through the full review cycle using the API.

```bash
# Authenticate as admin
TOKEN=$(curl -s -X POST https://dm.example.com:5000/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your_password"}' \
  | jq -r '.access_token')

# List pending candidates
echo "=== Pending Candidates ==="
curl -s -X GET https://dm.example.com:5000/dm-webmanager/api/training/queue \
  -H "Authorization: Bearer $TOKEN" | jq .

# Approve the high-quality candidate
echo "=== Approving health_check_ai ==="
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/training/tc-a1b2c3d4/approve \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq .

# Reject the lower-quality candidate with a reason
echo "=== Rejecting backup_databases_ai ==="
curl -s -X POST https://dm.example.com:5000/dm-webmanager/api/training/tc-e5f6g7h8/reject \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "No timeout configuration on backup steps. Could hang indefinitely."}' | jq .

# Verify the queue is now empty
echo "=== Updated Queue ==="
curl -s -X GET https://dm.example.com:5000/dm-webmanager/api/training/queue \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

## What Happens After Approval

When a candidate is approved:

1. The orchestration definition is formatted as a training example (input/output pair).
2. The example is appended to the training dataset.
3. The dataset growth is tracked in metrics (visible in the dashboard under AI > Training Metrics).
4. Periodic retraining (weekly by default, or triggered manually) incorporates the new examples into the model.

Over time, the model improves its ability to generate high-quality orchestrations that match the patterns and best practices established by your team.

---

## Tips

- **Review regularly**: Candidates accumulate over time. Check the queue weekly to keep the training pipeline flowing.
- **Use rejection reasons**: Documenting why a candidate was rejected helps identify patterns in AI-generated content that need improvement.
- **High scores are not automatic approvals**: A score of 1.0 means the automated checks passed, but an administrator should still verify the logic and intent of the orchestration.
- **Rejected candidates can return**: If a rejected orchestration is later modified to address quality concerns and reaches the success threshold again, it re-enters the queue as a new candidate.
- **Training threshold tuning**: If candidates appear too quickly, increase `success_threshold` in the configuration. If the queue is always empty, consider lowering it.

---

## Next Steps

- [Tutorial 19: Natural Language Runner](19-natural-language-runner.md) -- The feature that produces AI-generated orchestrations
- [Tutorial 17: Context-Aware AI](17-context-aware-ai.md) -- Understand the AI engine powering generation and training
