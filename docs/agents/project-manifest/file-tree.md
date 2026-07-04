# File Tree

```
comfyui-json-nodes/
  __init__.py           # Extension registration: JsonNodesExtension + comfy_entrypoint()
  nodes.py              # All 15 node classes + helpers (_set_nested_key, _get_next_counter, _coerce_json_object, _deep_merge, _sanitize_key, _MISSING, _get_nested_value, _coerce_to_string, _coerce_to_int, _coerce_to_float, _coerce_to_bool, _list_json_files, _guard_input_path, _raise_getter_error)
  pyproject.toml        # Package metadata (name, version, license, ComfyUI entry point)
  README.md             # User-facing documentation
  LICENSE               # MIT license
  AGENTS.md             # AI agent operating manual
  CLAUDE.md             # Claude companion (imports AGENTS.md)
  changelog.md          # Project changelog
  tests/
    verify_wp003.py     # Mock-based unit tests for LoadJsonNode (WP-003)
  docs/
    agents/
      project-manifest/ # Structured codebase overview for AI agents
        README.md       #   Manifest index
        api-surface.md  #   Node class schemas and method signatures
        constraints.md  #   Design rules and conventions
        data-flows.md   #   Execution paths through the nodes
        file-tree.md    #   This file
        tech-stack.md   #   Runtime, dependencies, architecture
      plans/            # Implementation plans
      projects/         # Project specifications
      implementation-history/ # Historical implementation records
```
