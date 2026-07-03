# Plan: LoadJsonNode Hardening & Test Organization

## Plan Audit Cycles
- Audits: 2 — Plan Auditor v1.5.0
- Architectural Reviews: none — Plan Architect Reviewer v1.6.0

## Prior Project Context
This rework plan addresses actionable items surfaced during the `2026-07-03-load-json-node` synthesis. That cycle added `LoadJsonNode` as the fourteenth node, completing the load/save file cycle. All 9 acceptance criteria were met across 5 pipeline stages with 17/17 tests passing and zero blocking security findings. However, the synthesis identified five deferred improvements — three code-hardening items (empty-filename guard, file-size cap, path-guard DRY refactor) and two project-organization items (test file cleanup and `tests/` directory creation). Knowledge base insight #4 independently corroborates the empty-filename guard recommendation.

## Summary
Harden `LoadJsonNode` against two edge cases (empty-filename combo placeholder and oversized JSON files), eliminate internal code duplication by extracting a shared path-traversal guard helper, and organize the project's test infrastructure by moving test files into a dedicated `tests/` directory and removing the defunct `qa_test_wp003.py` scaffold.

## Architectural Context

**Existing modules and patterns relevant to this change:**

- [nodes.py](../../nodes.py) — All 14 node classes and module-level helpers. `LoadJsonNode` (line 871) duplicates a 4-line path-traversal guard in both `fingerprint_inputs()` (line 898) and `execute()` (line 914). `SaveJsonNode` (line 954) uses an analogous guard for its subfolder validation.
- [verify_wp003.py](../../verify_wp003.py) — Standalone mock-based test suite for `LoadJsonNode` (8 test cases). Lives in the repo root by happenstance.
- [qa_test_wp003.py](../../qa_test_wp003.py) — Incomplete test scaffold with no assertions. Contains only a header comment pointing to `verify_wp003.py`.
- `_list_json_files()` (line 216) — Returns sorted list of `.json` files from the input directory; returns `[]` when the directory is empty. The `['']` combo placeholder is injected in `define_schema()` with an explicit `if not file_list` check.
- [docs/agents/project-manifest/constraints.md](../../docs/agents/project-manifest/constraints.md) — Documents the two-tier testing strategy and notes that new test files should go in `tests/`.

## Approach / Architecture

Five focused changes, grouped into three categories:

### A. Code Hardening (Steps 1–3)

1. **Empty-filename guard** — Add an early `if not filename` check at the top of both `execute()` and `fingerprint_inputs()` in `LoadJsonNode`, before the path-traversal logic. This produces a clear, user-friendly error message ("No file selected — add .json files to the input directory and restart ComfyUI") instead of the current confusing `PermissionError`.

2. **File-size cap** — Add a module-level constant `_MAX_JSON_FILE_SIZE = 50 * 1024 * 1024` (50 MB) and an `os.path.getsize()` pre-check in `LoadJsonNode.execute()` before reading the file. This prevents accidental memory exhaustion from unexpectedly large files. 50 MB is generous for JSON configuration/metadata files while still providing a safety net.

3. **`_guard_input_path()` helper** — Extract the duplicated path-traversal guard (resolve with `os.path.realpath()`, verify `startswith(real_dir + os.sep)`) into a module-level helper function `_guard_input_path(filename)` that returns the resolved real path or raises `ValueError`. Both `fingerprint_inputs()` and `execute()` will call this helper instead of inlining the logic. The empty-filename guard from step 1 will be integrated into this helper so the check is centralized.

### B. Test Organization (Steps 4–5)

4. **Create `tests/` directory** — Move `verify_wp003.py` to `tests/verify_wp003.py`. Update any internal path references (the script uses `os.path.dirname(os.path.abspath(__file__))` to find the repo root — this will need adjusting to `os.path.dirname(os.path.dirname(...))` since the file moves one level deeper).

5. **Remove `qa_test_wp003.py`** — Delete the defunct test scaffold from the repo root. It contains no assertions and exists only as a pointer to `verify_wp003.py`.

### C. Test Updates (Step 6)

6. **Add new test cases** — Add test cases to the verification script covering the two new guards (empty-filename and file-size cap).

## Rationale

- **Empty-filename guard**: The `['']` placeholder is a necessary ComfyUI convention for empty combos, but letting it flow through to the path-traversal guard produces a confusing error chain (`os.path.realpath(input_dir + '')` → resolves to `input_dir` itself → fails boundary check or raises `PermissionError` on Windows). An explicit early guard is cheap and produces a diagnostic message.
- **File-size cap at 50 MB**: JSON configuration files in ComfyUI workflows are typically kilobytes. A 50 MB cap is orders of magnitude above any reasonable use case while preventing `json.loads()` from consuming gigabytes of memory on accidental large-file selection. The constant is module-level so it can be easily adjusted.
- **`_guard_input_path()` extraction**: The 4-line guard is currently copy-pasted between two methods (and the synthesis correctly identifies that a third file-I/O node would make this worse). Extracting it now is low-risk DRY that also centralizes the empty-filename check.
- **`tests/` directory**: The constraints doc already recommends this. Moving the test file now establishes the convention before more test files accumulate.
- **Removing `qa_test_wp003.py`**: The file has no functional value and its continued existence is confusing.

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|----------|--------------|-------------------------|-------------------|
| File-size limit | Module-level constant `_MAX_JSON_FILE_SIZE` | No limit (status quo); configurable node input | A constant is simple and sufficient for defense-in-depth; a node input adds UI clutter for a niche edge case; no limit leaves the gap open |
| Guard helper scope | `_guard_input_path()` for input dir only | Generic `_guard_path(base_dir, filename)` usable by both Load and Save nodes | Save node's guard is structurally different (validates a subfolder, not a filename); a generic helper would need divergent signatures. Keep focused. |
| Empty-filename check location | Inside `_guard_input_path()` helper | Separate check in `execute()` before calling the guard | Centralizing in the helper means `fingerprint_inputs()` also gets the guard automatically, which is the correct behavior |
| Test directory structure | Flat `tests/` directory | `tests/unit/`, `tests/integration/` hierarchy | Only one test file exists; a flat directory is sufficient and avoids over-engineering |

## Pattern Alignment

- **Module-level private helpers** — `_guard_input_path()` follows the naming and placement pattern of `_coerce_json_object()`, `_get_next_counter()`, `_list_json_files()`, and other `_`-prefixed helpers in [nodes.py](../../nodes.py).
- **Module-level constants** — `_MAX_JSON_FILE_SIZE` follows the pattern of `_KEY_COMPONENT_MAX_LENGTH` (defined at module level, referenced in the relevant function).
- **`tests/` directory** — Follows the convention already documented in [constraints.md](../../docs/agents/project-manifest/constraints.md): "place new test files in a `tests/` subdirectory going forward."
- **`verify_*.py` naming** — Retained as-is per the documented testing convention.

## Detailed Steps

### Step 1: Add `_guard_input_path()` helper to `nodes.py`

Add a new module-level helper function after `_list_json_files()` (line ~240, before `_raise_getter_error`):

```python
def _guard_input_path(filename):
    """Resolve a filename relative to the input directory and validate it stays within bounds.

    Returns the resolved real path. Raises ValueError if the filename is empty
    (no file selected) or if the resolved path escapes the input directory.
    """
    if not filename:
        raise ValueError(
            "No file selected \u2014 add .json files to the input directory and restart ComfyUI."
        )
    input_dir = folder_paths.get_input_directory()
    real_input = os.path.realpath(input_dir)
    candidate = os.path.realpath(os.path.join(input_dir, filename))
    if not candidate.startswith(real_input + os.sep) and candidate != real_input:
        raise ValueError(
            f"File path resolves outside the input directory: {filename!r}"
        )
    return candidate
```

### Step 2: Add `_MAX_JSON_FILE_SIZE` constant to `nodes.py`

Add at module level, near the existing `_KEY_COMPONENT_MAX_LENGTH` constant (or near the top of the file after imports):

```python
_MAX_JSON_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
```

### Step 3: Refactor `LoadJsonNode.fingerprint_inputs()` to use `_guard_input_path()`

Replace the inline path-traversal logic:

```python
@classmethod
def fingerprint_inputs(cls, filename):
    """Return the file's mtime so ComfyUI re-executes when content changes."""
    try:
        real_path = _guard_input_path(filename)
    except ValueError:
        return ""
    try:
        return str(os.path.getmtime(real_path))
    except OSError:
        return ""
```

Note: `fingerprint_inputs()` must not raise — it returns `""` on any error so ComfyUI falls back to re-execution.

### Step 4: Refactor `LoadJsonNode.execute()` to use `_guard_input_path()` and add file-size cap

Replace the inline path-traversal guard and add the file-size check:

```python
@classmethod
def execute(cls, filename):
    # --- Path validation (includes empty-filename guard) ---
    candidate = _guard_input_path(filename)

    # --- File-size guard ---
    try:
        file_size = os.path.getsize(candidate)
    except OSError as exc:
        raise ValueError(f"Cannot access JSON file {filename!r}: {exc}") from exc
    if file_size > _MAX_JSON_FILE_SIZE:
        raise ValueError(
            f"JSON file {filename!r} is {file_size:,} bytes, which exceeds the "
            f"{_MAX_JSON_FILE_SIZE:,}-byte limit."
        )

    # --- Read and parse ---
    try:
        with open(candidate, 'r', encoding='utf-8') as fh:
            raw = fh.read()
    except OSError as exc:
        raise ValueError(f"Cannot read JSON file {filename!r}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Malformed JSON in file {filename!r}: {exc}"
        ) from exc

    # --- Validate top-level type ---
    if not isinstance(data, dict):
        raise ValueError(
            f"JSON file {filename!r} must contain a top-level object (dict), "
            f"but got {type(data).__name__}."
        )

    return io.NodeOutput(data)
```

### Step 5: Create `tests/` directory and move `verify_wp003.py`

1. Create `tests/` directory in the project root.
2. Move `verify_wp003.py` to `tests/verify_wp003.py`.
3. Update the repo-root path resolution in the script: change `os.path.dirname(os.path.abspath(__file__))` to `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` to account for the extra directory level.

### Step 6: Add new test cases to `tests/verify_wp003.py`

Add two new test cases after the existing AC tests:

**Empty-filename guard test:**
```python
# REWORK: Empty-filename guard
try:
    L.execute('')
    fail("REWORK-empty-filename", "no ValueError raised for empty filename")
except ValueError as e:
    assert 'no file selected' in str(e).lower(), str(e)
    ok("REWORK-empty-filename: empty string raises clear ValueError")
```

**File-size cap test:**
```python
# REWORK: File-size cap
import nodes as nd_mod
old_max = nd_mod._MAX_JSON_FILE_SIZE
try:
    nd_mod._MAX_JSON_FILE_SIZE = 10  # 10 bytes
    with open(f1, 'w') as fh:
        fh.write('{"key": "a very long value that exceeds 10 bytes"}')
    try:
        L.execute('config.json')
        fail("REWORK-file-size-cap", "no ValueError raised for oversized file")
    except ValueError as e:
        assert 'exceeds' in str(e).lower() or 'limit' in str(e).lower(), str(e)
        ok("REWORK-file-size-cap: oversized file raises clear ValueError")
finally:
    nd_mod._MAX_JSON_FILE_SIZE = old_max
```

**`_guard_input_path()` helper test:**
```python
# REWORK: _guard_input_path helper
from nodes import _guard_input_path
try:
    _guard_input_path('')
    fail("REWORK-guard-empty", "no ValueError for empty filename")
except ValueError:
    ok("REWORK-guard-empty: _guard_input_path rejects empty filename")

try:
    _guard_input_path('../../etc/passwd')
    fail("REWORK-guard-traversal", "no ValueError for path traversal")
except ValueError:
    ok("REWORK-guard-traversal: _guard_input_path rejects traversal")

result = _guard_input_path('config.json')
assert os.path.isabs(result), f"expected absolute path, got: {result}"
ok("REWORK-guard-valid: _guard_input_path returns resolved path for valid file")
```

**`fingerprint_inputs('')` guard test:**
```python
# REWORK: fingerprint_inputs returns "" for empty filename (AC 7)
fp_empty = L.fingerprint_inputs('')
assert fp_empty == '', repr(fp_empty)
ok("REWORK-fingerprint-empty: fingerprint_inputs('') returns '' without raising")
```

### Step 7: Delete `qa_test_wp003.py`

Remove the file from the repo root. It contains no assertions and serves no purpose beyond a comment pointing to `verify_wp003.py`.

### Step 8: Update documentation

Update all affected documentation per AGENTS.md maintenance rules.

## Dependencies

- No new external dependencies. All changes use stdlib (`os`, `json`) and existing ComfyUI builtins.
- Steps 1–2 must complete before steps 3–4 (the helper and constant must exist before they are referenced).
- Step 5 must complete before step 6 (test cases are added to the moved file).
- Step 7 is independent.
- Step 8 depends on all code changes being finalized.

## Required Components

- [nodes.py](../../nodes.py) — New `_guard_input_path()` helper, `_MAX_JSON_FILE_SIZE` constant, refactored `LoadJsonNode.fingerprint_inputs()` and `LoadJsonNode.execute()` (modified).
- [verify_wp003.py](../../verify_wp003.py) → [tests/verify_wp003.py](../../tests/verify_wp003.py) — Moved + path fix + new test cases (moved, modified).
- [qa_test_wp003.py](../../qa_test_wp003.py) — Deleted.
- [docs/agents/project-manifest/api-surface.md](../../docs/agents/project-manifest/api-surface.md) — Add `_guard_input_path()` and `_MAX_JSON_FILE_SIZE` entries (modified).
- [docs/agents/project-manifest/file-tree.md](../../docs/agents/project-manifest/file-tree.md) — Add `tests/` directory, remove `qa_test_wp003.py`, move `verify_wp003.py` (modified).
- [docs/agents/project-manifest/constraints.md](../../docs/agents/project-manifest/constraints.md) — Add file-size limit constraint (modified).
- [AGENTS.md](../../AGENTS.md) — Add `_guard_input_path` to helper list in section 6; add `tests/` directory (modified).
- [changelog.md](../../changelog.md) — Add rework entry (modified).

## Assumptions

- 50 MB is a safe upper bound for JSON files in ComfyUI workflows. If a legitimate use case exceeds this, the constant can be raised.
- `verify_wp003.py` is the only test file that needs moving (no other `verify_*.py` files exist in the root).
- The `gen_qa.ps1`, `gen_test.py`, `mk_test.py`, `ps_test.ps1`, `b64.txt`, and `b64chunk.txt` files in the repo root are development utilities unrelated to this plan and should not be moved.

## Constraints

- **No new external dependencies** — all changes use stdlib.
- **No behavioral changes to existing nodes** — only `LoadJsonNode` is modified.
- **`SaveJsonNode` guard is NOT refactored** — its path-traversal guard validates a subfolder (structurally different from a filename). Extracting a shared helper would require a divergent API. Leave it as-is.
- **V3 API only** — no V1 fallback.

## Out of Scope

- **Windows reserved device name filtering** — not applicable to `LoadJsonNode` (combo-based selection from actual files). Relevant only if freeform filename input nodes are added in the future.
- **Refactoring `SaveJsonNode` path guard** — structurally different from `LoadJsonNode`'s guard; would require a different helper signature.
- **Test runner / pytest integration** — the project uses standalone scripts; adding a test framework is a separate concern.
- **Migrating other root-level utility scripts** (e.g. `gen_test.py`, `mk_test.py`) — these are development utilities, not test files.

## Acceptance Criteria

1. `_guard_input_path(filename)` exists as a module-level helper in `nodes.py` and is used by both `LoadJsonNode.fingerprint_inputs()` and `LoadJsonNode.execute()`.
2. `_guard_input_path('')` raises `ValueError` with a message containing "no file selected".
3. `_guard_input_path('../../etc/passwd')` raises `ValueError`.
4. `_guard_input_path('valid_file.json')` returns the resolved absolute path.
5. `_MAX_JSON_FILE_SIZE` constant exists at module level in `nodes.py` with a value of `50 * 1024 * 1024`.
6. `LoadJsonNode.execute()` raises `ValueError` when the selected file exceeds `_MAX_JSON_FILE_SIZE`.
7. `LoadJsonNode.fingerprint_inputs('')` returns `""` (does not raise).
8. `tests/verify_wp003.py` exists and passes all tests (including the new rework tests).
9. `qa_test_wp003.py` no longer exists in the repo root.
10. All documentation listed in Documentation Updates is updated.

## Testing Strategy

Mock-based unit tests in `tests/verify_wp003.py` (consistent with the project's established two-tier testing strategy). New test cases are added for the empty-filename guard, file-size cap, and `_guard_input_path()` helper directly.

## Test Plan

- `tests/verify_wp003.py` — **REWORK-empty-filename** — `execute('')` raises `ValueError` with "no file selected" — AC 2
- `tests/verify_wp003.py` — **REWORK-file-size-cap** — `execute()` with file exceeding `_MAX_JSON_FILE_SIZE` raises `ValueError` with "exceeds" — AC 6
- `tests/verify_wp003.py` — **REWORK-guard-empty** — `_guard_input_path('')` raises `ValueError` — AC 2
- `tests/verify_wp003.py` — **REWORK-guard-traversal** — `_guard_input_path('../../etc/passwd')` raises `ValueError` — AC 3
- `tests/verify_wp003.py` — **REWORK-guard-valid** — `_guard_input_path('config.json')` returns absolute path — AC 4
- `tests/verify_wp003.py` — **REWORK-fingerprint-empty** — `fingerprint_inputs('')` returns `""` without raising — AC 7
- `tests/verify_wp003.py` — **All existing AC1–AC9 tests** — Continue to pass (regression) — AC 8

## Documentation Updates

Per AGENTS.md maintenance rules:

- [docs/agents/project-manifest/api-surface.md](../../docs/agents/project-manifest/api-surface.md) — Add `_guard_input_path(filename)` to Private Helper Functions section (parameters: `filename: str`; returns: resolved absolute path or raises `ValueError`; called by `LoadJsonNode.fingerprint_inputs()` and `LoadJsonNode.execute()`). Add `_MAX_JSON_FILE_SIZE` to constants section.
- [docs/agents/project-manifest/file-tree.md](../../docs/agents/project-manifest/file-tree.md) — Add `tests/` directory with `verify_wp003.py`. Remove `qa_test_wp003.py` from root listing. Update `nodes.py` helper list to include `_guard_input_path`.
- [docs/agents/project-manifest/constraints.md](../../docs/agents/project-manifest/constraints.md) — Add file-size limit constraint for `LoadJsonNode` under Non-Negotiable Design Decisions or Behavioral Invariants.
- [docs/agents/project-manifest/data-flows.md](../../docs/agents/project-manifest/data-flows.md) — Update `LoadJsonNode` execution flow (steps 3–5): reflect the empty-filename guard, the `_guard_input_path()` helper call, and the file-size check step; update step 3 to note `fingerprint_inputs()` returns `""` (instead of raising) on any guard error.
- [docs/agents/projects/json-node-project.md](../../docs/agents/projects/json-node-project.md) — Add a note to the `LoadJsonNode` spec section documenting the 50 MB file-size cap and the empty-filename guard error message as new behavioral constraints.
- [README.md](../../README.md) — Acknowledge the `LoadJsonNode` behavior change per AGENTS.md maintenance rules. The 50 MB cap and empty-filename guard are implementation-level constraints; a brief note is sufficient (e.g., "Files larger than 50 MB are rejected").
- [AGENTS.md](../../AGENTS.md) — Update section 6 (Project File Layout): add `_guard_input_path` to helper list in `nodes.py` comment; add `tests/` directory with `verify_wp003.py`; remove `qa_test_wp003.py`.
- [changelog.md](../../changelog.md) — Add rework entry documenting the three code changes and two organizational changes.

## Deferred Items

| # | Deferred Item | Origin | Reason Deferred | Notes |
|---|---------------|--------|-----------------|-------|
| 1 | Windows reserved device name filtering | Synthesis (inherited from prior cycle security audit) | Not applicable to `LoadJsonNode` — file selection is combo-based from actual files, not freeform text input | Reconsider if any node is added that accepts freeform filename input |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Moving `verify_wp003.py` breaks its repo-root path resolution** | Step 5 explicitly updates the `os.path.dirname()` call to account for the extra directory level. The test is re-run after the move to confirm. |
| **50 MB file-size cap is too low for some use case** | The constant is module-level and clearly named; adjusting it is a one-line change. 50 MB is far above typical JSON config files. |
| **`_guard_input_path()` changes error messages, breaking downstream expectations** | The error messages are end-user-facing `ValueError` strings, not API contracts. The test suite verifies the new messages. |
| **Deleting `qa_test_wp003.py` loses information** | The file contains zero assertions. Its only content (a pointer to `verify_wp003.py`) is obsoleted by moving the test to a discoverable location. |
