# Project: ComfyUI JSON Nodes

## The Problem

I like to collect metadata in my ComfyUI workflows, and while there are nodes that collect LoRA information, for example, it is often not formatted the way I want, or incomplete, or contains too much extraneous information. Additionally, my philosophy is to keep it as simple as possible to fight against the infamous node rot where nodes are quick to be deprecated, obsolete or unmaintained.

## The Idea

I would like to create a small set of nodes that can be used to build a JSON object with freeform values, in a way that I can just insert them anywhere in the flow to capture values without breaking the rest of the flow by leveraging the passthrough of values.

## How it works

Every node is a JSON object in the background, and nodes connected to each other are additive. If no existing JSON Object node is connected as input, a new JSON Object is created automatically.

For example, connecting two nodes:

1. JSON String node, key `string`, value `foobar` = `{"string":"foobar"}`
2. JSON Int node, key `int`, value `42` = `{"string":"foobar","int":42}`

## The Nodes

### "JSON String"
_Add a string key to an JSON object._

- Input: `json-object` - Optional JSON Object (creates a new one if not specified).
- Input: `string` - Value.
- Input: `string` - Key name.
- Output: `json-object` - The JSON Object.
- Output: `string` - Value (passthrough of the value).
- Output: `string` - Key name.

### "JSON Int" 
_Add an integer key to an JSON object.

- Input: `json-object` - Optional JSON Object (creates a new one if not specified).
- Input: `int` - Value.
- Input: `string` - Key name.
- Output: `json-object` - The JSON Object.
- Output: `int` - Value (passthrough of the value).
- Output: `string` - Key name.

### "JSON Float"
_Add a float key to an JSON object._

- Input: `json-object` - Optional JSON Object (creates a new one if not specified).
- Input: `float` - Value.
- Input: `string` - Key name.
- Output: `json-object` - The JSON Object.
- Output: `float` - Value (passthrough of the value).
- Output: `string` - Key name.

### "JSON Boolean" 
_Add a boolean key to an JSON object._

- Input: `json-object` - Optional JSON Object (creates a new one if not specified).
- Input: `bool` - Value.
- Input: `string` - Key name.
- Output: `json-object` - The JSON Object.
- Output: `bool` - Value (passthrough of the value).
- Output: `string` - Key name.

### "JSON Object"
_Nest the values of a JSON Object into the specified key._

- Input: `json-object` - Optional JSON Object (creates a new one if not specified).
- Input: `json-object` - Value (Mandatory. The object's values are deep-copied into the key).
- Input: `string` - Key name.
- Output: `json-object` - The JSON Object.
- Output: `json-object` - Value (passthrough).
- Output: `string` - Key name.

### "JSON Merge Objects"
_Merge all top-level keys from one JSON object into another._

Use this to combine multiple separately-built JSON objects into one without nesting them under a key.

- Input: `json-object` - Optional JSON Object to merge into (creates a new one if not specified).
- Input: `json-object` (×6) - Merge sources. All keys are copied into the target in order.
- Input: `boolean` - `deep_merge` — When `false` (default), duplicate keys in the target are replaced entirely by the source value. When `true`, if both the target and source values for a key are objects, they are merged recursively instead of replaced.
- Output: `json-object` - The merged JSON Object.
- Output: `json-object` (×6) - Merge source passthroughs (for connecting to multiple targets).

### "JSON Reroute"
_Typed passthrough for JSON object connections._

Use this as a junction point to split or reroute `JSON_OBJECT` connections without needing a setter node.

- Input: `json-object` - Optional JSON Object (outputs an empty `{}` if not connected).
- Output: `json-object` - Deep copy of the input, or `{}` if no input is connected.

### "JSON to String"
_Converts a JSON node to its string representation._

- Input: `json-object` - Existing JSON Object (mandatory).
- Output: `json-object` - Passthrough of the JSON object.
- Output: `string` - The serialized JSON.

### Save JSON
_Converts the node to string and saves it to a `.json` file._

- Input: `json-object` - Existing JSON Object (mandatory).
- Input: `string` - File name (without extension).
- Input: `string` - Subfolder name (optional).
- Input: `int` - Counter length (To avoid duplicates, set to `0` to disable).

The node builds the relative output path using the filename, optional counter, fixed `json` extension and optional folder name. It then saves the file to ComfyUI's output folder with the serialized JSON string as content. 

- **Subfolder creation** - The subfolder is created automatically if it does not exist yet.
- **Subfolder whitespace stripping** — `subfolder` is `strip()`-ed before use. A whitespace-only subfolder is treated as no subfolder.
- **Counter disabled at 0** — when `counter_length` is `0`, the file is written as `{filename}.{extension}` and overwrites on repeated runs.

#### Counter Convention

The counter is incremented for each duplicate file, which is determined by scanning the target folder (like the ImageSaveHelper does) for maximum reliability.

The counter follows ComfyUI's `ImageSaveHelper` pattern:

- Scan the target directory for files matching `{filename}_{counter}.{extension}`.
- Next counter = `max(existing) + 1`, or `1` if no matches.
- Counter is zero-padded to `counter_length` digits.
- Separator character is `_`.

#### File I/O

- All writes go through Python's `open(path, "w", encoding="utf-8")`.
- Subfolders are created with `os.makedirs(exist_ok=True)`.
- The output base directory is resolved via `folder_paths.get_output_directory()`.
- `subfolder` is validated with `os.path.realpath()` against the output directory boundary. Any path resolving outside the output directory raises `ValueError`. This is an active security control, not a documentation note.
- `filename` is processed with `os.path.basename()` before use. Directory separators in the filename input are stripped unconditionally.

### "JSON Load File"
_Read a `.json` file from ComfyUI's input directory and output its parsed data._

- Input: `filename` - Combo dropdown listing all `.json` files found (recursively) in ComfyUI's input directory. Populated at ComfyUI startup.
- Output: `json-object` - The parsed JSON data as a `JSON_OBJECT`.

The dropdown is populated by scanning the input directory at schema-definition time (ComfyUI startup). After adding new `.json` files to the input directory, restart ComfyUI or refresh node definitions to update the list. If no `.json` files are present, the dropdown shows a single empty placeholder — executing the node in this state raises a `ValueError` with the message `"No file selected — add .json files to the input directory and restart ComfyUI."`.

The selected file must contain a top-level JSON object (`{...}`). Arrays, strings, numbers, and other non-object values are rejected with a clear `ValueError`.

Files larger than 50 MB are rejected with a clear `ValueError` before the file is read. This prevents accidental memory exhaustion from unexpectedly large files. The limit is controlled by the `_MAX_JSON_FILE_SIZE` module-level constant.

Cache invalidation is handled via `fingerprint_inputs()` using the file's modification time (`mtime`). The node re-executes only when the selected file changes on disk, and uses cached output otherwise. `fingerprint_inputs()` returns `""` (rather than raising) for empty or invalid filenames so ComfyUI degrades gracefully.

**Security:** File selection is constrained to the combo dropdown, preventing freeform path injection. `_guard_input_path()` in both `execute()` and `fingerprint_inputs()` ensures the resolved path stays within the input directory boundary via `os.path.realpath()` + `startswith()` check.

## Nested JSON Structures

To nest values, two approaches:

1. Use the "JSON Object" node to add a set of values in a key.
2. Use the dot notation in the key name, e.g. `address.city` to automatically nest the value.

