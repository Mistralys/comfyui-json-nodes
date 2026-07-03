# Key Data Flows

## Extension Loading

1. ComfyUI calls `comfy_entrypoint()` in `__init__.py`
2. Returns a `JsonNodesExtension` instance
3. ComfyUI calls `get_node_list()` → receives all node classes
4. Each node's `define_schema()` is called to register inputs/outputs/metadata

## JSON Object Construction (Primitive & Structural Nodes)

1. User connects nodes in a chain; each node receives an optional `JSON_OBJECT` input
2. If no input connected, node creates a new empty `dict`
3. Input dict is deep-copied (`copy.deepcopy`) for fork-safety
4. `_set_nested_key()` sets the value at the dot-notation key path, creating intermediate dicts as needed
5. Node returns: modified `JSON_OBJECT` + passthrough `VALUE` + passthrough `KEY`

## Dot-Notation Key Expansion

Keys containing dots are split on `"."` and traversed as a nested path. Intermediate dicts are created automatically; non-dict intermediates are overwritten.

**Example:** `key="model.lora.name"`, `value="detail_tweaker"`

```
Input:  {}
Step 1: parts = ["model", "lora", "name"]
Step 2: create obj["model"] = {}
Step 3: create obj["model"]["lora"] = {}
Step 4: set obj["model"]["lora"]["name"] = "detail_tweaker"
Output: {"model": {"lora": {"name": "detail_tweaker"}}}
```

A key without dots (e.g. `"steps"`) sets a single top-level key as normal.

## JSON Object Merge (JsonMergeObjectsNode)

1. User optionally connects an accumulating object to `json_object` and up to six source objects to `merge_object_1` through `merge_object_6` (all inputs optional)
2. If `json_object` is not connected, node creates a new empty `dict`
3. `json_object` is deep-copied (`copy.deepcopy`) for fork-safety — the original upstream object is not modified
4. Each connected source (`merge_object_1` first, `merge_object_6` last) is deep-copied and applied via `dict.update()` — all top-level keys from the source overwrite any duplicate keys accumulated so far; unconnected inputs (`None`) are skipped
5. Node returns: merged `JSON_OBJECT` + passthrough outputs `MERGE_OBJECT_1`…`MERGE_OBJECT_6` (original references, not copies)

**Merge semantics:** `dict.update()` is a top-level key merge. Nested dicts inside either object are not recursively merged — the entire nested value is replaced if the key conflicts. Later sources overwrite earlier ones on key collision.

## JSON Serialization (JsonToStringNode)

1. Receives mandatory `JSON_OBJECT` input
2. Serializes via `json.dumps(indent=2, ensure_ascii=False)`
3. Returns: passthrough `JSON_OBJECT` (same reference) + `STRING` output

## JSON Value Retrieval (Getter Nodes)

1. User connects a `JSON_OBJECT` to `json_object` (mandatory)
2. `_sanitize_key()` validates the dot-notation key path
3. `_coerce_json_object()` guards against unexpected non-dict inputs
4. `_get_nested_value()` traverses the dict using the dot-split key path; returns `_MISSING` if any part of the path is absent or non-dict
5. Type coercion (`_coerce_to_string/int/float/bool()`) converts the raw value to the target type using the tacit conversion matrix
6. Error conditions are checked in order:
   - `error_on_missing`: checked immediately when `_get_nested_value()` returns `_MISSING`
   - `error_on_empty` / `error_on_zero`: checked after coercion on the resolved value
7. If an error condition is triggered: `_raise_getter_error()` raises `ValueError` with either the custom `error_message` or a default message including the key path
8. Node returns: same-reference `json_object` passthrough + coerced `VALUE` + all control input passthroughs

**`JsonGetObjectNode` special case:** The extracted `VALUE` is deep-copied for fork-safety. Non-dict values (including `_MISSING`, `None`, lists) produce `{}`.

**Chaining pattern:** Because `json_object` is passed through as the same reference and all control inputs are passed through as outputs, getter nodes can be daisy-chained: `JSON Object → Get String → Get Int → Get Float` reads multiple values from the same object.

## JSON File Output (SaveJsonNode)

1. Receives mandatory `JSON_OBJECT` input + filename/subfolder/counter_length params
2. Sanitizes filename via `os.path.basename()` (strips directory separators)
3. Resolves output directory via `folder_paths.get_output_directory()`
4. Validates subfolder against path traversal (`os.path.realpath()` + `startswith()`)
5. Creates target directory if needed (`os.makedirs(exist_ok=True)`)
6. If `counter_length > 0`: scans directory via `_get_next_counter()` → `{filename}_{padded}.json`
7. If `counter_length == 0`: uses `{filename}.json` (overwrite mode)
8. Writes JSON via `open(path, "w", encoding="utf-8")` with `json.dumps(indent=2, ensure_ascii=False)`
9. Returns empty `io.NodeOutput()` (side-effect-only node)

## JSON File Loading (LoadJsonNode)

1. At ComfyUI startup, `_list_json_files()` scans `folder_paths.get_input_directory()` recursively via `os.walk` and returns a sorted list of relative paths to all `.json` files; this list populates the `filename` combo dropdown
2. If no `.json` files are found, the combo is populated with a single placeholder `""` entry
3. `fingerprint_inputs()` calls `_guard_input_path(filename)` — which returns `""` on any `ValueError` (including empty filename) so ComfyUI falls back to re-execution safely; on success it returns `str(os.path.getmtime(real_path))` — ComfyUI uses this to determine whether to re-execute or use cached output
4. `execute()` calls `_guard_input_path(filename)` which raises `ValueError` with a user-friendly message if `filename` is empty (the `""` placeholder — "No file selected …"), or if the resolved path escapes the input directory (`os.path.realpath()` + `startswith(real_input + os.sep)`)
5. Checks file size via `os.path.getsize()` → raises `ValueError` if the file exceeds `_MAX_JSON_FILE_SIZE` (50 MB)
6. Reads the file via `open(candidate, 'r', encoding='utf-8')` → `OSError` is wrapped and re-raised as `ValueError`
7. Parses with `json.loads()` → `JSONDecodeError` is wrapped and re-raised as `ValueError` with `"Malformed JSON in file ..."` prefix
8. Validates that the parsed value is a `dict` → raises `ValueError` with `"must contain a top-level object"` message for any other type
9. Returns `io.NodeOutput(data)` — the parsed dict as a `JSON_OBJECT`