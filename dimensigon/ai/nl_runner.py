"""
Natural Language Orchestration Runner.

Resolves natural language commands into orchestration executions by
fuzzy-matching orchestration names, extracting target servers, and
parsing parameters from free-text input.
"""
import re
import typing as t

from dimensigon.dshell.catalog import fuzzy_match


# Template for future AI-backed resolution
NL_RUNNER_PROMPT = """You are an orchestration assistant for Dimensigon.
Given the user's natural language request, determine:
1. Which orchestration to run (from the available list)
2. Which servers to target
3. What parameters to pass

Available orchestrations:
{orchestrations}

Available servers:
{servers}

User request: {user_input}

Respond with JSON: {{"orchestration_name": "...", "targets": [...], "params": {{...}}}}
"""


def _extract_params(user_input: str) -> t.Dict[str, str]:
    """Extract parameters from user input.

    Looks for:
    - Explicit key=value patterns
    - "with <key> <value>" patterns
    - "using <key> <value>" patterns
    """
    params: t.Dict[str, str] = {}

    # Match key=value patterns (e.g., timeout=30, env=production)
    kv_pattern = re.compile(r'(\w+)\s*=\s*("[^"]*"|\S+)')
    for match in kv_pattern.finditer(user_input):
        key = match.group(1)
        value = match.group(2).strip('"')
        params[key] = value

    # Match "with <key> <value>" patterns
    with_pattern = re.compile(
        r'\bwith\s+(\w+)\s+("[^"]*"|\S+)', re.IGNORECASE
    )
    for match in with_pattern.finditer(user_input):
        key = match.group(1)
        value = match.group(2).strip('"')
        if key not in params:
            params[key] = value

    # Match "using <key> <value>" patterns
    using_pattern = re.compile(
        r'\busing\s+(\w+)\s+("[^"]*"|\S+)', re.IGNORECASE
    )
    for match in using_pattern.finditer(user_input):
        key = match.group(1)
        value = match.group(2).strip('"')
        if key not in params:
            params[key] = value

    return params


def _extract_targets(
    user_input: str,
    servers: t.List[t.Dict[str, t.Any]],
) -> t.List[t.Dict[str, t.Any]]:
    """Extract target servers from user input.

    Matches against server names and granule names. Also recognizes
    "all servers" and "all <granule>" patterns.
    """
    input_lower = user_input.lower()
    targets: t.List[t.Dict[str, t.Any]] = []
    seen_ids: t.Set[str] = set()

    # Check for "all servers" pattern (but not "all <granule> servers")
    if re.search(r'\ball\s+servers?\b', input_lower) and not re.search(r'\ball\s+\w+\s+servers?\b', input_lower):
        for srv in servers:
            if srv['id'] not in seen_ids:
                targets.append({'id': srv['id'], 'name': srv['name']})
                seen_ids.add(srv['id'])
        return targets

    # Check for "all <granule>" pattern (e.g., "all web servers")
    all_granule = re.search(r'\ball\s+(\w+)\s+servers?\b', input_lower)
    if all_granule:
        granule_term = all_granule.group(1).lower()
        for srv in servers:
            granules = [g.lower() for g in srv.get('granules', [])]
            if granule_term in granules and srv['id'] not in seen_ids:
                targets.append({'id': srv['id'], 'name': srv['name']})
                seen_ids.add(srv['id'])
        if targets:
            return targets

    # Check for explicit server name matches first (highest priority)
    server_names = [s['name'] for s in servers]
    name_to_server = {s['name']: s for s in servers}

    for srv in servers:
        name_lower = srv['name'].lower()
        if name_lower in input_lower and srv['id'] not in seen_ids:
            targets.append({'id': srv['id'], 'name': srv['name']})
            seen_ids.add(srv['id'])

    # If explicit names found, return those without granule matching
    if targets:
        return targets

    # If no explicit server names, try word-level fuzzy matching on "on <word>"
    on_pattern = re.findall(r'\bon\s+(\S+)', input_lower)
    for token in on_pattern:
        matched = fuzzy_match(token, server_names)
        if matched:
            best = matched[0]
            srv = name_to_server[best]
            if srv['id'] not in seen_ids:
                targets.append({'id': srv['id'], 'name': srv['name']})
                seen_ids.add(srv['id'])

    if targets:
        return targets

    # Fall back to granule name mentions in the input
    for srv in servers:
        for granule in srv.get('granules', []):
            if re.search(r'\b' + re.escape(granule.lower()) + r'\b', input_lower) and srv['id'] not in seen_ids:
                targets.append({'id': srv['id'], 'name': srv['name']})
                seen_ids.add(srv['id'])

    return targets


def resolve_intent(
    user_input: str,
    orchestrations: t.List[t.Dict[str, t.Any]],
    servers: t.List[t.Dict[str, t.Any]],
) -> t.Dict[str, t.Any]:
    """Resolve a natural language command into an orchestration execution plan.

    Parameters
    ----------
    user_input : str
        Natural language description of what to run.
    orchestrations : list of dict
        Each dict has keys: name, id, description, schema.
    servers : list of dict
        Each dict has keys: name, id, granules.

    Returns
    -------
    dict
        Resolution result with keys:
        - orchestration_id: best match ID (or None)
        - orchestration_name: best match name (or None)
        - confidence: float 0.0-1.0
        - targets: list of {id, name} dicts
        - params: dict of extracted parameters
        - alternatives: list of {id, name, confidence} if ambiguous
    """
    if not user_input or not user_input.strip():
        return {
            'orchestration_id': None,
            'orchestration_name': None,
            'confidence': 0.0,
            'targets': [],
            'params': {},
            'alternatives': [],
        }

    input_lower = user_input.lower()
    orch_names = [o['name'] for o in orchestrations]
    name_to_orch = {o['name']: o for o in orchestrations}

    # --- Orchestration matching ---
    # Strategy 1: Check for exact name match (case-insensitive substring)
    exact_matches = []
    for orch in orchestrations:
        if orch['name'].lower() in input_lower:
            exact_matches.append(orch)

    # Strategy 2: Fuzzy match on orchestration names
    fuzzy_matches = fuzzy_match(input_lower, orch_names)

    # Strategy 3: Match against description keywords
    desc_matches = []
    input_words = set(re.findall(r'\w+', input_lower))
    # Filter out common stop words
    stop_words = {
        'run', 'execute', 'do', 'the', 'a', 'an', 'on', 'all', 'servers',
        'server', 'please', 'with', 'using', 'and', 'or', 'for', 'to',
        'in', 'at', 'of', 'my', 'this', 'that', 'it', 'is', 'are',
    }
    meaningful_words = input_words - stop_words
    for orch in orchestrations:
        desc = (orch.get('description') or '').lower()
        name_lower = orch['name'].lower()
        desc_words = set(re.findall(r'\w+', desc + ' ' + name_lower))
        overlap = meaningful_words & desc_words
        if overlap:
            score = len(overlap) / max(len(meaningful_words), 1)
            desc_matches.append((score, orch))
    desc_matches.sort(key=lambda x: x[0], reverse=True)

    # Determine best match and confidence
    best_orch = None
    confidence = 0.0
    alternatives = []

    if exact_matches:
        best_orch = exact_matches[0]
        confidence = 1.0
        if len(exact_matches) > 1:
            confidence = 0.8
            alternatives = [
                {'id': o['id'], 'name': o['name'], 'confidence': 0.8}
                for o in exact_matches[1:]
            ]
    elif fuzzy_matches:
        best_name = fuzzy_matches[0]
        best_orch = name_to_orch[best_name]
        # Confidence based on how many fuzzy matches there are
        if len(fuzzy_matches) == 1:
            confidence = 0.9
        elif len(fuzzy_matches) <= 3:
            confidence = 0.7
        else:
            confidence = 0.5
        alternatives = [
            {'id': name_to_orch[n]['id'], 'name': n, 'confidence': max(0.3, confidence - 0.2)}
            for n in fuzzy_matches[1:5]
        ]
    elif desc_matches:
        score, orch = desc_matches[0]
        best_orch = orch
        confidence = min(0.6, score)
        alternatives = [
            {
                'id': o['id'],
                'name': o['name'],
                'confidence': min(0.5, s),
            }
            for s, o in desc_matches[1:4]
        ]

    # --- Target extraction ---
    targets = _extract_targets(user_input, servers)

    # --- Parameter extraction ---
    params = _extract_params(user_input)

    return {
        'orchestration_id': best_orch['id'] if best_orch else None,
        'orchestration_name': best_orch['name'] if best_orch else None,
        'confidence': confidence,
        'targets': targets,
        'params': params,
        'alternatives': alternatives,
    }
