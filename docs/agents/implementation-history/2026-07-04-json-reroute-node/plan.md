# Plan

## Plan Audit Cycles
- Audits: none — Plan Auditor v1.5.0
- Architectural Reviews: none — Plan Architect Reviewer v1.6.0

## Prior Project Context
Three prior projects have been completed in this repository: the original 7-node suite (2026-07-02), the LoadJsonNode (2026-07-03), and a LoadJsonNode rework (2026-07-03). The codebase now contains 14 V3 nodes. All projects followed the same patterns: V3 API only, `io.Custom("JSON_OBJECT")` inline type, deep copy on input for fork-safety, and `_coerce_json_object()` to guard against non-dict values from Reroute nodes. The existing `_coerce_json_object()` helper was in fact designed anticipating exactly this kind of passthrough node.

## Summary
Add a fifteenth node — "JSON Reroute" — that acts as a typed passthrough for `JSON_OBJECT` connections. It accepts an optional JSON object input and outputs either the same object (passed through) or a new empty object `{}` if no input is connected. This is the simplest node in the set: no key, no value manipulation, no side effects.

## Architectural Context
- All node classes live in `nodes.py` and extend `io.ComfyNode`.
- Each node defines `define_schema()` (returning `io.Schema`) and `execute()` (returning `io.NodeOutput`).
- The custom type `JsonObject = io.Custom("JSON_OBJECT")` is a module-level constant used for typed inputs/outputs.
- `_coerce_json_object(value)` already handles `None` → `None`, `dict` → `dict`, anything else → `{}`.
- Registration happens in `__init__.py` via the `JsonNodesExtension.get_node_list()` list.
- The `"json"` category is used by all existing nodes.
- Node IDs follow the `Mistralys_JsonXxx` convention.

## Approach / Architecture
Add a single `JsonRerouteNode` class to `nodes.py` following the exact same pattern as every other node. The node:

1. Takes one optional `JsonObject` input.
2. Outputs one `JsonObject` — the input deep-copied if provided, or `{}` if not.
3. Uses `_coerce_json_object()` + `copy.deepcopy()` for fork-safety, matching the established pattern.

Register the node in `__init__.py` alongside the existing 14 nodes.

## Rationale
- The node is useful as a typed junction point in workflows: it lets users split or reroute `JSON_OBJECT` connections without needing a setter node (which would require a key/value).
- Creating an empty `{}` when no input is connected matches the existing pattern where all setter nodes auto-create an empty object if no input is wired.
- Deep copy on the input is mandatory for fork-safety (a core design decision documented in `AGENTS.md`).

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|----------|--------------|-------------------------|-------------------|
| Deep copy behavior | Always deep-copy input | Pass by reference (no copy) | Deep copy is the established convention for fork-safety; skipping it would be the only node that violates this rule. |
| Empty object on no input | Return `{}` | Return `None` / raise error | Returning `{}` matches how all setter nodes behave when no input is connected — consistent UX. |
| Placement in code | After `JsonMergeObjectsNode`, before getter nodes | At end of file | Logical grouping: reroute is a structural/utility node, not a getter or I/O node. |

## Pattern Alignment
- **Node class structure** (`nodes.py`): Follows the exact `define_schema()` / `execute()` classmethod pattern used by all 14 existing nodes.
- **Input coercion** (`nodes.py`, `_coerce_json_object()`): Reuses the existing guard helper.
- **Deep copy on input** (`nodes.py`): Matches every setter/structural node.
- **Registration** (`__init__.py`): Added to the `get_node_list()` return list.
- **Node ID convention**: `Mistralys_JsonReroute` follows the `Mistralys_Json*` pattern.
- **Category**: `"json"` — same as all existing nodes.

No departures from existing patterns.

## Detailed Steps

1. **Add `JsonRerouteNode` class to `nodes.py`.**
   - Place it after `JsonMergeObjectsNode` (line ~554) and before the getter node section (line ~556).
   - Schema: `node_id="Mistralys_JsonReroute"`, `display_name="JSON Reroute"`, `category="json"`.
   - One optional `JsonObject` input (`json_object`).
   - One `JsonObject` output (`JSON_OBJECT`).
   - `execute()`: deep-copy the coerced input or return `{}`.

2. **Register `JsonRerouteNode` in `__init__.py`.**
   - Add import to the import list.
   - Add to the `get_node_list()` return list, after `JsonMergeObjectsNode`.

3. **Update project documentation.**
   - Add the node to `docs/agents/projects/json-node-project.md`.
   - Update node count references in `AGENTS.md`.
   - Update `docs/agents/project-manifest/api-surface.md` if node classes are listed there.
   - Update `docs/agents/project-manifest/file-tree.md` (no new files, but node count changes).
   - Update `README.md` with the new node description.

## Dependencies
- None. The node uses only existing infrastructure (`JsonObject`, `_coerce_json_object`, `copy.deepcopy`).

## Required Components
- `nodes.py` — new `JsonRerouteNode` class (modify existing file)
- `__init__.py` — registration (modify existing file)

## Assumptions
- The V3 API `io.Schema` supports nodes with a single optional input and single output (confirmed by existing patterns).
- `_coerce_json_object()` continues to handle `None` and non-dict values correctly (verified in source).

## Constraints
- V3 API only — no V1 fallback.
- No external dependencies.
- Must deep-copy input for fork-safety.
- Node count increases from 14 to 15.

## Out of Scope
- Adding any additional inputs (keys, values, configuration).
- Multiple outputs or passthrough variants.
- Any caching/fingerprinting logic (not needed for a pure passthrough).
- Test files (the node is trivially simple — single-line logic using existing helpers).

## Acceptance Criteria
- `JsonRerouteNode` exists in `nodes.py` with correct schema and execute method.
- Node is registered in `__init__.py` and appears in ComfyUI's node menu under the `json` category.
- When an input JSON object is connected, the output is a deep copy of that object.
- When no input is connected, the output is an empty `{}`.
- Non-dict inputs are coerced to `{}` via `_coerce_json_object()`.
- All existing nodes continue to function (no regressions).
- Documentation (`json-node-project.md`, `AGENTS.md`, `README.md`) reflects the new node and updated node count.

## Testing Strategy
The node is trivially simple (one line of logic using established helpers that are already tested). Manual testing in ComfyUI is sufficient:
- Place the node with no input connected → confirm output is `{}`.
- Connect a JSON object from a setter node → confirm output matches input.
- Chain two reroute nodes → confirm passthrough works through multiple hops.

## Test Plan
- Manual test: JSON Reroute with no input → outputs `{}` — covers AC "empty object on no input"
- Manual test: JSON Reroute with connected input → outputs deep copy — covers AC "passthrough"
- Manual test: Verify existing nodes still work — covers AC "no regressions"

## Documentation Updates
- `docs/agents/projects/json-node-project.md` — Add "JSON Reroute" node specification to the node list
- `AGENTS.md` — Update node count from "Fourteen" / "fourteen" / "14" to "Fifteen" / "fifteen" / "15" in Project Stats and Architecture line
- `docs/agents/project-manifest/file-tree.md` — No new files, but verify node count if mentioned
- `README.md` — Add JSON Reroute to the node list and usage documentation

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| **Node ID collision** | `Mistralys_JsonReroute` is unique — verified no existing node uses this ID via grep. |
| **Fork-safety violation** | Uses `copy.deepcopy()` on the input, matching all other nodes. |
