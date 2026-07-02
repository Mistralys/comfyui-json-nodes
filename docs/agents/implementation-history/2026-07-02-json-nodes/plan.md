# Plan

## Plan Audit Cycles
- Audits: 1 — Plan Auditor v1.5.0
- Architectural Reviews: 1 — Plan Architect Reviewer v1.6.0

## Summary

Implement a set of seven ComfyUI V3 custom nodes that allow users to incrementally build JSON objects within a workflow, serialize them to string, and save them to disk. The nodes use a custom `JSON_OBJECT` type that flows between nodes additively — each node in the chain adds a key-value pair to the accumulating dictionary. Key names support dot notation for automatic nesting (e.g., `address.city` creates `{"address": {"city": ...}}`). A Save JSON output node writes the final object to ComfyUI's output directory using the same counter and path-traversal protections established in the existing Save Text Node project.

## Architectural Context

The project is scaffolded as a ComfyUI V3 custom node package:

- **`nodes.py`** — currently empty (imports only). Will contain all node classes and helper functions.
- **`__init__.py`** — currently a skeleton `ComfyExtension` shell. Will register all nodes.
- **`pyproject.toml`** — already configured with package metadata (`comfyui-json-nodes`, publisher `Mistralys`).
- **V3 API patterns** — documented in the companion workspace `comfyui-custom-node-skills/plugins/comfyui-custom-nodes/skills/`. Key patterns: `io.ComfyNode` subclass, `io.Schema` definition, `io.NodeOutput` returns, `io.Custom()` for custom types, `ComfyExtension` registration.
- **Existing imports in `nodes.py`**: `os`, `re`, `folder_paths`, `io`, `ui` from `comfy_api.latest`.

The AGENTS.md and README currently reference the old "Save Text Node" project from which this repository was scaffolded. These will be updated as part of the documentation steps.

## Approach / Architecture

### Custom Type

Define `JsonObject = io.Custom("JSON_OBJECT")` at module level in `nodes.py`. This creates a typed connection slot that only accepts/produces JSON object dicts, preventing accidental connections to incompatible nodes.

### Node Family

Seven node classes, all in `nodes.py`:

| Node Class | Display Name | Purpose | Key Properties |
|---|---|---|---|
| `JsonStringNode` | JSON String | Add string key | — |
| `JsonIntNode` | JSON Int | Add integer key | — |
| `JsonFloatNode` | JSON Float | Add float key | — |
| `JsonBooleanNode` | JSON Boolean | Add boolean key | — |
| `JsonObjectNode` | JSON Object | Nest a sub-object under a key | Deep-copies value |
| `JsonToStringNode` | JSON to String | Serialize to JSON string | — |
| `SaveJsonNode` | Save JSON | Write JSON to `.json` file | `is_output_node=True`, `not_idempotent=True` |

### Shared Pattern (Value Nodes)

The five value nodes (String, Int, Float, Boolean, Object) follow an identical pattern:

```
Inputs:
  json_object  — JsonObject, optional (creates new dict if absent)
  value        — typed (String/Int/Float/Boolean/JsonObject)
  key          — String, default "key"

Outputs:
  JSON_OBJECT  — the accumulated dict
  VALUE        — passthrough of input value
  KEY          — passthrough of key name

Execute:
  1. Deep-copy incoming json_object (or create empty dict)
  2. Set key in dict using dot-notation helper
  3. Return (dict, value, key)
```

### Helper Functions

Two module-level helper functions in `nodes.py`:

1. **`_set_nested_key(obj, key, value)`** — Splits the key on `.` and traverses/creates intermediate dicts. Used by all value nodes.
2. **`_get_next_counter(directory, filename, extension, counter_length)`** — Scans the target directory for existing `{filename}_{counter}.{extension}` files and returns the next counter value. Used by Save JSON.

### Registration

`__init__.py` imports all seven node classes from `nodes.py` and returns them from `ComfyExtension.get_node_list()`.

## Rationale

- **`io.Custom()` inline type** — chosen over the `@comfytype` decorator because the JSON object is a plain Python `dict` with no special methods or type hints needed. `io.Custom("JSON_OBJECT")` is the minimal approach for this use case (reference: `skill_test_nodes/nodes_datatypes.py` `SkillTest_CustomType`).
- **Deep copy on input** — prevents mutation of upstream node outputs when the same dict flows to multiple downstream nodes (fork scenario in the graph). Uses `copy.deepcopy()` for correctness with arbitrarily nested structures.
- **Module-level helpers instead of a base class** — the five value nodes share logic but differ only in their input/output type declarations. A base class would add inheritance complexity without reducing code; a shared helper function is simpler and more transparent.
- **Dot notation in key name** — allows users to build nested structures without the JSON Object node, reducing graph complexity for common cases. Implementation is a simple `str.split(".")` traversal.
- **Counter via folder scan** — matches ComfyUI's `ImageSaveHelper` pattern for maximum reliability. The regex-based scan is proven in the existing ComfyUI ecosystem.
- **Pretty-printed JSON output** — `json.dumps(obj, indent=2, ensure_ascii=False)` produces readable output for both the JSON to String node and Save JSON. `ensure_ascii=False` preserves Unicode characters without escaping.

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|----------|--------------|-------------------------|-------------------|
| Custom type definition | `io.Custom("JSON_OBJECT")` inline | `@comfytype` decorator class | Inline is simpler for a type that wraps a plain dict; decorator adds boilerplate with no benefit here. |
| Value node code reuse | Shared helper function `_set_nested_key()` | Abstract base class with type-parameterized `execute()` | Helper function is more transparent; base class adds inheritance overhead for identical 5-line execute methods. |
| Dot-notation nesting | Built-in to all value nodes | Separate "JSON Set Nested" node | Building it into the key input eliminates an extra node while keeping simple keys as the default path. |
| JSON serialization format | `json.dumps(indent=2, ensure_ascii=False)` | Minified JSON / configurable formatting | Readable output is more useful for metadata inspection; adding a formatting option is over-engineering for v1. |
| Counter implementation | Folder-scan regex (same as ImageSaveHelper) | Atomic counter file / database | Folder scan is proven in ComfyUI ecosystem and requires no state files. |

## Pattern Alignment

- **V3 Node class structure** (`io.ComfyNode` + `define_schema()` + `execute()` classmethods) — follows `skill_test_nodes/nodes_basics.py` exactly.
- **Custom type via `io.Custom()`** — follows `skill_test_nodes/nodes_datatypes.py` `SkillTest_CustomType` pattern.
- **Extension registration** (`ComfyExtension` + `comfy_entrypoint()`) — follows `skill_test_nodes/__init__.py` pattern.
- **Output node pattern** (`is_output_node=True`, `not_idempotent=True`) — follows `skill_test_nodes/nodes_outputs.py` save patterns.
- **Counter + path traversal protection** — follows the ImageSaveHelper convention documented in the node-outputs skill.
- **Category naming** — uses `json` as the category, following ComfyUI's flat category convention for small node sets.

## Detailed Steps

### Step 1: Add Custom Type and Imports

In `nodes.py`, add the required imports and define the custom type:

```python
import os
import re
import json
import copy
import folder_paths
from comfy_api.latest import io, ui

JsonObject = io.Custom("JSON_OBJECT")
```

### Step 2: Implement Helper Functions

Add two module-level helper functions in `nodes.py`:

**`_set_nested_key(obj, key, value)`** — sets a value in a nested dict using dot notation:
- Split `key` on `"."`.
- Traverse the parts, creating intermediate dicts as needed.
- Set the final part to `value`.
- If an intermediate key exists but is not a dict, overwrite it with a new dict.

**`_get_next_counter(directory, filename, extension, counter_length)`** — determines the next file counter:
- Build regex pattern: `^{re.escape(filename)}_{counter_pattern}\.{re.escape(extension)}$` where `counter_pattern` is `\d{counter_length}` (or `\d+` if flexible matching is desired).
- Scan `directory` for matching files using `os.listdir()`.
- Extract counter values, find the maximum, return `max + 1` (or `1` if no matches).
- Use `\d+` for flexible digit matching to handle counter length changes gracefully.

### Step 3: Implement JsonStringNode

```python
class JsonStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonString",
            display_name="JSON String",
            category="json",
            description="Add a string key to a JSON object.",
            inputs=[
                JsonObject.Input("json_object", optional=True),
                io.String.Input("value"),
                io.String.Input("key", default="key"),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT"),
                io.String.Output("VALUE"),
                io.String.Output("KEY"),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        obj = copy.deepcopy(json_object) if json_object is not None else {}
        _set_nested_key(obj, key, value)
        return io.NodeOutput(obj, value, key)
```

### Step 4: Implement JsonIntNode

Same pattern as Step 3 but with:
- `node_id="Mistralys_JsonInt"`, `display_name="JSON Int"`
- Input: `io.Int.Input("value", default=0)`
- Output: `io.Int.Output("VALUE")`

### Step 5: Implement JsonFloatNode

Same pattern as Step 3 but with:
- `node_id="Mistralys_JsonFloat"`, `display_name="JSON Float"`
- Input: `io.Float.Input("value", default=0.0)`
- Output: `io.Float.Output("VALUE")`

### Step 6: Implement JsonBooleanNode

Same pattern as Step 3 but with:
- `node_id="Mistralys_JsonBoolean"`, `display_name="JSON Boolean"`
- Input: `io.Boolean.Input("value", default=True)`
- Output: `io.Boolean.Output("VALUE")`

### Step 7: Implement JsonObjectNode

Similar to Step 3 but:
- `node_id="Mistralys_JsonObject"`, `display_name="JSON Object"`
- `description="Nest the values of a JSON object into the specified key."`
- Value input: `JsonObject.Input("value")` — **mandatory** (not optional).
- Value output: `JsonObject.Output("VALUE")` — passthrough of the nested object.
- In `execute()`, the value is deep-copied before insertion: `_set_nested_key(obj, key, copy.deepcopy(value))`.

### Step 8: Implement JsonToStringNode

```python
class JsonToStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonToString",
            display_name="JSON to String",
            category="json",
            description="Converts a JSON object to its string representation.",
            inputs=[
                JsonObject.Input("json_object"),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT"),
                io.String.Output("STRING"),
            ],
        )

    @classmethod
    def execute(cls, json_object):
        serialized = json.dumps(json_object, indent=2, ensure_ascii=False)
        return io.NodeOutput(json_object, serialized)
```

### Step 9: Implement SaveJsonNode

```python
class SaveJsonNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_SaveJson",
            display_name="Save JSON",
            category="json",
            description="Saves a JSON object to a .json file in the output directory. When counter_length is 0, each run overwrites the previous file.",
            is_output_node=True,
            not_idempotent=True,
            inputs=[
                JsonObject.Input("json_object"),
                io.String.Input("filename", default="output"),
                io.String.Input("subfolder", default=""),
                io.Int.Input("counter_length", default=5, min=0, max=10),
            ],
            outputs=[],
        )

    @classmethod
    def execute(cls, json_object, filename, subfolder, counter_length):
        # 1. Sanitize filename
        filename = os.path.basename(filename)
        if not filename:
            filename = "output"

        # 2. Resolve and validate output directory
        output_dir = folder_paths.get_output_directory()
        subfolder = subfolder.strip()
        if subfolder:
            target_dir = os.path.join(output_dir, subfolder)
            real_target = os.path.realpath(target_dir)
            real_output = os.path.realpath(output_dir)
            if not real_target.startswith(real_output + os.sep) and real_target != real_output:
                raise ValueError(
                    f"Subfolder resolves outside the output directory: {subfolder}"
                )
        else:
            target_dir = output_dir

        # 3. Create subfolder if needed
        os.makedirs(target_dir, exist_ok=True)

        # 4. Build filename with counter
        extension = "json"
        if counter_length > 0:
            counter = _get_next_counter(target_dir, filename, extension, counter_length)
            padded = str(counter).zfill(counter_length)
            full_filename = f"{filename}_{padded}.{extension}"
        else:
            full_filename = f"{filename}.{extension}"

        # 5. Write file
        file_path = os.path.join(target_dir, full_filename)
        content = json.dumps(json_object, indent=2, ensure_ascii=False)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return io.NodeOutput()
```

### Step 10: Update `__init__.py`

Update the extension registration to import and list all seven node classes:

```python
"""Extension registration for ComfyUI JSON Nodes."""

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

from .nodes import (
    JsonStringNode,
    JsonIntNode,
    JsonFloatNode,
    JsonBooleanNode,
    JsonObjectNode,
    JsonToStringNode,
    SaveJsonNode,
)


class JsonNodesExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            JsonStringNode,
            JsonIntNode,
            JsonFloatNode,
            JsonBooleanNode,
            JsonObjectNode,
            JsonToStringNode,
            SaveJsonNode,
        ]


async def comfy_entrypoint() -> JsonNodesExtension:
    return JsonNodesExtension()
```

### Step 11: Update Documentation

Update the following files to reflect the new project:

1. **`AGENTS.md`** — Update project name from "Save Text Node" to "JSON Nodes". Update project stats (single node → seven nodes). Update file layout. Update key design decisions. Update documentation table links.
2. **`README.md`** — Rewrite to describe the JSON Nodes project: features, node list, usage examples, security notes.
3. **`docs/agents/project-manifest/api-surface.md`** — Document all seven node schemas (inputs, outputs, properties).
4. **`docs/agents/project-manifest/data-flows.md`** — Document the JSON accumulation flow, dot-notation nesting, and Save JSON file I/O.
5. **`docs/agents/project-manifest/file-tree.md`** — Document the project file structure.
6. **`docs/agents/project-manifest/tech-stack.md`** — Add `json` and `copy` to the stdlib dependencies table. Update architecture section to reflect seven nodes.
7. **`docs/agents/project-manifest/constraints.md`** — Add the "single custom type" constraint and dot-notation convention.

## Dependencies

- `json` — Python stdlib. JSON serialization.
- `copy` — Python stdlib. Deep copy of JSON objects.
- `os` — Python stdlib. Path manipulation, directory creation (already imported).
- `re` — Python stdlib. Counter filename pattern matching (already imported).
- `folder_paths` — ComfyUI built-in. Resolve output directory (already imported).
- `comfy_api.latest` — ComfyUI built-in. V3 node API (already imported).

No new external (pip) dependencies.

## Required Components

- `nodes.py` — **modified**: all seven node classes, custom type definition, two helper functions.
- `__init__.py` — **modified**: extension class with node registration.
- `AGENTS.md` — **modified**: project-wide documentation update.
- `README.md` — **modified**: full rewrite for new project.
- `docs/agents/project-manifest/api-surface.md` — **modified**: node schema documentation.
- `docs/agents/project-manifest/data-flows.md` — **modified**: flow documentation.
- `docs/agents/project-manifest/file-tree.md` — **modified**: file tree documentation.
- `docs/agents/project-manifest/tech-stack.md` — **modified**: dependency additions.
- `docs/agents/project-manifest/constraints.md` — **modified**: new conventions.

No new files created (all modifications to existing scaffolded files).

## Assumptions

- ComfyUI V3 API is available at runtime (`comfy_api.latest` is importable).
- `folder_paths.get_output_directory()` returns a valid, writable directory path.
- `io.Custom()` type creates a typed connection that only connects to matching `io.Custom()` slots (verified via `skill_test_nodes/nodes_datatypes.py` reference).
- The JSON object flowing between nodes is a plain Python `dict` — no special serialization or deserialization is needed within the graph.
- `os.listdir()` is sufficient for the counter scan (the output directory is not expected to contain millions of files).

## Constraints

- **V3 API only** — no V1 fallback or compatibility layer.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **UTF-8 encoding only** — all file writes use `encoding="utf-8"`.
- **Output directory only** — Save JSON writes to `folder_paths.get_output_directory()` and optional subfolders. No arbitrary file path support.
- **Path traversal protection** — `subfolder` is validated with `os.path.realpath()`. `filename` is sanitized with `os.path.basename()`.
- **Single custom type** — all nodes share the same `JSON_OBJECT` type for interoperability.
- **Dot notation is always active** — keys containing dots are always interpreted as nested paths. To use a literal dot in a key name, users must use the JSON Object node with a pre-built sub-object.
- **`counter_length=0` overwrites** — when `counter_length` is 0, Save JSON writes to `{filename}.json` with no uniqueness guarantee. Each run silently overwrites the previous file. This is intentional "fixed output" mode; users who need uniqueness should use the default `counter_length=5`.

## Out of Scope

- Automated test suite (manual testing in ComfyUI only, per project convention).
- JSON array support (only objects/dicts).
- JSON schema validation.
- Configurable indentation or formatting options.
- File reading / JSON import nodes.
- Key deletion or removal nodes.
- V1 API compatibility.
- Frontend JavaScript extensions or custom widgets.
- Internationalization / i18n translations.
- PreviewText UI output on nodes (can be added in a future iteration).

## Acceptance Criteria

1. All seven nodes register successfully in ComfyUI and appear under the `json` category.
2. Connecting JSON value nodes in a chain produces a correctly accumulated JSON object — each node adds its key-value pair to the result.
3. The `json_object` input is optional on value nodes — when not connected, a new empty dict is created.
4. Dot notation in key names creates nested structures (e.g., key `a.b.c` produces `{"a": {"b": {"c": value}}}`).
5. The JSON Object node deep-copies the nested object's values into the specified key.
6. JSON to String serializes the object to a readable JSON string with 2-space indentation.
7. Save JSON writes a valid `.json` file to ComfyUI's output directory.
8. Save JSON counter increments correctly by scanning existing files in the target directory.
9. Save JSON counter disabled at `counter_length=0` — file overwrites on each run.
10. Save JSON rejects subfolders that resolve outside the output directory (`ValueError`).
11. Save JSON strips directory separators from the filename input.
12. Save JSON creates subfolders automatically if they do not exist.
13. Save JSON strips whitespace from the subfolder input; whitespace-only subfolder is treated as no subfolder.
14. Value passthrough outputs return the exact input value unchanged.
15. No external (pip) dependencies are introduced.
16. Save JSON falls back to filename `"output"` when the filename input is empty or reduces to empty after `os.path.basename()` sanitization.

## Testing Strategy

Manual testing in ComfyUI (per project convention — no automated test framework). Build test workflows that exercise each node and each acceptance criterion.

## Test Plan

All tests are manual workflows executed in ComfyUI.

- **T1: Single node isolation** — connect each value node (String, Int, Float, Boolean) individually with no `json_object` input. Verify the output is a single-key dict. — AC 2, 3
- **T2: Chain accumulation** — connect String → Int → Float → Boolean in a chain. Verify the final dict contains all four keys. — AC 2
- **T3: Dot notation nesting** — use key `a.b.c` on a String node. Verify output is `{"a": {"b": {"c": "value"}}}`. — AC 4
- **T4: Dot notation merge** — chain two String nodes with keys `a.b` and `a.c`. Verify output is `{"a": {"b": "v1", "c": "v2"}}` (sibling keys preserved). — AC 4
- **T5: JSON Object nesting** — create a sub-object with two keys, then nest it under a key using the JSON Object node. Verify deep copy (modifying sub-object in a parallel branch does not affect the nested copy). — AC 5
- **T6: JSON to String** — connect a built JSON object to JSON to String. Verify the string output is valid JSON with 2-space indentation. Verify the json_object passthrough output is unchanged. — AC 6
- **T7: Save JSON with counter** — run Save JSON three times. Verify files `output_00001.json`, `output_00002.json`, `output_00003.json` are created with correct content. — AC 7, 8
- **T8: Save JSON counter disabled** — set `counter_length=0`. Run twice. Verify the file is overwritten (only one file exists). — AC 9
- **T9: Save JSON path traversal** — set subfolder to `../outside`. Verify `ValueError` is raised. — AC 10
- **T10: Save JSON filename sanitization** — set filename to `../../etc/passwd`. Verify it is reduced to `passwd` via `os.path.basename()`. — AC 11
- **T11: Save JSON subfolder creation** — set subfolder to a non-existent name. Verify the subfolder is created and the file is written inside it. — AC 12
- **T12: Save JSON whitespace subfolder** — set subfolder to `"  "`. Verify it is treated as no subfolder (file written to output root). — AC 13
- **T13: Value passthrough** — for each value node, connect the VALUE output to a downstream consumer. Verify the passthrough value matches the input. — AC 14
- **T14: Node registration** — start ComfyUI and verify all seven nodes appear in the `json` category in the node menu. — AC 1
- **T15: Save JSON empty filename fallback** — set filename to `""` (empty string). Verify the output file is named `output_00001.json` (or `output.json` when `counter_length=0`). — AC 16

## Documentation Updates

Per the documentation maintenance rules in `AGENTS.md`:

- **`AGENTS.md`** — full rewrite: project name, stats, file layout, key design decisions, documentation table links. All sections must reflect "JSON Nodes" instead of "Save Text Node".
- **`README.md`** — full rewrite: project description, feature list, node table with inputs/outputs, usage examples, security notes, quick start instructions, learn-more links.
- **`docs/agents/project-manifest/api-surface.md`** — replace placeholder with full node schema documentation for all seven nodes.
- **`docs/agents/project-manifest/data-flows.md`** — replace placeholder with JSON accumulation flow, dot-notation nesting behavior, and Save JSON file I/O flow.
- **`docs/agents/project-manifest/file-tree.md`** — replace placeholder with annotated file tree.
- **`docs/agents/project-manifest/tech-stack.md`** — add `json` and `copy` to dependencies table. Update architecture pattern table and stats to reflect seven nodes.
- **`docs/agents/project-manifest/constraints.md`** — add dot-notation convention, single custom type constraint, counter behavior, and security controls.
- **`docs/agents/projects/json-node-project.md`** — no changes needed (this is the source specification).

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **`io.Custom()` type not connectable between nodes** | Verified via `skill_test_nodes/nodes_datatypes.py` — the `SkillTest_CustomType` and `SkillTest_CustomTypeConsumer` pattern demonstrates cross-node custom type flow. |
| **Deep copy performance on large JSON objects** | Acceptable for metadata use case — JSON objects are expected to be small (tens of keys). If performance becomes an issue, shallow copy with selective deep copy can be considered. |
| **Dot notation conflicts with literal dots in keys** | Documented as a known limitation in Out of Scope. Users who need literal dots can use the JSON Object node to build sub-objects manually. |
| **Counter regex mismatch with non-standard filenames** | Counter uses `\d+` flexible matching for robustness. Edge case: files created by other tools with similar naming may affect the counter. Mitigation: this matches ComfyUI's own ImageSaveHelper behavior. |
| **Node ID collisions** | Prefixed all node IDs with `Mistralys_` (e.g., `Mistralys_JsonString`) to minimize collision risk with other custom node packages. |
| **Stale AGENTS.md/README causing confusion** | Documentation update is an explicit step in the plan (Step 11). |
