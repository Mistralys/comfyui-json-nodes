import os
import re
import json
import copy
import folder_paths
from comfy_api.latest import io, ui

JsonObject = io.Custom("JSON_OBJECT")


def _set_nested_key(obj, key, value):
    """Set a value in a nested dict using dot-notation key traversal.

    Splits key on '.' and traverses/creates intermediate dicts as needed.
    If an intermediate key exists but is not a dict, it is overwritten with
    a new dict.
    """
    parts = key.split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _get_next_counter(directory, filename, extension, counter_length):
    """Return the next integer counter for a filename in the given directory.

    Scans directory for files matching '{filename}_{digits}.{extension}' and
    returns max(found_counters) + 1, or 1 if no matching files exist.
    Uses flexible \\d+ matching to handle counter length changes gracefully.
    counter_length is accepted for call-site consistency but does not affect
    the regex pattern.
    """
    pattern = re.compile(
        r"^" + re.escape(filename) + r"_(\d+)\." + re.escape(extension) + r"$"
    )
    counters = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return 1
    for entry in entries:
        match = pattern.match(entry)
        if match:
            counters.append(int(match.group(1)))
    return max(counters) + 1 if counters else 1


def _coerce_json_object(value):
    """Return value unchanged if it is a dict, None if it is None, or {} for any other type.

    Guards execute methods against non-dict values (e.g. from Reroute nodes) without
    raising errors. The caller decides whether None should become {} via `or {}`.
    """
    if value is None:
        return None
    return value if isinstance(value, dict) else {}


def _deep_merge(target, source):
    """Recursively merge source dict into target dict in place.

    For each key in source:
    - If the key exists in target and both values are dicts, recurse.
    - Otherwise, replace target[key] with source[key].

    source values are assumed to already be deep-copied by the caller.
    """
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


_KEY_COMPONENT_MAX_LENGTH = 40
_MAX_JSON_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _sanitize_key(key):
    """Sanitize a dot-notation key string for use as a JSON property name.

    Strips leading/trailing whitespace, collapses internal whitespace
    (including newlines and tabs) to a single space, and validates that each
    dot-separated component is non-empty and within the maximum allowed length.

    Raises ValueError if any component is empty or exceeds
    _KEY_COMPONENT_MAX_LENGTH characters after sanitization.
    """
    parts = key.strip().split(".")
    sanitized = []
    for part in parts:
        part = re.sub(r"\s+", " ", part).strip()
        if not part:
            raise ValueError(
                f"JSON key contains an empty component after sanitization: {key!r}"
            )
        if len(part) > _KEY_COMPONENT_MAX_LENGTH:
            raise ValueError(
                f"JSON key component {part!r} exceeds the maximum allowed length of "
                f"{_KEY_COMPONENT_MAX_LENGTH} characters."
            )
        sanitized.append(part)
    return ".".join(sanitized)


# --- Getter node helpers ---

_MISSING = object()


def _get_nested_value(obj, key):
    """Read a value from a nested dict using dot-notation key traversal.

    Splits key on '.' and traverses the dict. Returns the value at the leaf,
    or _MISSING if any intermediate key is absent or not a dict, or the final
    key is absent.
    """
    parts = key.split(".")
    current = obj
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
        if not isinstance(current, dict):
            return _MISSING
    if not isinstance(current, dict) or parts[-1] not in current:
        return _MISSING
    return current[parts[-1]]


def _coerce_to_string(value, precision):
    """Convert any JSON-storable value to a string.

    precision controls decimal display when converting float values:
    0 = whole number, >0 = that many decimal places.
    """
    if value is _MISSING or value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if precision == 0:
            return str(int(round(value)))
        return f"{value:.{precision}f}"
    if isinstance(value, dict):
        return json.dumps(value, indent=2, ensure_ascii=False)
    if isinstance(value, list):
        return ""
    return str(value)


def _coerce_to_int(value):
    """Convert any JSON-storable value to an integer."""
    if value is _MISSING or value is None:
        return 0
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except (ValueError, OverflowError):
            return 0
    return 0


def _coerce_to_float(value, precision):
    """Convert any JSON-storable value to a float.

    precision controls rounding: 0 = no rounding (full precision),
    >0 = round to that many decimal places.
    """
    if value is _MISSING or value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int):
        result = float(value)
    elif isinstance(value, float):
        result = value
    elif isinstance(value, str):
        try:
            result = float(value)
        except (ValueError, OverflowError):
            return 0.0
    else:
        return 0.0
    if precision > 0:
        return round(result, precision)
    return result


def _coerce_to_bool(value):
    """Convert any JSON-storable value to a boolean."""
    if value is _MISSING or value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, float):
        return round(value) != 0
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return False



def _list_json_files():
    """Return a sorted list of relative paths to all .json files in ComfyUI's input directory.

    Scans folder_paths.get_input_directory() recursively and returns paths
    relative to the input directory, using forward slashes as separators.
    Returns an empty list if the directory does not exist or cannot be read.
    """
    try:
        input_dir = folder_paths.get_input_directory()
    except Exception:
        return []
    results = []
    try:
        for dirpath, _dirnames, filenames in os.walk(input_dir):
            for filename in filenames:
                if filename.lower().endswith('.json'):
                    abs_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(abs_path, input_dir)
                    # Normalise to forward slashes for cross-platform consistency
                    results.append(rel_path.replace(os.sep, '/'))
    except OSError:
        return []
    return sorted(results)


def _guard_input_path(filename):
    """Resolve a filename relative to the input directory and validate it stays within bounds.

    Returns the resolved real path. Raises ValueError if the filename is empty
    (no file selected) or if the resolved path escapes the input directory.
    """
    if not filename:
        raise ValueError(
            "No file selected \u2014 add .json files to the input directory and restart ComfyUI."
        )
    input_dir = folder_paths.get_input_directory()
    real_input = os.path.realpath(input_dir)
    candidate = os.path.realpath(os.path.join(input_dir, filename))
    if not candidate.startswith(real_input + os.sep) and candidate != real_input:
        raise ValueError(
            f"File path resolves outside the input directory: {filename!r}"
        )
    return candidate


def _raise_getter_error(key, condition, custom_message):
    """Raise a ValueError for a getter node error condition.

    Uses custom_message if non-empty (after strip), otherwise uses a default
    message that includes the key path and condition description.
    """
    msg = custom_message.strip()
    if msg:
        raise ValueError(msg)
    raise ValueError(f"JSON getter error: {condition} (key: '{key}')")


class JsonStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonString",
            display_name="JSON Set String",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to add to, or leave empty to start a new one.",
                ),
                io.String.Input("value", default="",
                    tooltip="The string value to store.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The JSON object with the new key-value pair added.",
                ),
                io.String.Output("VALUE",
                    tooltip="Passthrough of the input value, for connecting to other nodes.",
                ),
                io.String.Output("KEY",
                    tooltip="Passthrough of the key name.",
                ),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        key = _sanitize_key(key)
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        _set_nested_key(obj, key, value)
        return io.NodeOutput(obj, value, key)


class JsonIntNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonInt",
            display_name="JSON Set Int",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to add to, or leave empty to start a new one.",
                ),
                io.Int.Input("value", default=0,
                    tooltip="The integer value to store.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The JSON object with the new key-value pair added.",
                ),
                io.Int.Output("VALUE",
                    tooltip="Passthrough of the input value, for connecting to other nodes.",
                ),
                io.String.Output("KEY",
                    tooltip="Passthrough of the key name.",
                ),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        key = _sanitize_key(key)
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        _set_nested_key(obj, key, value)
        return io.NodeOutput(obj, value, key)


class JsonFloatNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonFloat",
            display_name="JSON Set Float",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to add to, or leave empty to start a new one.",
                ),
                io.Float.Input("value", default=0.0,
                    tooltip="The float value to store.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The JSON object with the new key-value pair added.",
                ),
                io.Float.Output("VALUE",
                    tooltip="Passthrough of the input value, for connecting to other nodes.",
                ),
                io.String.Output("KEY",
                    tooltip="Passthrough of the key name.",
                ),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        key = _sanitize_key(key)
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        _set_nested_key(obj, key, value)
        return io.NodeOutput(obj, value, key)


class JsonBooleanNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonBoolean",
            display_name="JSON Set Boolean",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to add to, or leave empty to start a new one.",
                ),
                io.Boolean.Input("value", default=True,
                    tooltip="The boolean value to store.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The JSON object with the new key-value pair added.",
                ),
                io.Boolean.Output("VALUE",
                    tooltip="Passthrough of the input value, for connecting to other nodes.",
                ),
                io.String.Output("KEY",
                    tooltip="Passthrough of the key name.",
                ),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        key = _sanitize_key(key)
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        _set_nested_key(obj, key, value)
        return io.NodeOutput(obj, value, key)


class JsonObjectNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonObject",
            display_name="JSON Set Object",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to add to, or leave empty to start a new one.",
                ),
                JsonObject.Input("value",
                    tooltip="The JSON sub-object to nest under the specified key.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Property name in the JSON object. Use dots (e.g. 'address.city') for nested structures.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The JSON object with the nested sub-object added.",
                ),
                JsonObject.Output("VALUE",
                    tooltip="Passthrough of the input sub-object, for connecting to other nodes.",
                ),
                io.String.Output("KEY",
                    tooltip="Passthrough of the key name.",
                ),
            ],
        )

    @classmethod
    def execute(cls, value, key, json_object=None):
        key = _sanitize_key(key)
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        value = _coerce_json_object(value) or {}
        _set_nested_key(obj, key, copy.deepcopy(value))
        return io.NodeOutput(obj, value, key)


class JsonMergeObjectsNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonMergeObjects",
            display_name="JSON Merge Objects",
            category="json",
            inputs=[
                JsonObject.Input("json_object", optional=True,
                    tooltip="Connect an existing JSON object to merge into, or leave empty to start a new one.",
                ),
                JsonObject.Input("merge_object_1", optional=True,
                    tooltip="First JSON object to merge in. Its keys are copied into the base object.",
                ),
                JsonObject.Input("merge_object_2", optional=True,
                    tooltip="Second JSON object to merge in. Applied after merge_object_1.",
                ),
                JsonObject.Input("merge_object_3", optional=True,
                    tooltip="Third JSON object to merge in. Applied after merge_object_2.",
                ),
                JsonObject.Input("merge_object_4", optional=True,
                    tooltip="Fourth JSON object to merge in. Applied after merge_object_3.",
                ),
                JsonObject.Input("merge_object_5", optional=True,
                    tooltip="Fifth JSON object to merge in. Applied after merge_object_4.",
                ),
                JsonObject.Input("merge_object_6", optional=True,
                    tooltip="Sixth JSON object to merge in. Applied last.",
                ),
                io.Boolean.Input("deep_merge", default=False,
                    tooltip="When enabled, nested object keys are merged recursively instead of being replaced. When disabled (default), a duplicate key in the merge source overwrites the entire value in the target.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="The combined JSON object after all merges.",
                ),
                JsonObject.Output("MERGE_OBJECT_1",
                    tooltip="Passthrough of merge_object_1, for connecting to other nodes.",
                ),
                JsonObject.Output("MERGE_OBJECT_2",
                    tooltip="Passthrough of merge_object_2, for connecting to other nodes.",
                ),
                JsonObject.Output("MERGE_OBJECT_3",
                    tooltip="Passthrough of merge_object_3, for connecting to other nodes.",
                ),
                JsonObject.Output("MERGE_OBJECT_4",
                    tooltip="Passthrough of merge_object_4, for connecting to other nodes.",
                ),
                JsonObject.Output("MERGE_OBJECT_5",
                    tooltip="Passthrough of merge_object_5, for connecting to other nodes.",
                ),
                JsonObject.Output("MERGE_OBJECT_6",
                    tooltip="Passthrough of merge_object_6, for connecting to other nodes.",
                ),
            ],
        )

    @classmethod
    def execute(
        cls,
        json_object=None,
        merge_object_1=None,
        merge_object_2=None,
        merge_object_3=None,
        merge_object_4=None,
        merge_object_5=None,
        merge_object_6=None,
        deep_merge=False,
    ):
        obj = copy.deepcopy(_coerce_json_object(json_object) or {})
        m1 = _coerce_json_object(merge_object_1)
        m2 = _coerce_json_object(merge_object_2)
        m3 = _coerce_json_object(merge_object_3)
        m4 = _coerce_json_object(merge_object_4)
        m5 = _coerce_json_object(merge_object_5)
        m6 = _coerce_json_object(merge_object_6)
        for source in (m1, m2, m3, m4, m5, m6):
            if source is not None:
                if deep_merge:
                    _deep_merge(obj, copy.deepcopy(source))
                else:
                    obj.update(copy.deepcopy(source))
        return io.NodeOutput(obj, m1, m2, m3, m4, m5, m6)


class JsonGetStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetString",
            display_name="JSON Get String",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the value from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the value. Use dots (e.g. 'address.city') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.Boolean.Input("error_on_empty", default=False,
                    tooltip="Raise an error if the resolved value is an empty string (or the key does not exist).",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
                io.Int.Input("precision", default=0, min=0, max=10,
                    tooltip="When converting float values, number of decimal places. 0 = whole number.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                io.String.Output("VALUE",
                    tooltip="The resolved value as a string.",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.Boolean.Output("ERROR_ON_EMPTY",
                    tooltip="Passthrough of the error_on_empty setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
                io.Int.Output("PRECISION",
                    tooltip="Passthrough of the precision setting.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_on_empty, error_message, precision):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        result = _coerce_to_string(raw, precision)

        if error_on_empty and result == "":
            _raise_getter_error(key, "value is empty", error_message)

        return io.NodeOutput(json_object, result, error_on_missing, error_on_empty, error_message, precision)


class JsonGetIntNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetInt",
            display_name="JSON Get Int",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the value from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the value. Use dots (e.g. 'address.city') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.Boolean.Input("error_on_zero", default=False,
                    tooltip="Raise an error if the resolved value is 0.",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                io.Int.Output("VALUE",
                    tooltip="The resolved value as an integer.",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.Boolean.Output("ERROR_ON_ZERO",
                    tooltip="Passthrough of the error_on_zero setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_on_zero, error_message):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        result = _coerce_to_int(raw)

        if error_on_zero and result == 0:
            _raise_getter_error(key, "value is zero", error_message)

        return io.NodeOutput(json_object, result, error_on_missing, error_on_zero, error_message)


class JsonGetFloatNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetFloat",
            display_name="JSON Get Float",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the value from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the value. Use dots (e.g. 'address.city') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.Boolean.Input("error_on_zero", default=False,
                    tooltip="Raise an error if the resolved value is 0.0.",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
                io.Int.Input("precision", default=0, min=0, max=10,
                    tooltip="Number of decimal places to round to. 0 = no rounding (full precision).",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                io.Float.Output("VALUE",
                    tooltip="The resolved value as a float.",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.Boolean.Output("ERROR_ON_ZERO",
                    tooltip="Passthrough of the error_on_zero setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
                io.Int.Output("PRECISION",
                    tooltip="Passthrough of the precision setting.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_on_zero, error_message, precision):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        result = _coerce_to_float(raw, precision)

        if error_on_zero and result == 0.0:
            _raise_getter_error(key, "value is zero", error_message)

        return io.NodeOutput(json_object, result, error_on_missing, error_on_zero, error_message, precision)


class JsonGetBoolNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetBool",
            display_name="JSON Get Bool",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the value from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the value. Use dots (e.g. 'address.city') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                io.Boolean.Output("VALUE",
                    tooltip="The resolved value as a boolean.",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_message):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        result = _coerce_to_bool(raw)

        return io.NodeOutput(json_object, result, error_on_missing, error_message)


class JsonGetObjectNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonGetObject",
            display_name="JSON Get Object",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to read the nested object from.",
                ),
                io.String.Input("key", default="key",
                    tooltip="Path to the nested object. Use dots (e.g. 'address') for nested structures.",
                ),
                io.Boolean.Input("error_on_missing", default=False,
                    tooltip="Raise an error if the key does not exist in the JSON object.",
                ),
                io.Boolean.Input("error_on_empty", default=False,
                    tooltip="Raise an error if the resolved object is empty ({}) or the key does not exist.",
                ),
                io.String.Input("error_message", default="",
                    tooltip="Custom error message. Leave empty to use the default message that includes the key path.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object.",
                ),
                JsonObject.Output("VALUE",
                    tooltip="The extracted nested object (deep-copied for fork-safety).",
                ),
                io.Boolean.Output("ERROR_ON_MISSING",
                    tooltip="Passthrough of the error_on_missing setting.",
                ),
                io.Boolean.Output("ERROR_ON_EMPTY",
                    tooltip="Passthrough of the error_on_empty setting.",
                ),
                io.String.Output("ERROR_MESSAGE",
                    tooltip="Passthrough of the custom error message.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object, key, error_on_missing, error_on_empty, error_message):
        key = _sanitize_key(key)
        json_object = _coerce_json_object(json_object) or {}
        raw = _get_nested_value(json_object, key)

        if raw is _MISSING and error_on_missing:
            _raise_getter_error(key, "value not found", error_message)

        if isinstance(raw, dict):
            result = copy.deepcopy(raw)
        else:
            result = {}

        if error_on_empty and result == {}:
            _raise_getter_error(key, "value is empty", error_message)

        return io.NodeOutput(json_object, result, error_on_missing, error_on_empty, error_message)


class JsonToStringNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_JsonToString",
            display_name="JSON to String",
            category="json",
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to convert to a string.",
                ),
            ],
            outputs=[
                JsonObject.Output("JSON_OBJECT",
                    tooltip="Passthrough of the input JSON object, for connecting to other nodes.",
                ),
                io.String.Output("STRING",
                    tooltip="The JSON data as a formatted, readable string.",
                ),
            ],
        )

    @classmethod
    def execute(cls, json_object):
        json_object = _coerce_json_object(json_object) or {}
        serialized = json.dumps(json_object, indent=2, ensure_ascii=False)
        return io.NodeOutput(json_object, serialized)



class LoadJsonNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        file_list = _list_json_files()
        # Provide a placeholder when no files exist so the combo is never empty
        if not file_list:
            file_list = [""]
        return io.Schema(
            node_id="Mistralys_LoadJson",
            display_name="JSON Load File",
            category="json",
            inputs=[
                io.Combo.Input(
                    "filename",
                    options=file_list,
                    tooltip="Select a .json file from ComfyUI's input directory.",
                ),
            ],
            outputs=[
                JsonObject.Output(
                    "JSON_OBJECT",
                    tooltip="The parsed JSON data as a JSON object.",
                ),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, filename):
        """Return the file's mtime so ComfyUI re-executes when content changes."""
        try:
            real_path = _guard_input_path(filename)
        except ValueError:
            return ""
        try:
            return str(os.path.getmtime(real_path))
        except OSError:
            return ""

    @classmethod
    def execute(cls, filename):
        # --- Path validation (includes empty-filename guard) ---
        candidate = _guard_input_path(filename)

        # --- File-size guard ---
        try:
            file_size = os.path.getsize(candidate)
        except OSError as exc:
            raise ValueError(f"Cannot access JSON file {filename!r}: {exc}") from exc
        if file_size > _MAX_JSON_FILE_SIZE:
            raise ValueError(
                f"JSON file {filename!r} is {file_size:,} bytes, which exceeds the "
                f"{_MAX_JSON_FILE_SIZE:,}-byte limit."
            )

        # --- Read and parse ---
        try:
            with open(candidate, 'r', encoding='utf-8') as fh:
                raw = fh.read()
        except OSError as exc:
            raise ValueError(f"Cannot read JSON file {filename!r}: {exc}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed JSON in file {filename!r}: {exc}"
            ) from exc

        # --- Validate top-level type ---
        if not isinstance(data, dict):
            raise ValueError(
                f"JSON file {filename!r} must contain a top-level object (dict), "
                f"but got {type(data).__name__}."
            )

        return io.NodeOutput(data)


class SaveJsonNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="Mistralys_SaveJson",
            display_name="JSON Save File",
            category="json",
            is_output_node=True,
            not_idempotent=True,
            inputs=[
                JsonObject.Input("json_object",
                    tooltip="The JSON object to save to a file.",
                ),
                io.String.Input("filename", default="output",
                    tooltip="Base filename without the .json extension.",
                ),
                io.String.Input("subfolder", default="",
                    tooltip="Subdirectory inside the output folder. Created automatically if needed.",
                ),
                io.Int.Input("counter_length", default=5, min=0, max=10,
                    tooltip="Number of digits for the auto-incrementing file counter (e.g. 5 produces _00001). Set to 0 to overwrite the file each run.",
                ),
            ],
            outputs=[],
        )

    @classmethod
    def fingerprint_inputs(cls, json_object, filename, subfolder, counter_length):
        # Return a unique value each run to force re-execution.
        # SaveJsonNode writes files, so it must never use cached results.
        import time
        return time.time()

    @classmethod
    def execute(cls, json_object, filename, subfolder, counter_length):
        json_object = _coerce_json_object(json_object) or {}
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
