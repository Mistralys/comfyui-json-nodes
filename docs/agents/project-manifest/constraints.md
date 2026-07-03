# Constraints & Conventions

## Non-Negotiable Design Decisions

These require explicit user approval to change.

- **V3 API only** — no V1 compatibility layer.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **UTF-8 encoding only** — no encoding selection.
- **SaveJsonNode: output directory only** — `SaveJsonNode` writes exclusively to ComfyUI's output directory. No arbitrary file path support.
- **LoadJsonNode: input directory only** — `LoadJsonNode` reads exclusively from ComfyUI's input directory. File selection is constrained to the combo dropdown (populated by scanning the input directory). No arbitrary file path support.
- **LoadJsonNode: 50 MB file-size cap** — `LoadJsonNode.execute()` rejects files larger than `_MAX_JSON_FILE_SIZE` (50 MB) with a clear `ValueError`. This prevents accidental memory exhaustion from unexpectedly large files. The limit is a module-level constant and can be adjusted if a legitimate use case requires it.

## Behavioral Invariants

- **Dot notation always active** — keys containing dots (e.g. `address.city`) are always interpreted as nested paths. There is no escape mechanism for literal dots in key names.
- **Key sanitization on every node** — `_sanitize_key()` is called by every node (both mutating and getter) before any key is used. It strips leading/trailing whitespace, collapses internal whitespace to a single space, splits on `"."`, and validates each component is non-empty and ≤ 40 characters (`_KEY_COMPONENT_MAX_LENGTH`). Raises `ValueError` on violation. Users must ensure key components do not exceed this limit.
- **Deep copy on input** — every node deep-copies the incoming JSON object before mutation for fork-safety. Downstream nodes never see upstream mutations.
- **Counter overwrite mode** — when `counter_length` is `0`, SaveJsonNode writes the file as `{filename}.json` without a counter suffix. The file is overwritten on each run. When `counter_length > 0`, a zero-padded counter is appended (e.g. `output_00001.json`) and increments automatically.

## Project Conventions

- **Reference patterns**: Follow `skill_test_nodes/` in the companion workspace for V3 API usage.
- **Testing strategy — two tiers:**
  - **Unit tests (mock-based):** Standalone Python scripts that mock `folder_paths` and other ComfyUI internals. These run without a live ComfyUI instance and are the primary regression safety net. Prefer `verify_*.py` naming; place test files in the `tests/` subdirectory (`tests/verify_wp003.py` is the current example).
  - **Manual integration tests:** Nodes must also be tested manually inside ComfyUI to validate UI rendering, combo dropdowns, and actual I/O behaviour. Unit tests cannot replace this layer.
- **Test coverage expectation**: Every new node should ship with a corresponding `verify_*.py` script covering its acceptance criteria.
