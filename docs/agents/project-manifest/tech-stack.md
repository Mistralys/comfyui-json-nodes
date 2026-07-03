# Tech Stack & Patterns

## Runtime

| Property | Value |
|---|---|
| Language | Python 3.10+ |
| Host Platform | ComfyUI (custom node) |
| API | ComfyUI V3 (`comfy_api.latest`) — no V1 fallback |

## Dependencies

| Dependency | Source | Purpose |
|---|---|---|
| `comfy_api.latest` | ComfyUI built-in | V3 node API (`io`, `ui`, `ComfyNode`, `ComfyExtension`) |
| `typing_extensions` | ComfyUI built-in | `@override` decorator for `get_node_list()` |
| `folder_paths` | ComfyUI built-in | Resolve input and output directory paths |
| `os` | Python stdlib | Path manipulation, directory creation |
| `re` | Python stdlib | Filename pattern matching for counter scan |
| `json` | Python stdlib | JSON serialization/deserialization |
| `copy` | Python stdlib | Deep copy of JSON objects between nodes |

No external (pip) dependencies.

## Architecture

Fourteen custom nodes registered as a ComfyUI V3 extension.

| Pattern | Description |
|---|---|
| V3 Node class | `io.ComfyNode` subclass with `define_schema()` + `execute()` classmethods |
| V3 Registration | `ComfyExtension` subclass + module-level `comfy_entrypoint()` |
| Folder-scan counter | Scan target directory for existing files to determine next counter value |

## Build & Packaging

| Property | Value |
|---|---|
| Package manager | pip (installed via ComfyUI `custom_nodes/`) |
| Build tool | None (pure Python) |
| Package metadata | `pyproject.toml` |
| Test framework | Manual testing in ComfyUI |
