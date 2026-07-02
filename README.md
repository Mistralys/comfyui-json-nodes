# ComfyUI JSON Nodes

Build, read, and save JSON objects directly in your ComfyUI workflow — no scripting required.

## Why Use It

Capturing workflow metadata (sampler settings, LoRA names, prompt snippets) normally means bolting on complex nodes or post-processing scripts. ComfyUI JSON Nodes lets you tap into any value already flowing through your graph, collect it into a typed JSON object, and save it alongside your image — all without rewiring a single existing connection.

## Features

- **Non-destructive capture** — every node passes its value straight through, so existing node connections are never broken.
- **Typed setter nodes** — add string, integer, float, boolean, or nested object values with dedicated nodes.
- **Dot-notation nesting** — use `model.name` as a key to create nested structures automatically.
- **Merge independent objects** — combine two separately-built JSON objects into one without nesting.
- **Read values back** — getter nodes retrieve any stored key as the right type, with automatic conversion.
- **Configurable error handling** — raise workflow errors on missing keys, empty strings, or zero values.
- **Serialize to string** — convert any JSON object to a pretty-printed string for use in text nodes.
- **Save to disk** — write `.json` files to ComfyUI's output directory with auto-incrementing counters.
- **Canvas tooltips** — every input and output shows a description when you hover over it.

## Requirements

- ComfyUI with V3 API support
- Python 3.10+

## Quick Start

Clone the repository into ComfyUI's `custom_nodes` directory and restart ComfyUI:

```bash
cd /path/to/ComfyUI/custom_nodes
git clone https://github.com/Mistralys/comfyui-json-nodes.git
```

The nodes appear under the **json** category in the node picker.

## Usage Example

Chain setter nodes to build a JSON object, then save it:

```
JSON String  (key="name",    value="my_workflow")
  → JSON Int   (key="steps",   value=20)
    → JSON Float (key="cfg",    value=7.5)
      → JSON Boolean (key="hi_res", value=True)
        → Save JSON (filename="metadata")
```

This writes `metadata_00001.json` to ComfyUI's output directory:

```json
{
  "name": "my_workflow",
  "steps": 20,
  "cfg": 7.5,
  "hi_res": true
}
```

![Basic Example](/docs/design/screenshot-basic.png)

> Easy debugging by showing the serialized JSON string in the native "Preview as Text" node.

## Nodes

All nodes are in the **json** category.

### Setter Nodes — Build a JSON Object

| Node | Purpose |
|------|---------|
| **JSON String** | Add a string value under a key |
| **JSON Int** | Add an integer value under a key |
| **JSON Float** | Add a float value under a key |
| **JSON Boolean** | Add a boolean value under a key |
| **JSON Object** | Nest a sub-object under a key |

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
| **Save JSON** | Write the JSON object to a `.json` file in ComfyUI's output directory |

`Save JSON` accepts a base filename, an optional subfolder, and a counter length (set to `0` to overwrite on every run instead of incrementing). Subfolders are created automatically. Path-traversal attacks are blocked: the filename is sanitized with `os.path.basename()` and the resolved subfolder path is validated to stay within the output directory.

## Dot Notation

Any key containing a dot is treated as a nested path. Setting `key="model.name"` with value `"sdxl"` produces:

```json
{
  "model": {
    "name": "sdxl"
  }
}
```

Intermediate dictionaries are created automatically. All nodes support dot notation; there is no escape mechanism for literal dots in key names.

## Learn More

| Resource | Description |
|----------|-------------|
| [Node Reference](docs/agents/projects/json-node-project.md) | Full input/output specifications for every node |
| [Changelog](changelog.md) | Version history and recent changes |
