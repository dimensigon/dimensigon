import logging
import time
import typing as t

_logger = logging.getLogger('dshell.catalog')

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes


def fuzzy_match(input_str: str, candidates: t.List[str]) -> t.List[str]:
    """Return candidates that contain input_str as a subsequence, sorted by match quality.

    A subsequence match means every character in input_str appears in the
    candidate in order, but not necessarily contiguously. Results are sorted
    by: (1) whether the candidate starts with input_str, (2) length of
    candidate (shorter is better), (3) alphabetical order.

    Parameters
    ----------
    input_str : str
        The partial input to match against.
    candidates : list of str
        The list of candidate strings to filter and rank.

    Returns
    -------
    list of str
        Matching candidates sorted by relevance.
    """
    if not input_str:
        return sorted(candidates)

    input_lower = input_str.lower()
    matches = []
    for candidate in candidates:
        candidate_lower = candidate.lower()
        # Check subsequence match
        it = iter(candidate_lower)
        if all(ch in it for ch in input_lower):
            starts_with = candidate_lower.startswith(input_lower)
            matches.append((not starts_with, len(candidate), candidate.lower(), candidate))

    matches.sort()
    return [m[3] for m in matches]


class OrchestrationCatalog:
    """Cache for orchestration names, parameter schemas, and server names.

    Data is fetched from the database and cached for ``CACHE_TTL`` seconds.
    After expiry the next access triggers an automatic refresh.
    """

    def __init__(self) -> None:
        self._orchestrations: t.Dict[str, t.Dict[str, t.Any]] = {}
        self._server_names: t.List[str] = []
        self._last_refresh: float = 0.0

    @property
    def _is_expired(self) -> bool:
        return (time.time() - self._last_refresh) > CACHE_TTL

    def _ensure_fresh(self) -> None:
        """Refresh the cache if it has expired."""
        if self._is_expired:
            self.refresh()

    def refresh(self) -> None:
        """Query the DB for all orchestrations and servers, updating the cache."""
        try:
            from dimensigon.domain.entities import Orchestration, Server
            from dimensigon.web import db
            from sqlalchemy import select

            # Fetch orchestrations
            orchestrations: t.Dict[str, t.Dict[str, t.Any]] = {}
            rows = db.session.execute(
                select(Orchestration).order_by(Orchestration.name, Orchestration.version.desc())
            ).scalars().all()
            for orch in rows:
                if orch.name not in orchestrations:
                    try:
                        schema = orch.schema
                    except Exception:
                        schema = {}
                    orchestrations[orch.name] = {
                        'description': orch.description or '',
                        'version': orch.version,
                        'schema': schema,
                        'target': list(orch.target) if orch.target else [],
                    }
            self._orchestrations = orchestrations

            # Fetch servers
            servers = db.session.execute(
                select(Server.name).order_by(Server.name)
            ).scalars().all()
            self._server_names = list(servers)

            self._last_refresh = time.time()
            _logger.debug(
                'Catalog refreshed: %d orchestrations, %d servers',
                len(self._orchestrations),
                len(self._server_names),
            )
        except Exception as e:
            _logger.debug('Catalog refresh failed: %s', e)

    def get_orchestration_names(self) -> t.List[str]:
        """Return a list of all orchestration names (latest version only)."""
        self._ensure_fresh()
        return sorted(self._orchestrations.keys())

    def get_parameters(self, orch_name: str) -> t.Dict[str, t.Any]:
        """Return the parameter schema dict for the given orchestration name.

        The schema is taken from ``Orchestration.schema`` which describes
        required inputs, their containers, and output variables.

        Returns an empty dict if the orchestration is not found.
        """
        self._ensure_fresh()
        info = self._orchestrations.get(orch_name)
        if info is None:
            return {}
        return info.get('schema', {})

    def get_target_names(self, orch_name: str) -> t.List[str]:
        """Return the target names for the given orchestration."""
        self._ensure_fresh()
        info = self._orchestrations.get(orch_name)
        if info is None:
            return []
        return info.get('target', [])

    def get_server_names(self) -> t.List[str]:
        """Return a list of all server names."""
        self._ensure_fresh()
        return list(self._server_names)


# Module-level singleton
_catalog_instance: t.Optional[OrchestrationCatalog] = None


def get_catalog() -> OrchestrationCatalog:
    """Return the module-level OrchestrationCatalog singleton."""
    global _catalog_instance
    if _catalog_instance is None:
        _catalog_instance = OrchestrationCatalog()
    return _catalog_instance
