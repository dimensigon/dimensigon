# Orch-Library Template Suggestions

> **Plan:** Community-driven template library with AI-powered search
> **Category:** AI / Templates
> **Effort:** 2-3 hours to integrate

## Overview

The `orch-library` is a public GitHub repository (`github.com/dimensigon/orch-library`) hosting 1,712+ unique ready-to-use orchestrations and action templates (deduplicated from an AI training dataset of 6,302 variants). Dimensigon integrates with it in three ways:

1. **Search** — a built-in TF-IDF + fuzzy hybrid search over the catalog
2. **Fetch** — retrieve a single template's full JSON by path
3. **Import** — copy a library template into your local `OrchTemplate` table

The catalog is cached in memory for 1 hour and fetched lazily on first use.

## Prerequisites

- Authenticated WebManager session (see [05-authentication](./05-authentication.md))
- Outbound HTTPS to `raw.githubusercontent.com` (or a mirror)
- Optional: `DM_ORCH_LIBRARY_URL` env var to point at a custom catalog URL

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DM_ORCH_LIBRARY_URL` | `raw.githubusercontent.com/dimensigon/orch-library/main/catalog.json` | Catalog JSON URL |
| `DM_ORCH_LIBRARY_RAW_BASE` | `raw.githubusercontent.com/dimensigon/orch-library/main/` | Base URL for individual templates |

Catalog TTL: 1 hour (hardcoded in `dimensigon/ai/template_suggest.py`).

## Endpoints

### Suggest templates by natural language

```bash
curl -X POST https://dm.example.com/dm-webmanager/api/library/suggest \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "restart a systemd service with retries",
    "top_k": 5,
    "entity_type": "action_template",
    "action_type": "SHELL"
  }'
```

Response:

```json
{
  "query": "restart a systemd service with retries",
  "size": 1712,
  "results": [
    {
      "id": "shell.service_mgmt.restart-service.v0",
      "name": "postgresql-restart",
      "description": "Restarts the postgresql systemd service and verifies...",
      "category": "shell.service_mgmt",
      "entity_type": "action_template",
      "action_type": "SHELL",
      "difficulty": "basic",
      "tags": ["shell", "service_mgmt", "basic"],
      "path": "action_templates/shell/service_mgmt/postgresql-restart.json",
      "score": 0.8241
    },
    ...
  ]
}
```

**Filters:** `entity_type` (orchestration|action_template), `action_type` (SHELL|PYTHON|ANSIBLE|ORCHESTRATION), `difficulty` (basic|intermediate|advanced).

### Fetch full template JSON

```bash
curl -X POST https://dm.example.com/dm-webmanager/api/library/fetch \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"path": "action_templates/shell/service_mgmt/postgresql-restart.json"}'
```

Returns the full template document including the executable `template` payload.

### Import into local library

```bash
curl -X POST https://dm.example.com/dm-webmanager/api/library/import \
  -H "Authorization: Bearer $JWT" \
  -d '{"path": "orchestrations/single/app_deploy/rolling-deploy.json"}'
```

Requires the `operator` role. Creates a new `OrchTemplate` row mapped from the library template.

### Force catalog refresh (admin)

```bash
curl -X POST https://dm.example.com/dm-webmanager/api/library/refresh \
  -H "Authorization: Bearer $JWT"
```

Requires `administrator` role. Forces a re-fetch even if the cached catalog is still fresh.

## End-to-end example

```bash
JWT=$(curl -sX POST https://dm.example.com/dm-webmanager/login \
  -d '{"username":"ops","password":"..."}' -H "Content-Type: application/json" \
  | jq -r '.access_token')

# 1. Describe what you want
PATH=$(curl -sX POST https://dm.example.com/dm-webmanager/api/library/suggest \
  -H "Authorization: Bearer $JWT" \
  -d '{"query":"deploy nginx with rolling update", "top_k":1}' \
  | jq -r '.results[0].path')

# 2. Import the top match
curl -sX POST https://dm.example.com/dm-webmanager/api/library/import \
  -H "Authorization: Bearer $JWT" \
  -d "{\"path\":\"$PATH\"}"
```

## How ranking works

The search engine computes:

1. **TF-IDF cosine similarity** over a document built from: name + description + category + action_type + user_prompt + tags
2. **Exact-match boosts**: +0.3 if the query text appears literally in the name, +0.2 in the user_prompt
3. **English stopwords** are stripped from both query and documents before tokenization
4. Results are sorted by final score descending and truncated to `top_k`

This is fast (no embeddings, no external services) and works offline once the catalog is cached. For semantic search with embeddings, you can adapt `TemplateIndex.search()` to use an embedding model and cosine over dense vectors.

## Contributing templates

See [`CONTRIBUTING.md`](https://github.com/dimensigon/orch-library/blob/main/CONTRIBUTING.md) in the orch-library repo:

1. Fork, add your template JSON in the right category
2. `python3 scripts/validate.py <path>` to verify
3. `python3 scripts/rebuild_catalog.py` to regenerate the index
4. Submit a PR — CI runs schema validation + integrity checks

## Related

- [11-templates-marketplace](./11-templates-marketplace.md) — the local `OrchTemplate` catalog
- [17-ai-chat](./17-ai-chat.md) — conversational orchestration authoring
- [19-natural-language-runner](./19-natural-language-runner.md) — NL orchestration execution
