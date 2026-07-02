# Constraints & Conventions

## Non-Negotiable Design Decisions

These require explicit user approval to change.

- **V3 API only** — no V1 compatibility layer.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **UTF-8 encoding only** — no encoding selection.
- **Output directory only** — no arbitrary file path support.

## Behavioral Invariants

- **Dot notation always active** — keys containing dots (e.g. `address.city`) are always interpreted as nested paths. There is no escape mechanism for literal dots in key names.
- **Key sanitization on every node** — `_sanitize_key()` is called by every node (both mutating and getter) before any key is used. It strips leading/trailing whitespace, collapses internal whitespace to a single space, splits on `"."`, and validates each component is non-empty and ≤ 40 characters (`_KEY_COMPONENT_MAX_LENGTH`). Raises `ValueError` on violation. Users must ensure key components do not exceed this limit.
- **Deep copy on input** — every node deep-copies the incoming JSON object before mutation for fork-safety. Downstream nodes never see upstream mutations.
- **Counter overwrite mode** — when `counter_length` is `0`, SaveJsonNode writes the file as `{filename}.json` without a counter suffix. The file is overwritten on each run. When `counter_length > 0`, a zero-padded counter is appended (e.g. `output_00001.json`) and increments automatically.

## Project Conventions

- **Reference patterns**: Follow `skill_test_nodes/` in the companion workspace for V3 API usage.
- **Manual testing only**: No automated test suite. Nodes are tested manually in ComfyUI.
