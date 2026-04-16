# Security Layer Simplification

- **Priority:** 2
- **Category:** Core
- **Effort:** 2 days
- **Dependencies:** None

## Context

The current D-Securizer layer applies full encryption/signing to every intra-dimension request,
adding latency and complexity for traffic that already travels over a trusted internal network.
Making `plain` the default for intra-dimension traffic significantly reduces overhead while
preserving security for cross-dimension communication.

## Scope

- Introduce a configuration key `SECURIZER_MODE` with values `auto`, `always`, and `never`.
- `auto` (new default): use plain for intra-dimension, encrypted for cross-dimension.
- `always`: current behavior, encrypt everything.
- `never`: skip securizer entirely (dev/test only).
- Refactor the securizer decorator to check the mode before processing.
- Add logging when mode transitions occur.

## Files to Modify

- `dimensigon/web/decorators.py` (securizer decorator logic)
- `dimensigon/web/config.py` (new config key)
- `dimensigon/domain/entities/dimension.py` (dimension membership check helper)
- `dimensigon/web/__init__.py` (config registration)

## Implementation Steps

1. Add `SECURIZER_MODE` to the app config with default `auto`.
2. Create helper `is_same_dimension(source_node)` in the dimension entity module.
3. Modify the securizer decorator: check mode, check dimension membership, skip
   encryption/decryption when appropriate.
4. Add `D-Securizer: plain` header on outgoing intra-dimension requests.
5. Log mode decisions at DEBUG level for troubleshooting.
6. Write unit tests for each mode: `auto`, `always`, `never`.
7. Update configuration documentation.

## Verification

- Intra-dimension requests complete without encryption overhead when mode is `auto`.
- Cross-dimension requests remain fully encrypted under `auto`.
- `always` mode produces identical behavior to current implementation.
- `never` mode bypasses all securizer logic (confirmed via header inspection).

## Breaking Changes

- Default behavior changes from `always` to `auto`. Deployments relying on full encryption
  for intra-dimension traffic must set `SECURIZER_MODE=always` explicitly.
