# Public API Surface

## Custom Type

| Symbol | Definition | Purpose |
|--------|-----------|---------|
| `JsonObject` | `io.Custom("JSON_OBJECT")` | Typed connection slot for JSON object dicts flowing between nodes |

## Private Helper Functions

### `_set_nested_key(obj, key, value)`

Sets a value in a nested dict using dot-notation key traversal.

| Parameter | Type | Description |
|-----------|------|-------------|
| `obj` | `dict` | The target dictionary to modify in place |
| `key` | `str` | Dot-delimited key path (e.g. `"a.b.c"`) |
| `value` | `any` | The value to set at the leaf key |

**Behavior:** Splits `key` on `"."` and traverses/creates intermediate dicts. If an intermediate key exists but is not a dict, it is overwritten with a new dict.

### `_get_next_counter(directory, filename, extension, counter_length)`

Returns the next integer counter for a filename pattern in a directory.

| Parameter | Type | Description |
|-----------|------|-------------|
| `directory` | `str` | Path to scan for existing files |
| `filename` | `str` | Base filename to match (regex-escaped internally) |
| `extension` | `str` | File extension to match (regex-escaped internally) |
| `counter_length` | `int` | Accepted for call-site consistency; does not affect the regex pattern |

**Behavior:** Scans `directory` for files matching `{filename}_{digits}.{extension}` using flexible `\d+` matching. Returns `max(found) + 1`, or `1` if no matches or if the directory is unreadable (`OSError`).

### `_coerce_json_object(value)`

Returns `value` unchanged if it is a `dict`, `None` if it is `None`, or `{}` for any other type. Guards `execute()` methods against non-dict inputs without raising errors. The caller decides whether `None` should become `{}` via `or {}`.

### `_deep_merge(target, source)`

Recursively merges `source` into `target` in place.

| Parameter | Type | Description |
|-----------|------|-------------|
| `target` | `dict` | The dictionary to merge into (modified in place) |
| `source` | `dict` | The dictionary to merge from (values assumed already deep-copied by caller) |

**Behavior:** For each key in `source`: if the key exists in `target` and both values are `dict`, recurse. Otherwise replace `target[key]` with `source[key]`.

### `_sanitize_key(key)`

Sanitizes a dot-notation key string. Strips whitespace, collapses internal whitespace to a single space, and validates each component is non-empty and within `_KEY_COMPONENT_MAX_LENGTH` (40) characters. Raises `ValueError` on invalid input.

### `_MISSING` (module-level sentinel)

A unique `object()` instance used to distinguish "key not found" from `None` (a valid JSON null value). Returned by `_get_nested_value()` when a key is absent.

### `_get_nested_value(obj, key)`

Reads a value from a nested dict using dot-notation key traversal.

| Parameter | Type | Description |
|-----------|------|-------------|
| `obj` | `dict` | The source dictionary to read from |
| `key` | `str` | Dot-delimited key path (e.g. `"a.b.c"`) |

**Returns:** The value at the leaf key, or `_MISSING` if any intermediate key is absent, any intermediate value is not a dict, or the final key is absent.

### `_coerce_to_string(value, precision)`

Converts any JSON-storable value to a string. `_MISSING` or `None` → `""`. `bool` → `"true"` or `"false"` (lowercase string literals, checked before `int`). `int` → `str(value)`. `float`: `precision=0` = whole number (rounds then converts to int); `precision>0` = that many decimal places. `dict` → serialized with `json.dumps(indent=2, ensure_ascii=False)`. `list` → `""`.

### `_coerce_to_int(value)`

Converts any JSON-storable value to an integer. `_MISSING` or `None` → `0`. `bool` checked before `int` (subclass guard): `True` → `1`, `False` → `0`. `int` → returned as-is. `float` → `round(value)` (not truncation). Strings parsed via `int(float(value))`, fallback `0`. `dict`/`list` return `0`.

### `_coerce_to_float(value, precision)`

Converts any JSON-storable value to a float. `bool` checked before `int` (subclass guard). `precision=0` = no rounding; `precision>0` = `round(result, precision)`. `dict`/`list` return `0.0`.

### `_coerce_to_bool(value)`

Converts any JSON-storable value to a boolean. `_MISSING` or `None` → `False`. `bool` checked before `int` (subclass guard): returned as-is. `int` → `value != 0`. `float` → `round(value) != 0`. Strings `"1"`, `"true"`, `"yes"` (case-insensitive, stripped) → `True`; all other strings → `False`. `dict`/`list` return `False`.

### `_raise_getter_error(key, condition, custom_message)`

Raises `ValueError` for getter node error conditions. Uses `custom_message.strip()` if non-empty; otherwise raises with `f"JSON getter error: {condition} (key: '{key}')"` .

## Node Classes

### Summary

| Class | Node ID | Display Name | Category | Schema Flags |
|-------|---------|-------------|----------|--------------|
| `JsonStringNode` | `Mistralys_JsonString` | JSON String | `json` | — |
| `JsonIntNode` | `Mistralys_JsonInt` | JSON Int | `json` | — |
| `JsonFloatNode` | `Mistralys_JsonFloat` | JSON Float | `json` | — |
| `JsonBooleanNode` | `Mistralys_JsonBoolean` | JSON Boolean | `json` | — |
| `JsonObjectNode` | `Mistralys_JsonObject` | JSON Object | `json` | — |
| `JsonMergeObjectsNode` | `Mistralys_JsonMergeObjects` | JSON Merge Objects | `json` | — |
| `JsonGetStringNode` | `Mistralys_JsonGetString` | JSON Get String | `json` | — |
| `JsonGetIntNode` | `Mistralys_JsonGetInt` | JSON Get Int | `json` | — |
| `JsonGetFloatNode` | `Mistralys_JsonGetFloat` | JSON Get Float | `json` | — |
| `JsonGetBoolNode` | `Mistralys_JsonGetBool` | JSON Get Bool | `json` | — |
| `JsonGetObjectNode` | `Mistralys_JsonGetObject` | JSON Get Object | `json` | — |
| `JsonToStringNode` | `Mistralys_JsonToString` | JSON to String | `json` | — |
| `SaveJsonNode` | `Mistralys_SaveJson` | JSON Save File | `json` | `is_output_node=True`, `not_idempotent=True` |

### Primitive Value Nodes (WP-002)

All four nodes share the same pattern: accept an optional `JSON_OBJECT` input, add a typed key-value pair via `_set_nested_key()`, and return the modified object alongside passthrough outputs. The `key` input supports dot notation (e.g. `address.city`) to create nested structures.

#### `JsonStringNode` — `Mistralys_JsonString` / "JSON String"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `value` | `String` | Default `""` |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of input with key-value pair added |
| Output | `VALUE` | `String` | Passthrough of `value` input |
| Output | `KEY` | `String` | Passthrough of `key` input |

#### `JsonIntNode` — `Mistralys_JsonInt` / "JSON Int"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `value` | `Int` | Default `0` |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of input with key-value pair added |
| Output | `VALUE` | `Int` | Passthrough of `value` input |
| Output | `KEY` | `String` | Passthrough of `key` input |

#### `JsonFloatNode` — `Mistralys_JsonFloat` / "JSON Float"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `value` | `Float` | Default `0.0` |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of input with key-value pair added |
| Output | `VALUE` | `Float` | Passthrough of `value` input |
| Output | `KEY` | `String` | Passthrough of `key` input |

#### `JsonBooleanNode` — `Mistralys_JsonBoolean` / "JSON Boolean"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `value` | `Boolean` | Default `True` |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of input with key-value pair added |
| Output | `VALUE` | `Boolean` | Passthrough of `value` input |
| Output | `KEY` | `String` | Passthrough of `key` input |

### Output Nodes (WP-004)

#### `SaveJsonNode` — `Mistralys_SaveJson` / "JSON Save File"

Saves a JSON object to a `.json` file in ComfyUI's output directory. When `counter_length` is 0, each run overwrites the previous file.

**Schema flags:** `is_output_node=True`, `not_idempotent=True`

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory — the object to serialize and save |
| Input | `filename` | `String` | Default `"output"` — sanitized with `os.path.basename()`; empty falls back to `"output"` |
| Input | `subfolder` | `String` | Default `""` — stripped of whitespace; validated against path traversal via `os.path.realpath()` |
| Input | `counter_length` | `Int` | Default `5`, min `0`, max `10` — zero-padded counter digits; `0` disables counter (overwrite mode) |

No outputs (`outputs=[]`). Returns `io.NodeOutput()` with no arguments. This is a side-effect-only node.

**File naming:**
- Counter mode (`counter_length > 0`): `{filename}_{padded_counter}.json` using `_get_next_counter()`
- Overwrite mode (`counter_length = 0`): `{filename}.json`

**Security controls:**
- `os.path.basename()` strips directory separators from the filename unconditionally
- `os.path.realpath()` + `startswith()` validates the subfolder stays within the output directory boundary; raises `ValueError` on traversal attempt
- Subfolders created automatically with `os.makedirs(target_dir, exist_ok=True)`

**File I/O:** UTF-8 with `json.dumps(indent=2, ensure_ascii=False)` via `open(path, "w", encoding="utf-8")`

## Extension Registration (WP-005)

### `JsonNodesExtension` (class)

Subclass of `ComfyExtension` that registers all thirteen node classes with ComfyUI.

| Method | Signature | Returns |
|--------|-----------|--------|
| `get_node_list()` | `async get_node_list(self) -> list[type[io.ComfyNode]]` | List of all 13 node classes |

Decorated with `@override`. Returns `[JsonStringNode, JsonIntNode, JsonFloatNode, JsonBooleanNode, JsonObjectNode, JsonMergeObjectsNode, JsonGetStringNode, JsonGetIntNode, JsonGetFloatNode, JsonGetBoolNode, JsonGetObjectNode, JsonToStringNode, SaveJsonNode]`.

### `comfy_entrypoint()` (module-level function)

| Signature | Returns |
|-----------|---------|
| `async def comfy_entrypoint() -> JsonNodesExtension` | `JsonNodesExtension` instance |

Module-level async entry point called by ComfyUI to discover and load the extension.

### Structural Nodes (WP-003)

#### `JsonObjectNode` — `Mistralys_JsonObject` / "JSON Object"

Nests a JSON sub-object under the specified key. The `value` input is mandatory (not optional). Both the accumulating dict and the nested value are deep-copied for fork-safety.

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `value` | `JSON_OBJECT` | Mandatory — the sub-object to nest |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of input with nested sub-object added |
| Output | `VALUE` | `JSON_OBJECT` | Passthrough of the original `value` input (original reference, not copy) |
| Output | `KEY` | `String` | Passthrough of `key` input |

#### `JsonMergeObjectsNode` — `Mistralys_JsonMergeObjects` / "JSON Merge Objects"

Merges all top-level keys from up to six source objects into `json_object` using `dict.update()`. Sources are applied in order (`merge_object_1` first, `merge_object_6` last); later sources overwrite duplicate keys from earlier ones. All source objects are deep-copied for fork-safety. Passthrough outputs return the original input references (not copies). Unconnected inputs default to `None` and are skipped.

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Optional — creates a new empty dict if not connected |
| Input | `merge_object_1` | `JSON_OBJECT` | Optional — first source; applied first |
| Input | `merge_object_2` | `JSON_OBJECT` | Optional — second source; applied after `merge_object_1` |
| Input | `merge_object_3` | `JSON_OBJECT` | Optional — third source |
| Input | `merge_object_4` | `JSON_OBJECT` | Optional — fourth source |
| Input | `merge_object_5` | `JSON_OBJECT` | Optional — fifth source |
| Input | `merge_object_6` | `JSON_OBJECT` | Optional — sixth source; applied last |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Deep copy of base with all connected merge sources applied |
| Output | `MERGE_OBJECT_1` | `JSON_OBJECT` | Passthrough of `merge_object_1` (original reference) |
| Output | `MERGE_OBJECT_2` | `JSON_OBJECT` | Passthrough of `merge_object_2` (original reference) |
| Output | `MERGE_OBJECT_3` | `JSON_OBJECT` | Passthrough of `merge_object_3` (original reference) |
| Output | `MERGE_OBJECT_4` | `JSON_OBJECT` | Passthrough of `merge_object_4` (original reference) |
| Output | `MERGE_OBJECT_5` | `JSON_OBJECT` | Passthrough of `merge_object_5` (original reference) |
| Output | `MERGE_OBJECT_6` | `JSON_OBJECT` | Passthrough of `merge_object_6` (original reference) |

### Getter Nodes

All five getter nodes share the same structural pattern: mandatory `json_object` input → `_sanitize_key()` → `_coerce_json_object()` → `_get_nested_value()` → type coercion → error check → passthrough outputs. The `json_object` is passed through as the same reference (no deep-copy) because getter nodes never mutate the object.

#### `JsonGetStringNode` — `Mistralys_JsonGetString` / "JSON Get String"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Input | `error_on_missing` | `Boolean` | Default `False` |
| Input | `error_on_empty` | `Boolean` | Default `False` |
| Input | `error_message` | `String` | Default `""` — empty = use default message |
| Input | `precision` | `Int` | Default `0`, min `0`, max `10` — float decimal display |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Same-reference passthrough |
| Output | `VALUE` | `String` | Resolved string value |
| Output | `ERROR_ON_MISSING` | `Boolean` | Passthrough |
| Output | `ERROR_ON_EMPTY` | `Boolean` | Passthrough |
| Output | `ERROR_MESSAGE` | `String` | Passthrough |
| Output | `PRECISION` | `Int` | Passthrough |

#### `JsonGetIntNode` — `Mistralys_JsonGetInt` / "JSON Get Int"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Input | `error_on_missing` | `Boolean` | Default `False` |
| Input | `error_on_zero` | `Boolean` | Default `False` |
| Input | `error_message` | `String` | Default `""` — empty = use default message |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Same-reference passthrough |
| Output | `VALUE` | `Int` | Resolved integer value |
| Output | `ERROR_ON_MISSING` | `Boolean` | Passthrough |
| Output | `ERROR_ON_ZERO` | `Boolean` | Passthrough |
| Output | `ERROR_MESSAGE` | `String` | Passthrough |

#### `JsonGetFloatNode` — `Mistralys_JsonGetFloat` / "JSON Get Float"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Input | `error_on_missing` | `Boolean` | Default `False` |
| Input | `error_on_zero` | `Boolean` | Default `False` |
| Input | `error_message` | `String` | Default `""` — empty = use default message |
| Input | `precision` | `Int` | Default `0`, min `0`, max `10` — `0` = no rounding |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Same-reference passthrough |
| Output | `VALUE` | `Float` | Resolved float value |
| Output | `ERROR_ON_MISSING` | `Boolean` | Passthrough |
| Output | `ERROR_ON_ZERO` | `Boolean` | Passthrough |
| Output | `ERROR_MESSAGE` | `String` | Passthrough |
| Output | `PRECISION` | `Int` | Passthrough |

#### `JsonGetBoolNode` — `Mistralys_JsonGetBool` / "JSON Get Bool"

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Input | `error_on_missing` | `Boolean` | Default `False` |
| Input | `error_message` | `String` | Default `""` — empty = use default message |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Same-reference passthrough |
| Output | `VALUE` | `Boolean` | Resolved boolean value |
| Output | `ERROR_ON_MISSING` | `Boolean` | Passthrough |
| Output | `ERROR_MESSAGE` | `String` | Passthrough |

#### `JsonGetObjectNode` — `Mistralys_JsonGetObject` / "JSON Get Object"

Extracted sub-objects are **deep-copied** for fork-safety (unlike the JSON_OBJECT passthrough, which is the same reference).

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory |
| Input | `key` | `String` | Default `"key"` — supports dot notation |
| Input | `error_on_missing` | `Boolean` | Default `False` |
| Input | `error_on_empty` | `Boolean` | Default `False` |
| Input | `error_message` | `String` | Default `""` — empty = use default message |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Same-reference passthrough |
| Output | `VALUE` | `JSON_OBJECT` | Deep copy of extracted sub-object; `{}` if absent or non-dict |
| Output | `ERROR_ON_MISSING` | `Boolean` | Passthrough |
| Output | `ERROR_ON_EMPTY` | `Boolean` | Passthrough |
| Output | `ERROR_MESSAGE` | `String` | Passthrough |

#### `JsonToStringNode` — `Mistralys_JsonToString` / "JSON to String"

Serializes a JSON object to its string representation using `json.dumps(indent=2, ensure_ascii=False)`. Read-only — does not modify the object.

| I/O | Name | Type | Notes |
|-----|------|------|-------|
| Input | `json_object` | `JSON_OBJECT` | Mandatory — the object to serialize |
| Output | `JSON_OBJECT` | `JSON_OBJECT` | Passthrough of `json_object` (same reference, no copy) |
| Output | `STRING` | `String` | Pretty-printed JSON string, indented 2 spaces, Unicode preserved |