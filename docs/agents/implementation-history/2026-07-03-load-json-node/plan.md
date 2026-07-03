# Plan: JSON Load File Node

## Plan Audit Cycles
- Audits: 1 — Plan Auditor v1.5.0
- Architectural Reviews: none — Plan Architect Reviewer v1.6.0

## Prior Project Context
The comfyui-json-nodes project completed its initial implementation (2026-07-02) with 13 nodes: 4 primitive setters, 1 object setter, 1 merge node, 5 getters, 1 serializer, and 1 save node. The codebase is stable and follows a consistent pattern. A known insight from the prior project's security audit flags that Windows reserved device names (`CON`, `NUL`, etc.) bypass `os.path.basename()` sanitization — this same risk applies to the load node and must be mitigated.

## Summary
Add a "JSON Load File" node (`LoadJsonNode`) that reads a `.json` file from ComfyUI's input directory and outputs its parsed contents as a `JSON_OBJECT`. The user selects the file from a dropdown (`io.Combo.Input`) populated by scanning the input directory for `.json` files. This is the natural counterpart to the existing `SaveJsonNode`, completing the load/save cycle and enabling workflows that consume externally-produced JSON data (e.g. configuration files, metadata templates, API responses saved to disk).

## Architectural Context

**Existing modules and patterns relevant to this change:**

- [nodes.py](nodes.py) — All 13 node classes live in a single file. Helper functions (`_coerce_json_object`, `_get_nested_value`, etc.) are defined at module level. The `SaveJsonNode` class (line 844) establishes the file I/O pattern.
- [__init__.py](__init__.py) — Extension registration via `JsonNodesExtension.get_node_list()`. All nodes are imported explicitly and listed in the return array.
- `folder_paths` (ComfyUI built-in) — `get_output_directory()` is used by `SaveJsonNode`; `get_input_directory()` is the counterpart for loading.
- `JsonObject = io.Custom("JSON_OBJECT")` — Module-level constant for the typed connection slot, shared by all nodes.
- **Naming convention** — Node IDs follow `Mistralys_{PascalName}`, display names follow `JSON {Action} {Type}`.
- **Category** — All nodes use `category="json"`.

## Approach / Architecture

Add a single new node class `LoadJsonNode` to `nodes.py` that:

1. **Presents a combo dropdown** listing all `.json` files found in ComfyUI's input directory (and subdirectories, matching the subfolder format used by `SaveJsonNode`).
2. **Reads the selected file** from disk and parses it with `json.loads()`.
3. **Validates** the parsed content is a JSON object (dict), not an array or scalar.
4. **Outputs** the parsed dict as a `JSON_OBJECT` for downstream consumption by getter nodes, merge nodes, or `SaveJsonNode`.
5. **Uses `fingerprint_inputs`** based on the file's modification time (`os.path.getmtime()`) so the node re-executes automatically when the file changes on disk, but uses cached output when the file is unchanged.

### File Listing Strategy

The combo dropdown will be populated by scanning `folder_paths.get_input_directory()` for files ending in `.json` (case-insensitive). Files in subdirectories will be listed with their relative path (e.g. `subfolder/config.json`), matching the `subfolder/filename` pattern that `SaveJsonNode` writes.

The V3 API does not provide a built-in "list files by extension" route — the `/internal/files/input` route returns all files with image metadata, which is unsuitable. Instead, the node will use a **static options list** populated at schema definition time by scanning the directory, combined with an explicit **`fingerprint_inputs`** override for cache invalidation when the file on disk changes.

This is the same approach used by ComfyUI's built-in `LoadImage` V1 node (which calls `os.listdir(folder_paths.get_input_directory())` in `INPUT_TYPES`). The V3 equivalent places the scan result in `io.Combo.Input(options=[...])`.

**Limitation:** Because `define_schema()` is called once at ComfyUI startup, newly added `.json` files will only appear in the dropdown after restarting ComfyUI (or refreshing the node definitions). This is the same behavior as all ComfyUI loader nodes that use static file listing.

## Rationale

- **Combo dropdown** over a freeform string input: prevents typos and path-traversal attacks by constraining selection to files that actually exist in the sandboxed input directory. Matches the UX of every other ComfyUI loader node.
- **`fingerprint_inputs` with mtime** over `not_idempotent=True`: avoids unnecessary re-reads when the file hasn't changed, while still detecting on-disk modifications. `not_idempotent` would force a re-read every execution — wasteful for static config files.
- **Dict-only validation**: JSON files can contain arrays or scalars at the top level, but the `JSON_OBJECT` type contract is a dict. Rejecting non-dict top-level values with a clear error is safer than silently wrapping them.
- **Input directory only** (not output or arbitrary paths): follows the established ComfyUI security model. The output directory is for generated artifacts; the input directory is for user-supplied data.

## Considered Alternatives

| Decision | Chosen Shape | Alternatives Considered | Trade-Off Summary |
|----------|--------------|-------------------------|-------------------|
| File selection UI | `io.Combo.Input` with static file scan | Freeform `io.String.Input` for filename | Combo prevents typos and path traversal; freeform would need manual validation and offers worse UX |
| File listing source | Scan `folder_paths.get_input_directory()` at schema time | `io.RemoteOptions` with `/internal/files/input` route | The internal route returns image-oriented metadata and doesn't filter by extension; manual scan is simpler and proven |
| Cache strategy | `fingerprint_inputs` with `os.path.getmtime()` | `not_idempotent=True` (never cache) | Mtime fingerprinting avoids redundant disk reads; not_idempotent wastes cycles on static files |
| Non-dict handling | Raise `ValueError` | Wrap in `{"data": value}` | Wrapping silently changes the data shape; an explicit error is more honest and debuggable |
| Directory scope | Input directory only | Input + output directories | Keeps scope minimal and avoids confusion about which directory is being read; output dir files can be moved to input if needed |

## Pattern Alignment

- **Single-file module** — follows the existing pattern of all node classes in `nodes.py` (no new files).
- **Module-level helper function** — the JSON file scanning helper follows the pattern of `_get_next_counter()`, `_coerce_json_object()`, and other private helpers.
- **`folder_paths` for directory resolution** — matches `SaveJsonNode`'s use of `folder_paths.get_output_directory()`.
- **`os.path.realpath()` path-traversal guard** — mirrors the subfolder validation in `SaveJsonNode.execute()`.
- **Node ID naming** — `Mistralys_LoadJson` follows the `Mistralys_{PascalName}` convention.
- **Explicit node registration** — follows the import-and-list pattern in `__init__.py`.

## Detailed Steps

### Step 1: Add helper function `_list_json_files()`

Add a module-level helper in `nodes.py` (after the existing `_coerce_to_bool` function, before `_raise_getter_error`) that scans the input directory for `.json` files:

```python
def _list_json_files():
    """Return a sorted list of .json filenames in ComfyUI's input directory.

    Scans recursively and returns paths relative to the input directory
    (e.g. 'config.json', 'subfolder/data.json'). Returns an empty list
    if the directory is unreadable.
    """
    input_dir = folder_paths.get_input_directory()
    json_files = []
    try:
        for root, _dirs, files in os.walk(input_dir):
            for f in files:
                if f.lower().endswith(".json"):
                    rel = os.path.relpath(os.path.join(root, f), input_dir)
                    json_files.append(rel.replace(os.sep, "/"))
    except OSError:
        return []
    json_files.sort()
    return json_files
```

### Step 2: Add `LoadJsonNode` class

Add the node class at the end of `nodes.py`, just before the `SaveJsonNode` class (to keep load/save adjacent):

```python
class LoadJsonNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        json_files = _list_json_files()
        return io.Schema(
            node_id="Mistralys_LoadJson",
            display_name="JSON Load File",
            category="json",
            inputs=[
                io.Combo.Input("file",
                    options=json_files,
                    tooltip="Select a .json file from ComfyUI's input directory.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The parsed JSON object from the file.",
                ),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, file):
        """Re-execute when the selected file changes on disk."""
        input_dir = folder_paths.get_input_directory()
        file_path = os.path.join(input_dir, file)
        real_input = os.path.realpath(input_dir)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_input + os.sep) and real_file != real_input:
            return None
        try:
            return os.path.getmtime(real_file)
        except OSError:
            return None

    @classmethod
    def execute(cls, file):
        # 1. Resolve and validate file path
        input_dir = folder_paths.get_input_directory()
        file_path = os.path.join(input_dir, file)
        real_input = os.path.realpath(input_dir)
        real_file = os.path.realpath(file_path)
        if not real_file.startswith(real_input + os.sep) and real_file != real_input:
            raise ValueError(
                f"File path resolves outside the input directory: {file}"
            )

        # 2. Read and parse JSON
        with open(real_file, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in file '{file}': {e}") from e

        # 3. Validate top-level type
        if not isinstance(data, dict):
            raise ValueError(
                f"File '{file}' contains a {type(data).__name__} at the top level, "
                f"but a JSON object (dict) is required."
            )

        return io.NodeOutput(data)
```

### Step 3: Register `LoadJsonNode` in `__init__.py`

1. Add `LoadJsonNode` to the import statement from `.nodes`.
2. Add `LoadJsonNode` to the `get_node_list()` return array, positioned before `SaveJsonNode`.

### Step 4: Update project documentation

Update all documentation affected by the new node (per AGENTS.md maintenance rules).

## Dependencies

- `folder_paths` (ComfyUI built-in) — `get_input_directory()` function.
- `json` (stdlib) — already imported in `nodes.py`.
- `os` (stdlib) — already imported in `nodes.py`.

No new external dependencies.

## Required Components

- [nodes.py](nodes.py) — New `_list_json_files()` helper + `LoadJsonNode` class (modified).
- [__init__.py](__init__.py) — Import and register `LoadJsonNode` (modified).
- [docs/agents/projects/json-node-project.md](docs/agents/projects/json-node-project.md) — Add node spec (modified).
- [docs/agents/project-manifest/api-surface.md](docs/agents/project-manifest/api-surface.md) — Add node to API table (modified).
- [docs/agents/project-manifest/data-flows.md](docs/agents/project-manifest/data-flows.md) — Add load flow (modified).
- [docs/agents/project-manifest/constraints.md](docs/agents/project-manifest/constraints.md) — Add input-directory constraint (modified).
- [docs/agents/project-manifest/file-tree.md](docs/agents/project-manifest/file-tree.md) — Update inline `nodes.py` comment: change "13" to "14" and append `_list_json_files` to the helper name list (modified).
- [AGENTS.md](AGENTS.md) — Update node count from 13 to 14, add design decision (modified).
- [README.md](README.md) — Add node to feature table (modified).
- [changelog.md](changelog.md) — Add entry (modified).

## Assumptions

- `folder_paths.get_input_directory()` is always available and returns a valid path in every ComfyUI installation.
- `.json` files in the input directory are UTF-8 encoded (consistent with the project's UTF-8-only constraint).
- Users understand that files must be placed in the input directory before starting/refreshing ComfyUI.
- The input directory is not excessively large (the recursive scan at startup is fast for typical use cases).

## Constraints

- **Input directory only** — files must reside in `folder_paths.get_input_directory()`. No arbitrary filesystem paths.
- **UTF-8 encoding only** — matches the existing project constraint.
- **Dict-only top-level** — JSON files with arrays, strings, numbers, or booleans at the root are rejected with a clear error.
- **Static file list** — the dropdown is populated at ComfyUI startup; new files require a restart/refresh to appear.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **V3 API only** — no V1 fallback.

## Out of Scope

- **File upload via drag-and-drop** — `io.UploadType` is designed for media files; JSON files should be placed in the input directory manually or via the API.
- **Editing or modifying loaded JSON** — the node is read-only; mutations use the existing setter/merge nodes.
- **Loading from output directory** — output files can be moved to input if needed.
- **Loading multiple files** — this node loads a single file; batching is a separate concern.
- **Schema validation** — the node does not validate the JSON structure beyond requiring a top-level dict.
- **File watching / hot-reload of the dropdown** — the static file list is a known limitation of ComfyUI's architecture.

## Acceptance Criteria

1. A `LoadJsonNode` class exists in `nodes.py` with node ID `Mistralys_LoadJson` and display name "JSON Load File".
2. The node shows a dropdown listing all `.json` files (recursively) from ComfyUI's input directory.
3. Selecting a file and executing the node outputs the parsed dict as a `JSON_OBJECT`.
4. Non-dict top-level JSON values produce a clear `ValueError`.
5. Malformed JSON files produce a clear `ValueError` including the parse error.
6. Path traversal attempts (e.g. `../../etc/passwd`) are rejected — the resolved path must stay within the input directory.
7. The node re-executes when the selected file's content changes on disk (mtime-based fingerprinting).
8. The node uses cached output when the file is unchanged between runs.
9. The node is registered in `__init__.py` and appears in ComfyUI's node menu under the "json" category.
10. All documentation listed in Documentation Updates is updated.

## Testing Strategy

Manual testing in ComfyUI (consistent with the project's existing test approach — no automated test framework).

## Test Plan

- **Load valid dict file** — Place a `{"key": "value"}` JSON file in the input directory, select it, execute → verify `JSON_OBJECT` output matches. — AC 3
- **Load nested dict file** — Place a deeply nested JSON file, select it, execute → verify nested structure is preserved. — AC 3
- **Connect to getter nodes** — Load a JSON file, connect output to `JsonGetStringNode` → verify value retrieval works. — AC 3
- **Load array file** — Place a `[1, 2, 3]` JSON file, select it, execute → verify `ValueError` with "dict is required" message. — AC 4
- **Load scalar file** — Place a `"hello"` JSON file, select it, execute → verify `ValueError`. — AC 4
- **Load malformed file** — Place a file with invalid JSON syntax, select it, execute → verify `ValueError` with parse error details. — AC 5
- **Path traversal rejection** — (Developer test) Manually invoke `execute()` with a `../` path → verify `ValueError`. — AC 6
- **Mtime cache hit** — Execute the node twice without modifying the file → verify second run uses cache (check execution log). — AC 7, 8
- **Mtime cache miss** — Execute the node, modify the file on disk, execute again → verify re-read with updated content. — AC 7
- **Dropdown population** — Place multiple `.json` files (including in subdirectories) in the input directory, restart ComfyUI → verify all appear in the dropdown sorted alphabetically with relative paths. — AC 2
- **Empty input directory** — Remove all `.json` files from the input directory, restart ComfyUI → verify node loads without error (empty combo). — AC 2
- **Node registration** — Search for "JSON Load File" in ComfyUI's node menu → verify it appears under "json" category. — AC 9

## Documentation Updates

Per AGENTS.md maintenance rules:

- [docs/agents/projects/json-node-project.md](docs/agents/projects/json-node-project.md) — Add "JSON Load File" node specification under "The Nodes" section.
- [docs/agents/project-manifest/api-surface.md](docs/agents/project-manifest/api-surface.md) — Add `LoadJsonNode` row to the node overview table and detailed section; add `_list_json_files()` to the Private Helper Functions section (parameters: none; returns: sorted list of relative `.json` file paths or empty list on `OSError`).
- [docs/agents/project-manifest/data-flows.md](docs/agents/project-manifest/data-flows.md) — Add "JSON File Loading" flow section.
- [docs/agents/project-manifest/constraints.md](docs/agents/project-manifest/constraints.md) — Scope the existing "Output directory only" constraint to `SaveJsonNode` specifically (e.g. retitle it "Fixed directory only — no arbitrary file path support"), then add a separate "Input directory only" constraint for `LoadJsonNode`.
- [docs/agents/project-manifest/tech-stack.md](docs/agents/project-manifest/tech-stack.md) — Update the `folder_paths` dependency description from "Resolve output directory path" to "Resolve input and output directory paths".
- [AGENTS.md](AGENTS.md) — Update section 5 (Project Stats): change "Thirteen" to "Fourteen" in the node count and update the architecture description. Update section 6 (Project File Layout): change "13" to "14" in the `nodes.py` inline comment and append `_list_json_files` to the helper name list.
- [README.md](README.md) — Add "JSON Load File" to the nodes table and update feature list.
- [changelog.md](changelog.md) — Add entry for new node.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Empty combo on first install** | If no `.json` files exist in the input directory, the combo will be empty. ComfyUI handles empty combos gracefully (the node simply can't be executed). Document this in the README. |
| **Large files causing memory pressure** | JSON files in a workflow context are typically small (metadata, configs). No explicit size limit is needed; Python's `json.loads()` handles reasonable file sizes. If this becomes an issue, a size cap can be added later. |
| **Windows reserved device names** | Per the global insight from the prior project's security audit, `os.path.basename()` does not filter names like `CON`, `NUL`. However, since the load node's file selection is constrained to the combo dropdown (populated by actual file listing), reserved device names would only appear if such a file literally exists in the input directory — which is a valid file to load. No additional mitigation needed beyond the path-traversal guard. |
| **Race condition: file deleted after dropdown populated** | If a user selects a file that was deleted between schema load and execution, `open()` will raise `FileNotFoundError`. This is an acceptable Python error — no special handling needed. |
| **Symlink escape** | `os.path.realpath()` resolves symlinks before the boundary check, preventing symlink-based directory escape. Already proven in `SaveJsonNode`. |
