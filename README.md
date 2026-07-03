# ComfyUI JSON Nodes

Build, read, and save JSON objects directly in your [ComfyUI][https://comfy.org/] Workflow — no scripting required.

## Why Use It

These nodes let you collect values in your workflow into typed JSON objects without rewiring existing connections. This data can then be saved alongside your image, and be accessed anytime.

## Usage Examples

- Collecting Workflow metadata.
- Saving configuration data.

## Built To Last

These nodes are built as close to the vanilla ComfyUI feature set as possible, and each of them fulfills a singular purpose. This makes them very stable from the start.

## Features

- **Parallel flow** — All nodes can capture data without disrupting your existing flow.
- **Data types** — dedicated nodes for basic types like strings, integers, floats and booleans.
- **Nested data** — Use dot notation in keys (`model.name`) to create nested structures.
- **Merge data** — combine multiple data sets to gather the entire data your workflow produces.
- **Access values** — Stored values can be accessed anytime.
- **Customize errors** — Choose when to fail and provide custom error messages.
- **Display & Save** — display a pretty-printed JSON string, or write to JSON files.

## Requirements

- ComfyUI with V3 API support
- Python 3.10+

## Quick Start

Clone the repository into ComfyUI's `custom_nodes` directory and restart ComfyUI:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/Mistralys/comfyui-json-nodes.git
```

## Usage Example

![Basic Example](/docs/design/screenshot-basic.png)

> Debugging is possible by showing the serialized JSON string in the native "Preview as Text" node.

## Nodes

All nodes are in the **json** category.

### Setter Nodes — Build a JSON Object

| Node | Purpose |
|------|---------|
| **JSON Set String** | Add a string value under a key |
| **JSON Set Int** | Add an integer value under a key |
| **JSON Set Float** | Add a float value under a key |
| **JSON Set Boolean** | Add a boolean value under a key |
| **JSON Set Object** | Nest a sub-object under a key |

Each setter accepts an optional incoming `JSON_OBJECT` (creates a fresh one if none is connected) and outputs the updated object plus a passthrough of the value and key.

### Structural Nodes — Combine and Convert

| Node | Purpose |
|------|---------|
| **JSON Merge Objects** | Merge keys from up to six objects into a base object; toggle `deep_merge` to recursively merge nested objects instead of replacing them |
| **JSON to String** | Serialize an object to a pretty-printed JSON string |

### Getter Nodes — Read Values Back Out

| Node | Returns |
|------|---------|
| **JSON Get String** | String (with optional precision rounding) |
| **JSON Get Int** | Integer |
| **JSON Get Float** | Float (with optional precision rounding) |
| **JSON Get Bool** | Boolean |
| **JSON Get Object** | Nested `JSON_OBJECT` |

Getters convert stored values to the requested type automatically. All control inputs (error flags, precision, custom message) are passed through as outputs so daisy-chained getters share the same configuration.

### Output Node — Save to Disk

| Node | Purpose |
|------|---------|
| **JSON Save File** | Write the JSON object to a `.json` file in ComfyUI's output directory |

## Dot Notation

Any key containing a dot is treated as a nested path. Setting `key="model.name"` with value `"sdxl"` produces:

```json
{
  "model": {
    "name": "sdxl"
  }
}
```

All nodes support dot notation, and each dot adds a nesting level. This works both for setting and getting values.

## Learn More

| Resource | Description |
|----------|-------------|
| [Node Reference](docs/agents/projects/json-node-project.md) | Full input/output specifications for every node |
| [Changelog](changelog.md) | Version history and recent changes |
