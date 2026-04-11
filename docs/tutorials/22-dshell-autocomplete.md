# Tutorial 22: DShell Auto-Complete

## Overview

DShell, the Dimensigon interactive shell, includes a comprehensive auto-complete system that accelerates command entry and reduces errors. The completer is context-aware -- it understands which command you are typing, what arguments are expected, and what values are valid, then offers intelligent completions drawn from the local catalog cache and the remote API.

The auto-complete system supports orchestration name completion with fuzzy matching, parameter name completion from orchestration schemas, server and target name completion, and full option completion for all DShell commands. A local cache with a 5-minute TTL keeps completions fast and responsive without constant network requests.

---

## Prerequisites

- Dimensigon 3.0 installed and running
- DShell accessible (the interactive command-line shell)
- At least one orchestration and one server registered in the Dimension
- The `prompt_toolkit` Python package (included in Dimensigon dependencies)

---

## Step-by-Step Instructions

### Step 1: Launch DShell

Start the DShell interactive shell:

```bash
dimensigon shell
```

Or, if using the DShell directly:

```bash
dshell
```

You will see the DShell prompt, ready for input.

### Step 2: Trigger Auto-Complete with Tab

Press the **Tab** key at any point while typing a command to trigger auto-complete. The behavior depends on what you have typed so far:

- **Empty prompt**: Tab lists all available top-level commands.
- **Partial command**: Tab completes the command name.
- **After a command**: Tab offers subcommands, positional arguments, or options.
- **After an option flag**: Tab suggests valid values for that option.

### Step 3: Orchestration Name Completion

When typing a command that expects an orchestration name (such as `run`), Tab completes orchestration names from the local catalog.

**Exact prefix matching:**

```
> run hea<Tab>
> run health_check
```

Type the beginning of an orchestration name and press Tab. If there is a single match, the name completes immediately. If there are multiple matches, a dropdown appears with all matching orchestrations.

**Fuzzy matching:**

```
> run hlth<Tab>
  health_check
  health_monitor
```

The completer uses subsequence matching: every character in your input must appear in the candidate in order, but not necessarily contiguously. This means `hlth` matches `health_check` because `h`, `l`, `t`, `h` all appear in sequence within "health_check".

Results are ranked by:

1. Whether the candidate starts with the input string (prefix matches first)
2. Length of the candidate (shorter names first)
3. Alphabetical order

**Orchestrations with spaces in names:**

If an orchestration name contains spaces, the completer automatically wraps it in quotes:

```
> run my app<Tab>
> run "my app deployment"
```

**Parameter hints in completion dropdown:**

When the dropdown appears, each orchestration shows its required parameters as metadata. For example:

```
> run <Tab>
  health_check          params: target, timeout
  deploy_app            params: version, environment
  backup_database
```

### Step 4: Parameter Completion

After selecting an orchestration name, use `--` followed by Tab to see available parameters from the orchestration schema:

```
> run health_check --<Tab>
  --target
  --timeout
  --verbose
```

The `CatalogParamCompleter` extracts parameter names from the orchestration's schema definition, including required inputs, optional inputs, and output variables.

Fuzzy matching also works for parameter names:

```
> run health_check --tgt<Tab>
> run health_check --target
```

### Step 5: Server and Target Completion

When a command or parameter expects a server name, Tab auto-completes from the list of known servers:

```
> run health_check --target web<Tab>
  web-prod-01
  web-prod-02
```

The `CatalogServerNameCompleter` pulls server names from the local catalog cache, and `CatalogTargetCompleter` provides context-aware completions for target fields.

**Target fields with value assignment:**

When a target field expects a `key=value` format, Tab completes both parts:

```
> run deploy_app --target web=<Tab>
  web-prod-01
  web-prod-02
```

Typing the target name followed by `=` switches completion to server name values.

### Step 6: Option Completion for All Commands

Every DShell command supports option completion. After typing a command and a space, press Tab to see available options:

```
> server list --<Tab>
  --name
  --id
  --detail
  --like
```

For options that have a fixed set of choices, Tab shows only valid values:

```
> run deploy_app --environment <Tab>
  production
  staging
  development
```

---

## Cache Behavior

### 5-Minute TTL

The auto-complete system uses a local catalog cache (`OrchestrationCatalog`) that stores:

- All orchestration names and their schemas
- All server names

The cache has a **time-to-live (TTL) of 300 seconds (5 minutes)**. The first time you trigger a completion, the cache is populated by querying the database. Subsequent completions within the 5-minute window use cached data, avoiding repeated database queries.

After the TTL expires, the next completion request triggers an automatic refresh in the background.

### Automatic Refresh

The cache refresh happens transparently:

1. You press Tab to trigger a completion.
2. The completer checks if the cache has expired (`time.time() - last_refresh > 300`).
3. If expired, the cache queries the database for the latest orchestrations and servers.
4. The completion results are returned from the freshly populated cache.

This means if a new orchestration or server is added to the Dimension, you may need to wait up to 5 minutes for it to appear in auto-complete, or manually refresh the cache.

### Manual Refresh

To force an immediate cache refresh without waiting for the TTL to expire, use the `refresh` command in DShell:

```
> refresh
Catalog refreshed: 15 orchestrations, 8 servers
```

This clears the cache and repopulates it immediately from the database. Use this after adding new orchestrations or servers, or if completions seem stale.

---

## Context-Aware Completion

The DShell completer is fully context-aware. The completions you see change based on:

### Command type

Different commands offer different completions. The `run` command completes orchestration names; `server list` completes server names and options; `action` commands complete action template names.

### Argument position

The completer tracks which positional argument or option you are currently typing. After the orchestration name is resolved, it switches to parameter and target completers. After `--target`, it offers server names instead of orchestration names.

### Already-used values

Options that have already been provided are excluded from future completions. If you have already specified `--target web-prod-01`, that server is not suggested again.

### Sub-command nesting

DShell supports nested commands (e.g., `server list`, `manager locker show`). The completer walks the command tree and delegates to the appropriate sub-completer at each level.

---

## Completer Architecture

The auto-complete system is composed of several completer classes, each responsible for a specific type of completion:

### DshellCompleter

The top-level completer that routes to sub-completers based on the command tree. Supports nested dictionaries of commands, where each leaf node can be another completer or a list of argument definitions.

### CatalogOrchNameCompleter

Completes orchestration names using the local catalog cache with fuzzy matching. Shows required parameters as metadata in the dropdown.

### CatalogParamCompleter

Completes orchestration parameter names from the schema. Set the orchestration name via `set_orch_name()` before triggering completion.

### CatalogServerNameCompleter

Completes server names using the local catalog cache with fuzzy matching.

### CatalogTargetCompleter

Completes target fields, supporting both target key names (from the orchestration schema) and server name values (after `=`).

### ResourceCompleter

A network-based completer that fetches completion candidates from the Dimensigon REST API in real time. Used for resources that may not be in the local cache, such as action templates, software, log federations, and files. Has a 3-second timeout to keep the UI responsive.

### DshellWordCompleter

An enhanced word completer that supports case-insensitive matching, middle-of-word matching, and automatic quoting for values with spaces.

---

## How to Extend: Adding Custom Completers

You can create custom completers for new commands or resources by subclassing the prompt_toolkit `Completer` class.

### Basic custom completer

```python
from prompt_toolkit.completion import Completer, Completion
from dimensigon.dshell.catalog import fuzzy_match, get_catalog


class MyCustomCompleter(Completer):
    """Complete custom resource names from the catalog."""

    def get_completions(self, document, complete_event):
        word = document.get_word_before_cursor(WORD=True)
        # Get your list of candidate values
        candidates = ["value-a", "value-b", "value-c"]
        # Use fuzzy_match for consistent matching behavior
        matches = fuzzy_match(word, candidates)
        for match in matches:
            if match != word:
                yield Completion(match, -len(word))
```

### Registering a custom completer

To make your completer available in DShell, add it to the command definition in `dimensigon/dshell/commands.py`:

```python
from dimensigon.dshell.completer import MyCustomCompleter

my_custom_completer = MyCustomCompleter()

# In the command definition dict, reference the completer:
{
    'argument': '--my-param',
    'completer': my_custom_completer,
}
```

### Using ResourceCompleter for API-backed completion

For resources served by a Dimensigon API endpoint, use `ResourceCompleter` directly:

```python
from dimensigon.dshell.completer import ResourceCompleter

# Complete from an API endpoint, using 'name' as the display key
my_resource_completer = ResourceCompleter(
    'api_1_0.myresourcelist',     # Flask endpoint name
    key='name',                    # JSON key to use as completion value
    meta_html_format="<b>{name}</b>, <i>{description}</i>",
    filters=['--category'],        # URL filters from other arguments
)
```

### Using CatalogOrchNameCompleter with custom data

If you need catalog-style completion for a different data source, subclass `CatalogOrchNameCompleter` and override the data retrieval logic:

```python
from dimensigon.dshell.completer import CatalogOrchNameCompleter

class MyOrchestrationsCompleter(CatalogOrchNameCompleter):
    def get_completions(self, document, complete_event):
        # Custom logic to get orchestration names
        # Falls back to catalog-based completion
        yield from super().get_completions(document, complete_event)
```

---

## Pre-Built Completer Instances

DShell ships with several pre-configured completer instances ready for use:

| Instance | Resource | What it completes |
|---|---|---|
| `server_name_completer` | `api_1_0.serverlist` | Server names via API |
| `server_completer` | `api_1_0.serverlist` | Server IDs with name as metadata |
| `granule_completer` | `api_1_0.granulelist` | Granule (tag) names |
| `orch_completer` | `api_1_0.orchestrationlist` | Orchestration IDs with name and version |
| `orch_name_completer` | `api_1_0.orchestrationlist` | Orchestration names |
| `orch_ver_completer` | `api_1_0.orchestrationlist` | Orchestration versions |
| `action_completer` | `api_1_0.actiontemplatelist` | Action template IDs with name and version |
| `action_name_completer` | `api_1_0.actiontemplatelist` | Action template names |
| `action_ver_completer` | `api_1_0.actiontemplatelist` | Action template versions |
| `software_completer` | `api_1_0.softwarelist` | Software IDs with name and version |
| `catalog_orch_name_completer` | Local cache | Orchestration names (offline, fuzzy) |
| `catalog_param_completer` | Local cache | Parameter names from schema |
| `catalog_server_name_completer` | Local cache | Server names (offline, fuzzy) |
| `catalog_target_completer` | Local cache | Target names and server values |

The `catalog_*` instances use the local cache and fuzzy matching, while the others use real-time API requests with a 3-second timeout.

---

## Fuzzy Matching Algorithm

The fuzzy matching algorithm used by catalog-based completers works as follows:

1. **Subsequence check**: Every character in the input must appear in the candidate string in order, but not necessarily contiguously. For example, `hlth` matches `health_check` because the characters `h`, `l`, `t`, `h` appear in that order.

2. **Ranking**: Matching candidates are sorted by:
   - **Prefix match** (candidates starting with the input come first)
   - **Length** (shorter candidates rank higher)
   - **Alphabetical order** (tiebreaker)

3. **Case-insensitive**: Both input and candidates are lowercased for comparison.

**Examples:**

| Input | Candidates | Matches (in order) |
|---|---|---|
| `hea` | `health_check`, `heap_dump`, `heartbeat` | `heap_dump`, `heartbeat`, `health_check` |
| `hlth` | `health_check`, `health_monitor` | `health_check`, `health_monitor` |
| `dep` | `deploy`, `deployment`, `deep_scan` | `deploy`, `deep_scan`, `deployment` |
| `xyz` | `health_check`, `deploy` | _(no matches)_ |

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Tab does nothing | Ensure prompt_toolkit is installed (`pip install prompt_toolkit`). DShell requires it for interactive features. |
| New orchestration not appearing | The catalog cache may not have refreshed yet. Run the `refresh` command to force a cache update. |
| Slow completions | ResourceCompleter instances make API calls with a 3-second timeout. If the API is slow or unreachable, completions may lag. Use catalog-based completers for faster offline completion. |
| Completions show stale data | The cache TTL is 5 minutes. Run `refresh` to force an update, or wait for the cache to expire naturally. |
| Fuzzy match returns too many results | Type more characters to narrow the match. Fuzzy matching uses subsequence logic, so even short inputs can match many candidates. |
| Server names not appearing | Verify that servers are properly registered in the Dimension. Run `server list` to confirm they are visible. |
| Completions contain duplicate entries | This can happen if the same resource appears multiple times in the API response. The completer deduplicates by key, but edge cases may occur with version conflicts. |
| Quoted completions break | Orchestration or server names with spaces are automatically quoted. If you see quoting issues, ensure you are not adding extra quotes around the completed value. |

---

**Document Version**: 1.0.0
**Last Updated**: 2026-04-07
**Dimensigon Version**: 3.0
