# AGENTS.md — ComfyUI JSON Nodes

> **This file is the operating manual for AI agents entering this codebase.**
> Read it in full before making any changes.

---

## 1. Project Documentation — Start Here

| Document | Path | Purpose |
|----------|------|---------|
| Project Manifest | `docs/agents/project-manifest/README.md` | Structured overview of the codebase (tech stack, API surface, data flows, constraints) |
| Project Specification | `docs/agents/projects/json-node-project.md` | Problem statement, node properties, and behavioral requirements |
| Implementation Plan | `docs/agents/plans/2026-07-02-json-nodes/plan.md` | Detailed architecture, steps, patterns, and acceptance criteria |
| README | `README.md` | User-facing project description |

### Quick Start Workflow

1. **Read** `docs/agents/projects/json-node-project.md` — understand what the nodes do and why they exist.
2. **Read** `docs/agents/plans/2026-07-02-json-nodes/plan.md` — understand the architecture, file layout, and implementation details.
3. **Read** the ComfyUI V3 API skills in the companion workspace `comfyui-custom-node-skills/plugins/comfyui-custom-nodes/skills/` — understand the API surface.
4. **Then** read source files as needed.

### Companion Workspace: ComfyUI Custom Node Skills

The multi-root workspace includes `comfyui-custom-node-skills`, which contains comprehensive V3 API documentation and reference implementations. Key resources:

| Resource | Path (relative to skills workspace root) | Use For |
|----------|------------------------------------------|---------|
| Node Basics Skill | `plugins/comfyui-custom-nodes/skills/comfyui-node-basics/SKILL.md` | V3 node class structure |
| Node Outputs Skill | `plugins/comfyui-custom-nodes/skills/comfyui-node-outputs/SKILL.md` | Data + UI output patterns, PreviewText |
| Node Inputs Skill | `plugins/comfyui-custom-nodes/skills/comfyui-node-inputs/SKILL.md` | Input definitions |
| Node Packaging Skill | `plugins/comfyui-custom-nodes/skills/comfyui-node-packaging/SKILL.md` | pyproject.toml, registration |
| Node Lifecycle Skill | `plugins/comfyui-custom-nodes/skills/comfyui-node-lifecycle/SKILL.md` | Caching, execution behavior |
| Reference Implementation | `skill_test_nodes/` | Working V3 node examples |

---

## 2. Documentation Maintenance Rules

When making changes to the codebase, update the corresponding documentation:

| Change Made | Documents to Update |
|---|---|
| Node inputs/outputs modified | `docs/agents/projects/json-node-project.md`, `docs/agents/project-manifest/api-surface.md`, `README.md` |
| File added or renamed | `docs/agents/plans/2026-07-02-json-nodes/plan.md` (file layout section), `docs/agents/project-manifest/file-tree.md` |
| Node behavior changed | `docs/agents/projects/json-node-project.md`, `docs/agents/project-manifest/data-flows.md`, `README.md` |
| Dependencies added | `pyproject.toml`, `docs/agents/project-manifest/tech-stack.md`, `README.md` |
| New plan created | `docs/agents/plans/` (new plan directory) |
| Constraints or conventions changed | `docs/agents/project-manifest/constraints.md` |

---

## 3. Efficiency Rules — Search Smart

- **Finding files?** Check the file layout in `plan.md` FIRST.
- **Understanding node behavior?** Check `json-node-project.md` FIRST.
- **Understanding V3 API patterns?** Check the skills in `comfyui-custom-node-skills` FIRST.
- **Understanding registration / packaging?** Check `comfyui-node-packaging` skill FIRST.
- **Only then** read source files.

---

## 4. Failure Protocol & Decision Matrix

| Scenario | Action | Priority |
|---|---|---|
| Ambiguous requirement | Consult `json-node-project.md` for intent; use most restrictive interpretation | MUST |
| Documentation/code conflict | Trust documentation (`json-node-project.md`, `plan.md`), flag code for fix | MUST |
| Missing documentation | Flag gap, do not invent facts | MUST |
| Unsure about V3 API usage | Consult the skills in `comfyui-custom-node-skills`; check `skill_test_nodes/` for working examples | MUST |
| V3 API pattern not covered by skills | Check ComfyUI source if accessible; flag gap in skills workspace | SHOULD |
| Untested code path | Proceed with caution, add manual test recommendation | SHOULD |
| Tempted to add features beyond spec | Do not. This project is intentionally focused — fourteen nodes, no extras | MUST |

---

## 5. Project Stats

| Property | Value |
|---|---|
| **Language** | Python 3.10+ |
| **Architecture** | Fourteen ComfyUI V3 custom nodes (4 primitive + 1 load + 3 structural + 5 getter + 1 output) |
| **API** | ComfyUI V3 (`comfy_api.latest`) — no V1 fallback |
| **Package Manager** | pip (installed via ComfyUI custom_nodes) |
| **Build Tool** | None (pure Python) |
| **Test Framework** | Mock-based unit tests (`verify_*.py`) + manual testing in ComfyUI |
| **External Dependencies** | None (stdlib + ComfyUI builtins only) |
| **License** | MIT |

---

## 6. Project File Layout

```
comfyui-json-nodes/
  __init__.py           # Extension registration: JsonNodesExtension + comfy_entrypoint()
  nodes.py              # All 14 node classes + helpers (_set_nested_key, _get_next_counter, _coerce_json_object, _deep_merge, _sanitize_key, _MISSING, _get_nested_value, _coerce_to_string, _coerce_to_int, _coerce_to_float, _coerce_to_bool, _list_json_files, _guard_input_path, _raise_getter_error)
  pyproject.toml        # Package metadata
  README.md             # User-facing documentation
  LICENSE               # MIT license
  AGENTS.md             # This file
  CLAUDE.md             # Claude companion (imports AGENTS.md)
  changelog.md          # Project changelog
  tests/
    verify_wp003.py     # Mock-based unit tests for LoadJsonNode (WP-003)
  docs/
    agents/
      project-manifest/ # Structured codebase overview for AI agents
      plans/            # Implementation plans
      projects/         # Project specifications
```

---

## 7. Key Design Decisions

These decisions are documented in `plan.md` and are **not negotiable** without explicit user approval:

- **V3 API only** — no V1 compatibility layer.
- **`io.Custom("JSON_OBJECT")` inline type** — custom connection type defined as a module-level constant; no separate type registration.
- **Deep copy on input** — each node deep-copies the incoming JSON object before mutation for fork-safety.
- **Dot notation** — keys containing dots (e.g. `address.city`) are always interpreted as nested paths; there is no escape mechanism.
- **No external dependencies** — stdlib and ComfyUI builtins only.
- **Folder-scan counter** — matches ComfyUI's `ImageSaveHelper` pattern for SaveJsonNode.
- **`not_idempotent=True`** — SaveJsonNode must re-execute every run, never cache.
- **`is_output_node=True`** — SaveJsonNode writes to disk (side effect).
- **UTF-8 encoding only** — no encoding selection.
- **Output directory only** — no arbitrary file path support.
