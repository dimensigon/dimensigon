# SQLAlchemy 2.x Migration

- **Priority:** 1
- **Category:** Core
- **Effort:** 3-4 days
- **Dependencies:** None

## Context

The current codebase relies on SQLAlchemy 1.4 patterns that are deprecated or removed in
SQLAlchemy 2.x. Calls like `session.transaction`, `engine.execute()`, and `Query.get()` will
break on upgrade. This migration unblocks every other feature that touches the database layer,
making it the highest-priority item.

## Scope

- Replace all `engine.execute()` calls with `session.execute()` using `text()` wrappers.
- Migrate `session.transaction` references to the 2.x context-manager style.
- Replace `Query.get(pk)` with `session.get(Model, pk)`.
- Update relationship lazy-loading defaults where needed.
- Ensure all entity models use `DeclarativeBase` (2.x style) or remain compatible via
  `__allow_unmapped__`.
- Pin SQLAlchemy>=2.0 in requirements.

## Files to Modify

- `dimensigon/utils/helpers.py`
- `dimensigon/bootstrap.py`
- `dimensigon/domain/entities/*.py` (all entity files)
- `dimensigon/use_cases/*.py` (any direct engine usage)
- `requirements.txt`

## Implementation Steps

1. Audit every file for deprecated API calls using `sqlalchemy.warn_20` compatibility mode.
2. Replace `engine.execute()` with `with engine.connect() as conn: conn.execute(text(...))`.
3. Replace `session.query(Model).get(pk)` with `session.get(Model, pk)`.
4. Replace `session.transaction` with explicit `session.begin()` context managers.
5. Update relationship definitions for 2.x lazy-loading semantics.
6. Run full test suite under SQLAlchemy 2.x with warnings as errors.
7. Update `requirements.txt` to pin `SQLAlchemy>=2.0,<2.1`.

## Verification

- All existing unit tests pass with SQLAlchemy 2.0 installed.
- `python -W error::DeprecationWarning -m pytest` produces zero SQLAlchemy warnings.
- Application boots and completes a full orchestration cycle end-to-end.

## Breaking Changes

- Any third-party code or plugin using `engine.execute()` directly will need updating.
- Lazy-loading behavior may change for relationships accessed outside a session context.
