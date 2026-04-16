# forward_or_dispatch Decorator Fix

- **Priority:** 3
- **Category:** Core
- **Effort:** 2-3 hours
- **Dependencies:** None

## Context

The `forward_or_dispatch` decorator calls `request.get_json()` unconditionally, which raises
a 400 or 415 error on GET requests that have no JSON body. This silently breaks any route
decorated with `forward_or_dispatch` when accessed via GET. The fix is a one-line change but
has wide impact since the decorator is used across the API surface.

## Scope

- Change `request.get_json()` to `request.get_json(silent=True)` so that requests without
  a JSON body return `None` instead of raising an exception.
- Add a guard to handle the `None` case downstream.
- Add regression tests to ensure GET requests through the decorator work correctly.

## Files to Modify

- `dimensigon/web/decorators.py` (the `forward_or_dispatch` function)
- `tests/` (new regression test file)

## Implementation Steps

1. Locate the `request.get_json()` call in the `forward_or_dispatch` decorator.
2. Replace with `request.get_json(silent=True)`.
3. Add a `if json_data is None: json_data = {}` guard where the result is consumed.
4. Write a test: GET request through decorated endpoint returns 200, not 400/415.
5. Write a test: POST with JSON body still works as before.
6. Write a test: POST without Content-Type header returns graceful error.

## Verification

- `GET /api/v1.0/<any-decorated-endpoint>` returns expected data without errors.
- `POST /api/v1.0/<any-decorated-endpoint>` with JSON body works unchanged.
- No regression in existing test suite.

## Breaking Changes

- None. This is a pure bug fix. Any code that relied on the 400 error for GET requests
  (unlikely) would see different behavior.
