# Plan

## Plan Audit Cycles
- Audits: 1 — Plan Auditor v1.5.0
- Architectural Reviews: none — Plan Architect Reviewer v1.6.0

## Prior Project Context
The initial 7-node implementation was completed in `2026-07-02-json-nodes` with all 7 WPs complete, 23/23 pipeline stages passing, and 164/164 tests passing. The synthesis report noted that "description fields carry discoverability" and recommended treating them as first-class user-facing content (Gold Nugget #5). This plan extends that principle from node-level descriptions to per-input/output tooltips, and adds the eighth node to the family.

## Summary

Add user-friendly tooltips to every input and output across all existing nodes, and implement a new "JSON Merge Objects" node that merges all top-level keys from one JSON object into another without requiring a key name. The merge node enables building a single JSON object from multiple independently-constructed branches.

## Architectural Context

The codebase contains seven `io.ComfyNode` subclasses in [nodes.py](nodes.py), all registered via `JsonNodesExtension` in [\_\_init\_\_.py](__init__.py). Each node uses `io.Schema` with typed inputs/outputs. The V3 API supports a `tooltip` parameter on both `Input()` and `Output()` constructors — this is confirmed in the reference implementations at `skill_test_nodes/nodes_inputs.py` (line 45, 105, 175, 378) and `skill_test_nodes/nodes_outputs.py` (line 60). Tooltip support on `io.Custom()` types is assumed based on a shared base interface — the reference implementations do not demonstrate it for custom types. See Assumptions and Risks for the corresponding caveat.

The existing node family follows a consistent pattern: optional `json_object` input → mutation via `_set_nested_key()` → output (object, value passthrough, key passthrough). The new merge node follows this same pattern but replaces the key+value pair with a merge source object and uses `dict.update()` instead of `_set_nested_key()`.

## Approach / Architecture

### Part 1: Tooltips

Add the `tooltip` parameter to every `Input()` and `Output()` call across all seven existing nodes. Tooltips are brief, non-technical, and describe what the input/output does from the user's perspective. They should help users understand how to connect nodes without consulting external documentation.

### Part 2: JSON Merge Objects Node

Add a new `JsonMergeObjectsNode` class in `nodes.py` with:

| Property | Value |
|---|---|
| `node_id` | `Mistralys_JsonMergeObjects` |
| `display_name` | `JSON Merge Objects` |
| `category` | `json` |

**Inputs:**
- `json_object` — `JsonObject`, optional (target object to merge into; creates new if absent)
- `merge_object` — `JsonObject`, mandatory (source object whose keys are copied into the target)

**Outputs:**
- `JSON_OBJECT` — the merged result
- `MERGE_OBJECT` — passthrough of the merge source

**Execute logic:**
1. Deep-copy incoming `json_object` (or create empty dict) — fork-safety for the target.
2. Deep-copy `merge_object` and call `dict.update()` to merge all keys into the target — fork-safety for the source.
3. Return `(merged_object, merge_object)` — passthrough returns the original reference (not the copy).

This follows the same asymmetric deep-copy pattern established by `JsonObjectNode` (Gold Nugget #2 from the synthesis).

**Registration:** Add `JsonMergeObjectsNode` to the import list in `__init__.py` and to the `get_node_list()` return array.

## Rationale

- **Tooltips** — The synthesis report explicitly called out tooltip discoverability as a gold nugget. Adding per-input/output tooltips is the natural extension: users can hover over any connection point or widget to understand its purpose without leaving the ComfyUI canvas.
- **`dict.update()` for merge** — This is the simplest correct approach for top-level key merging. It matches Python semantics that users would expect: later values overwrite earlier ones. A deep merge would be more complex and was not requested.
- **No key input on merge node** — The entire purpose of this node is to merge without nesting. The JSON Object node already handles nesting. Having both nodes gives users the choice.
- **Passthrough of merge source** — Consistent with the value passthrough pattern in all other nodes, allowing the same merge source to be connected to multiple merge targets.

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|----------|--------------|-------------------------|-------------------|
| Merge strategy | `dict.update()` (top-level) | Deep recursive merge | Top-level merge is simpler, predictable, and matches the user request ("copies and replaces"). Deep merge adds complexity without a stated need. |
| Merge node output names | `JSON_OBJECT` + `MERGE_OBJECT` | `JSON_OBJECT` + `VALUE` | `MERGE_OBJECT` is more descriptive than `VALUE` for this context; breaks from the primitive node naming convention intentionally for clarity. |
| Tooltip style | Brief, user-facing, non-technical | Technical/developer-oriented | Users of ComfyUI are workflow builders, not API consumers. Tooltips should explain what to connect and why, not implementation details. |

## Pattern Alignment

- **V3 `tooltip` on Input/Output** — follows `skill_test_nodes/nodes_inputs.py` and `skill_test_nodes/nodes_outputs.py` patterns exactly.
- **Fork-safe deep copy** — follows the dual deep-copy pattern from `JsonObjectNode` (deep-copy both accumulator and incoming object).
- **Node class structure** — follows identical `io.ComfyNode` + `define_schema()` + `execute()` pattern as all other nodes in `nodes.py`.
- **Extension registration** — follows existing `__init__.py` import + `get_node_list()` pattern.
- **No external dependencies** — stdlib only, consistent with project constraint.

## Detailed Steps

### Step 1: Add tooltips to all inputs and outputs in existing nodes

In `nodes.py`, add the `tooltip` parameter to every `Input()` and `Output()` call across all seven existing node classes. The specific tooltip texts:

**Shared input tooltips (used across primitive value nodes + JsonObjectNode):**
- `json_object` (optional): `"Connect an existing JSON object to add to, or leave empty to start a new one."`
- `key`: `"Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures."`

**JsonStringNode:**
- Input `value`: `"The string value to store."`
- Output `JSON_OBJECT`: `"The JSON object with the new key-value pair added."`
- Output `VALUE`: `"Passthrough of the input value, for connecting to other nodes."`
- Output `KEY`: `"Passthrough of the key name."`

**JsonIntNode:**
- Input `value`: `"The integer value to store."`
- Output `JSON_OBJECT`: `"The JSON object with the new key-value pair added."`
- Output `VALUE`: `"Passthrough of the input value, for connecting to other nodes."`
- Output `KEY`: `"Passthrough of the key name."`

**JsonFloatNode:**
- Input `value`: `"The float value to store."`
- Output `JSON_OBJECT`: `"The JSON object with the new key-value pair added."`
- Output `VALUE`: `"Passthrough of the input value, for connecting to other nodes."`
- Output `KEY`: `"Passthrough of the key name."`

**JsonBooleanNode:**
- Input `value`: `"The boolean value to store."`
- Output `JSON_OBJECT`: `"The JSON object with the new key-value pair added."`
- Output `VALUE`: `"Passthrough of the input value, for connecting to other nodes."`
- Output `KEY`: `"Passthrough of the key name."`

**JsonObjectNode:**
- Input `value`: `"The JSON sub-object to nest under the specified key."`
- Output `JSON_OBJECT`: `"The JSON object with the nested sub-object added."`
- Output `VALUE`: `"Passthrough of the input sub-object, for connecting to other nodes."`
- Output `KEY`: `"Passthrough of the key name."`

**JsonToStringNode:**
- Input `json_object`: `"The JSON object to convert to a string."`
- Output `JSON_OBJECT`: `"Passthrough of the input JSON object, for connecting to other nodes."`
- Output `STRING`: `"The JSON data as a formatted, readable string."`

**SaveJsonNode:**
- Input `json_object`: `"The JSON object to save to a file."`
- Input `filename`: `"Base filename without the .json extension."`
- Input `subfolder`: `"Subdirectory inside the output folder. Created automatically if needed."`
- Input `counter_length`: `"Number of digits for the auto-incrementing file counter (e.g. 5 produces _00001). Set to 0 to overwrite the file each run."`

### Step 2: Add JsonMergeObjectsNode class

In `nodes.py`, add a new `JsonMergeObjectsNode` class after `JsonObjectNode` (before `JsonToStringNode`). The class follows the same pattern as the other nodes:

```python
class JsonMergeObjectsNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonMergeObjects",
            display_name="JSON Merge Objects",
            category="json",
            description="Merge all keys from one JSON object into another. Use this to combine multiple separately-built JSON objects into one. Duplicate keys are overwritten by the merge source.",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to merge into, or leave empty to start a new one.",
                ),
                JsonObject.Input("merge_object",
                    tooltip="The JSON object whose keys will be copied into the target. Overwrites any duplicate keys.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The combined JSON object after merging.",
                ),
                JsonObject.Output("MERGE_OBJECT",
                    tooltip="Passthrough of the merge source object, for connecting to other nodes.",
                ),
            ],
        )

    @classmethod
    def execute(cls, merge_object, json_object=None):
        obj = copy.deepcopy(json_object) if json_object is not None else {}
        obj.update(copy.deepcopy(merge_object))
        return io.NodeOutput(obj, merge_object)
```

### Step 3: Register the new node

In `__init__.py`, add `JsonMergeObjectsNode` to the import statement and to the `get_node_list()` return array, placed after `JsonObjectNode`.

### Step 4: Update documentation

Update all documentation artifacts that are affected by the new node and the tooltip additions.

## Dependencies

- Step 2 depends on Step 1 being in progress (same file, avoid merge conflicts).
- Step 3 depends on Step 2 (class must exist before registration).
- Step 4 depends on Steps 1–3 (all code changes must be finalized).

## Required Components

- `nodes.py` — tooltip additions to all 7 existing node classes + new `JsonMergeObjectsNode` class (modified)
- `__init__.py` — import and register `JsonMergeObjectsNode` (modified)
- `README.md` — add JSON Merge Objects documentation, note tooltip availability (modified)
- `docs/agents/projects/json-node-project.md` — add JSON Merge Objects specification (modified)
- `docs/agents/project-manifest/api-surface.md` — add JSON Merge Objects API entry (modified)
- `docs/agents/project-manifest/data-flows.md` — add merge data flow (modified)
- `AGENTS.md` — update node count from 7 to 8, update file layout notes (modified)

## Assumptions

- The `tooltip` parameter is supported on `io.Custom().Input()` and `io.Custom().Output()` in the version of ComfyUI V3 API being targeted.
- `dict.update()` is the intended merge behavior (top-level key overwrite, not recursive deep merge).
- The merge node does not need a `key` parameter — that is the explicit design distinction from `JsonObjectNode`.

## Constraints

- No external dependencies — stdlib and ComfyUI builtins only.
- V3 API only — no V1 fallback.
- Deep copy on input for fork-safety — both `json_object` and `merge_object` must be deep-copied.
- UTF-8 encoding only.

## Out of Scope

- Deep/recursive merge strategy (only top-level keys are merged).
- Merge conflict reporting or detection.
- Array merge strategies.
- Tooltip localization (English only for v1).
- Any changes to the existing node behavior or logic.

## Acceptance Criteria

- Every input and output on all existing nodes displays a tooltip on hover in the ComfyUI UI.
- Tooltips are brief, user-friendly, and accurately describe the input/output purpose.
- The JSON Merge Objects node appears in the **json** category in ComfyUI.
- The JSON Merge Objects node correctly merges all top-level keys from the merge source into the target object.
- Duplicate keys in the merge source overwrite the target's keys.
- The merge source is passed through as a second output for downstream use.
- Fork-safety is maintained: deep-copy on both inputs.
- If no `json_object` is connected, the node starts with an empty dict.
- The node is registered and loads without errors.
- All documentation is updated to reflect the new node and the total count of 8 nodes.

## Testing Strategy

Testing is manual within ComfyUI, consistent with the project's established approach (no automated test framework). The test plan covers both tooltip verification (visual inspection) and merge node functional testing.

## Test Plan

- **Tooltip visual inspection** — Hover over every input and output on all 8 nodes in the ComfyUI UI and verify tooltips appear with correct text — covers all tooltip acceptance criteria.
- **Merge node: basic merge** — Connect two primitive node chains into a JSON Merge Objects node and verify all keys appear in the output — covers basic merge functionality.
- **Merge node: empty target** — Connect only a merge_object (no json_object connected) and verify the output equals the merge source — covers empty dict creation.
- **Merge node: key overwrite** — Set the same key in both the target and merge source, verify the merge source's value wins — covers duplicate key overwrite behavior.
- **Merge node: passthrough** — Connect the MERGE_OBJECT output to a JSON to String node and verify it contains only the merge source's keys — covers passthrough correctness.
- **Merge node: fork-safety** — Connect the same JSON object to two different merge nodes with different merge sources, verify each output is independent — covers deep-copy fork-safety.
- **Merge node: chain** — Chain multiple merge nodes to combine 3+ objects into one — covers multi-merge workflow.
- **Node registration** — Restart ComfyUI and verify the JSON Merge Objects node appears in the json category — covers registration.

## Documentation Updates

Per the documentation maintenance rules in `AGENTS.md`:

- [README.md](README.md) — Add JSON Merge Objects to the Structural Nodes section; update the intro to say "eight nodes"; add a usage example showing merge.
- [docs/agents/projects/json-node-project.md](docs/agents/projects/json-node-project.md) — Add "JSON Merge Objects" node specification with inputs, outputs, and behavior description.
- [docs/agents/project-manifest/api-surface.md](docs/agents/project-manifest/api-surface.md) — Add `Mistralys_JsonMergeObjects` entry with inputs/outputs.
- [docs/agents/project-manifest/data-flows.md](docs/agents/project-manifest/data-flows.md) — Add merge data flow pattern.
- [AGENTS.md](AGENTS.md) — Update "Seven ComfyUI V3 custom nodes" to "Eight" in section 5 (Project Stats), and architecture description; update section 4 (Failure Protocol) row "Tempted to add features beyond spec" from "seven nodes, no extras" to "eight nodes, no extras"; update section 7 key decisions if needed.
- [docs/agents/project-manifest/tech-stack.md](docs/agents/project-manifest/tech-stack.md) — Update the Architecture section row from "Seven custom nodes" to "Eight custom nodes".
- [docs/agents/project-manifest/file-tree.md](docs/agents/project-manifest/file-tree.md) — Update the `nodes.py` inline comment from "All 7 node classes" to "All 8 node classes".

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **`tooltip` not supported on `io.Custom()` types** | The V3 API documentation and reference implementations show `tooltip` is a common parameter on all input/output types. If the Custom type wrapper does not forward it, the tooltip will silently be ignored — no runtime error, just missing tooltip. Verify in ComfyUI after implementation. |
| **User expects deep merge instead of shallow** | The node description and tooltip explicitly state "Duplicate keys are overwritten by the merge source." The out-of-scope section documents that deep merge is not included. A deep merge node could be added in the future if requested. |
| **Merge of non-dict objects** | The `json_object` and `merge_object` inputs are typed as `JSON_OBJECT`, which constrains connections to only dict-producing nodes. Non-dict values cannot be connected in the UI. |
