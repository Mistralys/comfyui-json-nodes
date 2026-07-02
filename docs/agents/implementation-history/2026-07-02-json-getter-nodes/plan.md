# Plan

## Plan Audit Cycles
- Audits: none — Plan Auditor v1.5.0
- Architectural Reviews: none — Plan Architect Reviewer v1.6.0

## Prior Project Context

The initial `2026-07-02-json-nodes` project delivered 8 ComfyUI V3 custom nodes (4 primitive setters, 2 structural, 1 serialization, 1 file output) with 164/164 QA tests passing. Key patterns established: `io.Custom("JSON_OBJECT")` custom type, `_set_nested_key()` dot-notation traversal, `_sanitize_key()` input validation, `_coerce_json_object()` type guard, deep-copy-on-input for fork-safety, and same-reference passthrough for read-only outputs. The `2026-07-02-tooltips-merge-node` follow-up added tooltips to all I/O and introduced `JsonMergeObjectsNode` (6 merge inputs). Both projects are COMPLETE. This plan extends the extension with complementary getter nodes that read values back out of JSON objects.

## Summary

Add five JSON getter nodes to the existing `comfyui-json-nodes` extension. These nodes read values from a JSON object by dot-notation key path and return them as typed outputs (string, int, float, bool, or nested object), applying tacit type conversion when the stored type differs from the requested type. Each node supports configurable error triggering (missing key, empty/zero value) with a customizable error message, and passes through all control inputs for downstream chaining. The getter nodes complete the read/write symmetry of the JSON node family, transforming the JSON object from a metadata-collection tool into a general-purpose in-workflow data store.

## Architectural Context

The existing codebase in `nodes.py` contains:

- **Module-level constants**: `JsonObject = io.Custom("JSON_OBJECT")`, `_KEY_COMPONENT_MAX_LENGTH = 40`
- **Helper functions**: `_set_nested_key()`, `_get_next_counter()`, `_coerce_json_object()`, `_sanitize_key()`
- **8 node classes**: `JsonStringNode`, `JsonIntNode`, `JsonFloatNode`, `JsonBooleanNode`, `JsonObjectNode`, `JsonMergeObjectsNode`, `JsonToStringNode`, `SaveJsonNode`
- **Registration** in `__init__.py`: `JsonNodesExtension.get_node_list()` returns all 8 classes

All setter nodes follow an identical pattern: optional `json_object` input → deep-copy → `_set_nested_key()` → `io.NodeOutput(obj, value, key)`. The getter nodes will follow a parallel pattern but read instead of write, and do not mutate the object.

Error handling uses `raise ValueError(...)` — ComfyUI surfaces these as execution errors in the UI. This is the established pattern in `SaveJsonNode` and `_sanitize_key()`.

## Approach / Architecture

### New Helper Functions

Add to `nodes.py`, after the existing helpers:

1. **`_MISSING` sentinel** — A module-level sentinel object (`object()`) to distinguish "key not found" from `None` values stored in the JSON. Required because `None` is a valid JSON value (`null`).

2. **`_get_nested_value(obj, key)`** — The read counterpart of `_set_nested_key()`. Splits `key` on `"."`, traverses the dict, and returns the value at the leaf. Returns `_MISSING` if any intermediate key is absent or non-dict.

3. **`_coerce_to_string(value, precision)`** — Converts any JSON-storable value to a string per the conversion matrix. `precision` controls decimal rounding for float values (0 = whole number).

4. **`_coerce_to_int(value)`** — Converts any JSON-storable value to an integer per the conversion matrix.

5. **`_coerce_to_float(value, precision)`** — Converts any JSON-storable value to a float per the conversion matrix. `precision` controls rounding (0 = no rounding).

6. **`_coerce_to_bool(value)`** — Converts any JSON-storable value to a boolean per the conversion matrix.

### Getter Node Family

Five node classes, all in `nodes.py`, placed between `JsonMergeObjectsNode` and `JsonToStringNode`:

| Node Class | Display Name | Node ID | Value Output Type | Error Modes |
|---|---|---|---|---|
| `JsonGetStringNode` | JSON Get String | `Mistralys_JsonGetString` | `String` | missing, empty |
| `JsonGetIntNode` | JSON Get Int | `Mistralys_JsonGetInt` | `Int` | missing, zero |
| `JsonGetFloatNode` | JSON Get Float | `Mistralys_JsonGetFloat` | `Float` | missing, zero |
| `JsonGetBoolNode` | JSON Get Bool | `Mistralys_JsonGetBool` | `Bool` | missing |
| `JsonGetObjectNode` | JSON Get Object | `Mistralys_JsonGetObject` | `JSON_OBJECT` | missing, empty |

### Shared Getter Pattern

All five nodes follow the same structural pattern:

```
Inputs:
  json_object    — JsonObject, mandatory
  key            — String, default "key"
  error_on_*     — Boolean flags (node-specific, see per-node details)
  error_message  — String, default "" (custom error message; uses default if empty)
  precision      — Int (only on Get String and Get Float)

Outputs:
  JSON_OBJECT    — passthrough of json_object (same reference, no deep-copy)
  VALUE          — the coerced value
  error_on_*     — passthrough of each error flag
  ERROR_MESSAGE  — passthrough of error_message
  precision      — passthrough (only on Get String and Get Float)

Execute:
  1. Sanitize key via _sanitize_key()
  2. Coerce json_object via _coerce_json_object() (guard against non-dict)
  3. Look up value via _get_nested_value()
  4. Coerce value to target type via _coerce_to_*()
  5. Check error conditions; raise ValueError if triggered
  6. Return (json_object, coerced_value, ...passthroughs)
```

### Error Message Input

Every getter node has an `error_message` string input (default `""`). When an error condition is triggered (e.g. missing key, empty value, zero value), the node checks this input:
- If non-empty after `strip()`: raises `ValueError` with the custom message.
- If empty: raises `ValueError` with a default message that includes the key name and the error condition (e.g. `"JSON key 'address.city' not found"`).

This allows workflow builders to provide context-specific error messages (e.g. `"Model name is required"`) instead of generic key-path errors.

### Error Evaluation Order

When multiple error flags are enabled and both conditions are true (e.g. a missing key triggers both `error_on_missing` and `error_on_empty`), `error_on_missing` is evaluated first. This avoids redundant "empty" errors when the root cause is a missing key. Evaluation order:

1. `error_on_missing` — checked immediately after `_get_nested_value()` returns `_MISSING`
2. `error_on_empty` / `error_on_zero` — checked after type coercion on the resolved value

### Passthrough Design

Getter nodes pass through `json_object` as the **same reference** (no deep-copy). This is safe because getter nodes do not mutate the object — identical to the `JsonToStringNode` passthrough pattern. The passthrough enables chaining: `JSON Object → Get String → Get Int → ...` reads multiple values from the same object without extra connections.

All control inputs (error flags, precision, error_message) are passed through as outputs so that downstream getter nodes of the same type can inherit the same configuration when daisy-chained.

### Tacit Type Conversion Matrix

Implemented in the `_coerce_to_*` helpers. The full matrix from the spec:

| Source → Target | String | Int | Float | Bool | Object |
|---|---|---|---|---|---|
| **String** | identity | numeric→int, else `0` | numeric→float, else `0.0` | `"1"`/`"true"`/`"yes"` (ci) → `True`, else `False` | `{}` (unsupported) |
| **Int** | `str(v)` | identity | `float(v)` | `v != 0` | `{}` (treat as null) |
| **Float** | see precision | `round(v)` | identity | `round(v) != 0` | `{}` (treat as null) |
| **Bool** | `"true"`/`"false"` | `1`/`0` | `1.0`/`0.0` | identity | `{}` (treat as null) |
| **None/Missing** | `""` | `0` | `0.0` | `False` | `{}` |
| **list (Array)** | treat as None | treat as None | treat as None | treat as None | `{}` (treat as null) |
| **dict (Object)** | `json.dumps()` | treat as None → `0` | treat as None → `0.0` | treat as None → `False` | identity |

### Precision Semantics

- **Get String** `precision` input: Controls decimal display when converting float→string. `precision=0` means whole number (e.g. `3.14` → `"3"`). `precision=2` → `"3.14"`. Default `precision=0`.
- **Get Float** `precision` input: Controls rounding of the output float. `precision=0` means no rounding (full float precision). `precision=2` → `round(v, 2)`. Default `precision=0`.

## Rationale

- **Tacit type conversion** — The primary design goal. Users should be able to read any stored value as any type without explicit conversion nodes. This keeps workflows compact and approachable. The conversion rules are intentionally lenient (never raise on type mismatch — always produce a sensible default).
- **Error flags as inputs (not schema options)** — Making error conditions configurable via boolean inputs (rather than hardcoded behavior) lets users wire them dynamically. The passthrough pattern means a single toggle propagates to all downstream getters.
- **Custom error message** — A single `error_message` input shared across all error conditions keeps the node simple while giving workflow builders the ability to surface meaningful context when a required value is absent or invalid. The empty-string-means-default convention avoids forcing users to write messages for every node.
- **Same-reference passthrough** — No deep-copy needed because getters are pure reads. This is more efficient and consistent with `JsonToStringNode`.
- **Sentinel vs. `None`** — A `_MISSING` sentinel is necessary because `json.loads()` maps JSON `null` to Python `None`, which is a valid stored value. Without the sentinel, we cannot distinguish "key exists with value null" from "key does not exist."
- **Helpers over base class** — Consistent with the setter node architecture decision. The 5 getter nodes differ in their I/O declarations and coercion logic, but share the lookup + error-check flow via helper functions.
- **Placement between structural and serialization nodes** — Getters logically sit between "build the object" (setters/structural) and "output the object" (serialization/save), mirroring the typical workflow order.

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|---|---|---|---|
| Error reporting | `raise ValueError()` | `block_execution` return, separate error output | `ValueError` is the established pattern in this codebase and produces clear UI feedback; `block_execution` silently stops the pipeline without an error message; a separate error output adds complexity. |
| Single error_message vs. per-condition messages | Single `error_message` input for all conditions | Separate `missing_message` / `empty_message` / `zero_message` inputs | One input keeps nodes compact; the error condition is always clear from context (missing vs. empty); per-condition messages would add 2-3 inputs per node with minimal practical benefit. |
| Coercion approach | Per-type helper functions | Single `_coerce(value, target_type)` dispatcher | Per-type helpers are more readable, testable, and allow type-specific parameters (e.g. `precision`). A single dispatcher would need complex branching and parameter forwarding. |
| Get Object deep-copy | Deep-copy the extracted sub-object for the VALUE output | Same-reference passthrough | Fork-safety: if two downstream nodes receive the same extracted sub-object and one mutates it (e.g. via a setter node), the other would see the mutation. Deep-copy prevents this, consistent with `JsonObjectNode`'s value handling. |
| Precision default for Get String | `0` (whole number) | `2` or `-1` (disable) | `0` is the most conservative default — float values appear as clean integers unless the user explicitly requests decimals. This matches the most common metadata use case (steps, seeds, dimensions). |
| Precision default for Get Float | `0` (no rounding) | `2` (common precision) | `0` meaning "no rounding" preserves full precision by default. Users opt into rounding explicitly. This avoids silent precision loss. |

## Pattern Alignment

- **V3 node class structure** (`io.ComfyNode` + `define_schema()` + `execute()`) — follows all existing nodes in `nodes.py`.
- **`_sanitize_key()` reuse** — getter nodes validate keys through the same sanitizer as setter nodes.
- **`_coerce_json_object()` reuse** — getter nodes guard against non-dict inputs the same way setter nodes do.
- **Passthrough output convention** — follows the `VALUE`/`KEY` passthrough pattern established in all setter nodes.
- **`raise ValueError()` for errors** — follows `SaveJsonNode` and `_sanitize_key()` error pattern.
- **Tooltip on every I/O** — follows the convention established in the tooltips-merge-node project.
- **Category `"json"`** — all nodes in the same flat category.
- **Node ID prefix `Mistralys_`** — follows the existing naming convention.

## Detailed Steps

### Step 1: Add `_MISSING` Sentinel and `_get_nested_value()` Helper

In `nodes.py`, after the existing helper functions, add:

**`_MISSING`** — A module-level sentinel:
```python
_MISSING = object()
```

**`_get_nested_value(obj, key)`** — The read counterpart of `_set_nested_key()`:
- Split `key` on `"."`.
- Traverse the dict. If any intermediate part is missing or not a dict, return `_MISSING`.
- Return the value at the final part, or `_MISSING` if the final part is absent.

### Step 2: Add Type Coercion Helpers

In `nodes.py`, after `_get_nested_value()`, add four coercion functions:

**`_coerce_to_string(value, precision)`**:
- `_MISSING` or `None` → `""`
- `bool` → `"true"` / `"false"` (must check before `int` since `bool` is subclass of `int`)
- `int` → `str(value)`
- `float` → format with `precision` decimals (0 = whole number via `str(int(round(value)))`)
- `dict` → `json.dumps(value, indent=2, ensure_ascii=False)`
- `list` → `""` (treat as missing)
- other → `str(value)`

**`_coerce_to_int(value)`**:
- `_MISSING` or `None` → `0`
- `bool` → `1` / `0` (check before `int`)
- `int` → identity
- `float` → `round(value)`
- `str` → try `int(float(value))`, fallback `0`
- `dict` / `list` → `0`

**`_coerce_to_float(value, precision)`**:
- `_MISSING` or `None` → `0.0`
- `bool` → `1.0` / `0.0` (check before `int`)
- `int` → `float(value)`
- `float` → identity
- `str` → try `float(value)`, fallback `0.0`
- `dict` / `list` → `0.0`
- If `precision > 0`: apply `round(result, precision)`

**`_coerce_to_bool(value)`**:
- `_MISSING` or `None` → `False`
- `bool` → identity
- `int` → `value != 0`
- `float` → `round(value) != 0`
- `str` → `value.strip().lower() in ("1", "true", "yes")`
- `dict` / `list` → `False`

### Step 3: Add `_raise_getter_error()` Helper

A shared helper to keep error-raising consistent across all getter nodes:

**`_raise_getter_error(key, condition, custom_message)`**:
- If `custom_message.strip()` is non-empty: `raise ValueError(custom_message.strip())`
- Else: `raise ValueError(f"JSON getter error: {condition} (key: '{key}')")`

Where `condition` is a string like `"value not found"`, `"value is empty"`, `"value is zero"`.

### Step 4: Implement `JsonGetStringNode`

```python
class JsonGetStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetString",
            display_name="JSON Get String",
            category="json",
            description="Read a value from a JSON object as a string. Supports dot notation (e.g. 'address.city') and automatic type conversion.",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the value from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the value. Use dots (e.g. 'address.city') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.Boolean.Input("error_on_empty", default=False,
                    tooltip="Raise an error if the resolved value is an empty string (or the key does not exist).",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
                io.Int.Input("precision", default=0, min=0, max=10,
                    tooltip="When converting float values, number of decimal places. 0 = whole number.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                io.String.Output("VALUE",
                    tooltip="The resolved value as a string.",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.Boolean.Output("ERROR_ON_EMPTY",
                    tooltip="Passthrough of the error_on_empty setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
                io.Int.Output("PRECISION",
                    tooltip="Passthrough of the precision setting.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_on_empty, error_message, precision):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        result = _coerce_to_string(raw, precision)

        if error_on_empty and result == "":
            _raise_getter_error(key, "value is empty", error_message)

        return io.NodeOutput(json_object, result, error_on_missing, error_on_empty, error_message, precision)
```

### Step 5: Implement `JsonGetIntNode`

Same pattern as Step 4 but with:
- `node_id="Mistralys_JsonGetInt"`, `display_name="JSON Get Int"`
- `description="Read a value from a JSON object as an integer. Supports dot notation and automatic type conversion."`
- Replace `error_on_empty` with `error_on_zero` (Boolean, default `False`, tooltip: `"Raise an error if the resolved value is 0."`)
- No `precision` input
- Output: `io.Int.Output("VALUE")`, passthrough `ERROR_ON_ZERO`
- Coercion: `_coerce_to_int(raw)`
- Error check: `if error_on_zero and result == 0`

### Step 6: Implement `JsonGetFloatNode`

Same pattern as Step 4 but with:
- `node_id="Mistralys_JsonGetFloat"`, `display_name="JSON Get Float"`
- `description="Read a value from a JSON object as a float. Supports dot notation and automatic type conversion."`
- Replace `error_on_empty` with `error_on_zero` (Boolean, default `False`, tooltip: `"Raise an error if the resolved value is 0.0."`)
- Has `precision` input (default `0`, tooltip: `"Number of decimal places to round to. 0 = no rounding (full precision)."`)
- Output: `io.Float.Output("VALUE")`, passthrough `ERROR_ON_ZERO`, `PRECISION`
- Coercion: `_coerce_to_float(raw, precision)`
- Error check: `if error_on_zero and result == 0.0`

### Step 7: Implement `JsonGetBoolNode`

Same pattern as Step 4 but with:
- `node_id="Mistralys_JsonGetBool"`, `display_name="JSON Get Bool"`
- `description="Read a value from a JSON object as a boolean. Supports dot notation and automatic type conversion."`
- Only `error_on_missing` (no empty/zero — a boolean is always `True` or `False`)
- No `precision` input
- Output: `io.Boolean.Output("VALUE")`, passthrough `ERROR_ON_MISSING`, `ERROR_MESSAGE`
- Coercion: `_coerce_to_bool(raw)`

### Step 8: Implement `JsonGetObjectNode`

Same pattern as Step 4 but with:
- `node_id="Mistralys_JsonGetObject"`, `display_name="JSON Get Object"`
- `description="Read a nested object from a JSON object. Supports dot notation for deep access."`
- Has `error_on_empty` (Boolean, default `False`, tooltip: `"Raise an error if the resolved object is empty ({}) or the key does not exist."`)
- No `precision` input
- Output: `JsonObject.Output("VALUE")` — the extracted sub-object is **deep-copied** for fork-safety
- Coercion: if value is a dict, deep-copy it; if `_MISSING`/`None`/list/non-dict → empty `{}`
- Error check: `if error_on_empty and result == {}`

### Step 9: Register Getter Nodes

In `__init__.py`:
1. Add imports for the 5 new classes: `JsonGetStringNode`, `JsonGetIntNode`, `JsonGetFloatNode`, `JsonGetBoolNode`, `JsonGetObjectNode`
2. Add them to `get_node_list()` return list, after `JsonMergeObjectsNode` and before `JsonToStringNode`

### Step 10: Update Project Specification

In `docs/agents/projects/json-getter-nodes.md`:
- Add the `error_message` string input to each node's specification
- Add the `error_message` passthrough to each node's output list

## Dependencies

- No new external dependencies. All coercion logic uses Python stdlib (`json.dumps` for Object→String, which is already imported).
- The 5 getter nodes depend on the new helper functions (`_MISSING`, `_get_nested_value`, `_coerce_to_*`, `_raise_getter_error`).
- Registration depends on all 5 node classes being implemented.

## Required Components

### New (to be created)

| Component | Location | Purpose |
|---|---|---|
| `_MISSING` sentinel | `nodes.py` (module level) | Distinguish missing keys from `None` values |
| `_get_nested_value()` | `nodes.py` (module level) | Read value from nested dict by dot-notation key |
| `_coerce_to_string()` | `nodes.py` (module level) | Type conversion to string |
| `_coerce_to_int()` | `nodes.py` (module level) | Type conversion to int |
| `_coerce_to_float()` | `nodes.py` (module level) | Type conversion to float |
| `_coerce_to_bool()` | `nodes.py` (module level) | Type conversion to bool |
| `_raise_getter_error()` | `nodes.py` (module level) | Shared error-raising logic |
| `JsonGetStringNode` | `nodes.py` | JSON Get String node |
| `JsonGetIntNode` | `nodes.py` | JSON Get Int node |
| `JsonGetFloatNode` | `nodes.py` | JSON Get Float node |
| `JsonGetBoolNode` | `nodes.py` | JSON Get Bool node |
| `JsonGetObjectNode` | `nodes.py` | JSON Get Object node |

### Modified (existing)

| Component | Location | Change |
|---|---|---|
| `JsonNodesExtension` | `__init__.py` | Add 5 imports + 5 entries in `get_node_list()` |

## Assumptions

- `raise ValueError(message)` is surfaced as a user-visible error in ComfyUI's execution UI — consistent with existing usage in `SaveJsonNode` and `_sanitize_key()`.
- `io.Boolean.Input()` renders as a checkbox/toggle widget in ComfyUI's node UI.
- `io.Int.Input()` with `min`/`max` renders as a number widget.
- The `json_object` mandatory input (non-optional) will cause ComfyUI to require a connection before execution — nodes without a connected JSON object will not run.
- `_coerce_json_object()` will handle unexpected non-dict values from Reroute nodes, consistent with the existing setter pattern.
- The `tooltip` parameter works on `io.Custom()` type inputs/outputs (established in the tooltips-merge-node project).

## Constraints

- **V3 API only** — no V1 compatibility layer.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **Dot notation always active** — keys containing dots are always interpreted as nested paths. No escape mechanism.
- **No mutation** — getter nodes must never modify the incoming JSON object.
- **Bool-before-int checks** — In all coercion functions, `isinstance(value, bool)` must be checked before `isinstance(value, int)` because `bool` is a subclass of `int` in Python.
- **Array values unsupported** — `list` values are treated as missing/null (consistent with spec).

## Out of Scope

- Array/list support in JSON objects (explicitly noted as "currently not supported" in the spec).
- Recursive/deep merge in `JsonMergeObjectsNode` (established as top-level-only in existing code).
- `block_execution` as an alternative to `ValueError` for error handling.
- Lazy input evaluation — all inputs are eagerly evaluated.
- Default value input (e.g. "return this instead of raising an error") — the user chose error flags, not fallback values.

## Acceptance Criteria

1. All 5 getter nodes appear in ComfyUI under the `json` category.
2. Each getter node reads values from a JSON object using dot-notation key paths.
3. Tacit type conversion works for all combinations in the conversion matrix (string↔int↔float↔bool, object→string, null/missing→defaults).
4. `error_on_missing` raises a `ValueError` when enabled and the key is absent.
5. `error_on_empty` raises a `ValueError` when enabled and the resolved string or object is empty (or the key is absent).
6. `error_on_zero` raises a `ValueError` when enabled and the resolved int or float is zero.
7. When `error_message` is non-empty, the custom message is used in the `ValueError`. When empty, a default message including the key path is used.
8. All control inputs (error flags, precision, error_message) are passed through as outputs.
9. `json_object` is passed through as the same reference (no deep-copy).
10. `JsonGetObjectNode` deep-copies the extracted sub-object for fork-safety.
11. `precision` in Get String: `0` = whole number, `>0` = that many decimal places.
12. `precision` in Get Float: `0` = no rounding, `>0` = round to that many places.
13. No existing tests, nodes, or behaviors are broken.
14. All new nodes have tooltips on every input and output.
15. `__init__.py` registers all 13 nodes (8 existing + 5 new).
16. Project specification is updated with the `error_message` input/output.

## Testing Strategy

This project follows the established convention of manual testing in ComfyUI (no automated test framework). Testing will verify each node's type coercion, error triggering, and passthrough behavior through interactive workflow construction.

## Test Plan

Manual test scenarios to verify in ComfyUI:

- **T01** — JSON Get String: store a string, retrieve it → exact match. — AC 2
- **T02** — JSON Get String: store an int `42`, retrieve as string → `"42"`. — AC 3
- **T03** — JSON Get String: store a float `3.14`, retrieve with precision=2 → `"3.14"`, precision=0 → `"3"`. — AC 3, 11
- **T04** — JSON Get String: store a bool `true`, retrieve → `"true"`. — AC 3
- **T05** — JSON Get String: store an object, retrieve → JSON string. — AC 3
- **T06** — JSON Get String: missing key, error_on_missing=true → error raised. — AC 4
- **T07** — JSON Get String: missing key, error_on_empty=true → error raised (subsumes missing). — AC 5
- **T08** — JSON Get String: empty string value, error_on_empty=true → error raised. — AC 5
- **T09** — JSON Get String: custom error_message → custom text in error. — AC 7
- **T10** — JSON Get Int: store `"42"`, retrieve → `42`. — AC 3
- **T11** — JSON Get Int: store `3.7`, retrieve → `4` (rounded). — AC 3
- **T12** — JSON Get Int: store `true`, retrieve → `1`. — AC 3
- **T13** — JSON Get Int: store `"not a number"`, retrieve → `0`. — AC 3
- **T14** — JSON Get Int: value is 0, error_on_zero=true → error raised. — AC 6
- **T15** — JSON Get Float: store `"3.14"`, retrieve → `3.14`. — AC 3
- **T16** — JSON Get Float: precision=2 on `3.14159` → `3.14`. — AC 3, 12
- **T17** — JSON Get Float: precision=0 → full precision (no rounding). — AC 12
- **T18** — JSON Get Bool: store `"yes"`, retrieve → `True`. — AC 3
- **T19** — JSON Get Bool: store `0`, retrieve → `False`. — AC 3
- **T20** — JSON Get Bool: missing key, error_on_missing=true → error raised. — AC 4
- **T21** — JSON Get Object: store nested object under `"config"`, retrieve → object matches. — AC 2
- **T22** — JSON Get Object: missing key, error_on_empty=true → error (empty object). — AC 5
- **T23** — JSON Get Object: empty object `{}`, error_on_empty=true → error. — AC 5
- **T24** — JSON Get Object: extracted object mutation does not affect original. — AC 10
- **T25** — Chaining: Get String → Get Int → Get Float → Get Bool on same object. — AC 8, 9
- **T26** — Dot notation: store at `a.b.c`, retrieve at `a.b.c` → correct value. — AC 2
- **T27** — All passthrough outputs connect correctly to downstream nodes. — AC 8
- **T28** — Custom error_message with empty string → default message used. — AC 7

## Documentation Updates

Per the `AGENTS.md` documentation maintenance rules:

- `docs/agents/projects/json-getter-nodes.md` — Add `error_message` input and `ERROR_MESSAGE` output to each node specification.
- `AGENTS.md` — Update node count from "eight" to "thirteen" in Section 4 (Failure Protocol) and Section 5 (Project Stats: Architecture line). Update file layout comment.
- `README.md` — Add "Getter Nodes" section documenting the 5 new nodes with I/O tables, type conversion explanation, and error handling behavior. Update feature list and node count.
- `docs/agents/project-manifest/api-surface.md` — Add all 5 getter node schemas, the 7 new helper functions, and update `get_node_list()` count from 8 to 13.
- `docs/agents/project-manifest/data-flows.md` — Add "JSON Value Retrieval (Getter Nodes)" section describing the lookup → coerce → error-check → passthrough flow, and the type conversion matrix.
- `changelog.md` — Add entry for the getter nodes feature.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Bool/int subclass confusion** — `isinstance(True, int)` returns `True` in Python, causing bool values to be treated as integers in coercion functions. | All coercion functions check `isinstance(value, bool)` before `isinstance(value, int)`. This is documented as a constraint. |
| **Precision=0 ambiguity** — Different semantics for Get String (whole number) vs. Get Float (no rounding) could confuse users. | Document clearly in tooltips and README. The semantics are chosen to match the most useful default for each type. |
| **Deep copy performance** — `JsonGetObjectNode` deep-copies extracted sub-objects, which could be slow for very large nested structures. | Acceptable for the expected use case (metadata objects are typically small). Matches the established deep-copy pattern in setter nodes. |
| **Missing key vs. null value** — Without the `_MISSING` sentinel, `None` (JSON null) would be indistinguishable from a missing key. | The `_MISSING = object()` sentinel cleanly separates these cases. `error_on_missing` only fires for truly absent keys, not for explicit null values. |
| **Float precision edge cases** — Floating-point representation can produce unexpected results (e.g. `0.1 + 0.2 ≠ 0.3`). | `round()` is applied when `precision > 0`, which handles display rounding. Full IEEE 754 precision is preserved when `precision=0` (Get Float). |
