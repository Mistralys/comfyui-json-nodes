# Project: JSON Getter Nodes

## Description

I just realized that with the JSON objects that I previously only meant to use for metadata collection and saving to disk to archive alongside generated images, I actually have a working data storage that can be used by the workflow.

## The Idea

In addition to the existing nodes used to write data into the JSON objects, we will add a series of getter nodes that can be used to access the stored data.

## The Nodes

### JSON Get String

Gets a stored value as a string, converting as necessary.

- Input: `json-object` - JSON Object to get the value from (Mandatory).
- Input: `string` - Key: Path to the value (dot notation supported).
- Input: `bool` - Error on missing: Whether to register an error if the value does not exist.
- Input: `bool` - Error on empty: Whether to register an error if the value is empty (or does not exist).
- Input: `string` - Error message: Custom error message. Leave empty to use the default message.
- Input: `int` - Precision: When converting float values, how many decimals to round to (`0` = whole number).
- Output: `json-object` - JSON Object (passthrough).
- Output: `string` - Value.
- Output: `bool` - Error on missing (passthrough).
- Output: `bool` - Error on empty (passthrough).
- Output: `string` - Error message (passthrough).
- Output: `int` - Precision (passthrough).

### JSON Get Int

Gets a stored value as an integer, converting as necessary.

- Input: `json-object` - JSON Object to get the value from (Mandatory).
- Input: `string` - Key: Path to the value (dot notation supported).
- Input: `bool` - Error on missing: Whether to register an error if the value does not exist.
- Input: `bool` - Error on zero: Whether to register an error if the resolved value is `0`.
- Input: `string` - Error message: Custom error message. Leave empty to use the default message.
- Output: `json-object` - JSON Object (passthrough).
- Output: `int` - Value.
- Output: `bool` - Error on missing (passthrough).
- Output: `bool` - Error on zero (passthrough).
- Output: `string` - Error message (passthrough).

### JSON Get Float

Gets a stored value as a float, converting as necessary.

- Input: `json-object` - JSON Object to get the value from (Mandatory).
- Input: `string` - Key: Path to the value (dot notation supported).
- Input: `bool` - Error on missing: Whether to register an error if the value does not exist.
- Input: `bool` - Error on zero: Whether to register an error if the resolved value is `0.0`.
- Input: `string` - Error message: Custom error message. Leave empty to use the default message.
- Input: `int` - Precision: Number of decimal places to round the output to (`0` = no rounding).
- Output: `json-object` - JSON Object (passthrough).
- Output: `float` - Value.
- Output: `bool` - Error on missing (passthrough).
- Output: `bool` - Error on zero (passthrough).
- Output: `string` - Error message (passthrough).
- Output: `int` - Precision (passthrough).

### JSON Get Bool

Gets a stored value as a boolean, converting as necessary.

- Input: `json-object` - JSON Object to get the value from (Mandatory).
- Input: `string` - Key: Path to the value (dot notation supported).
- Input: `bool` - Error on missing: Whether to register an error if the value does not exist.
- Input: `string` - Error message: Custom error message. Leave empty to use the default message.
- Output: `json-object` - JSON Object (passthrough).
- Output: `bool` - Value.
- Output: `bool` - Error on missing (passthrough).
- Output: `string` - Error message (passthrough).

### JSON Get Object

Gets a stored nested object.

- Input: `json-object` - JSON Object to get the value from (Mandatory).
- Input: `string` - Key: Path to the value (dot notation supported).
- Input: `bool` - Error on missing: Whether to register an error if the value does not exist.
- Input: `bool` - Error on empty: Whether to register an error if the resolved object is empty (`{}`).
- Input: `string` - Error message: Custom error message. Leave empty to use the default message.
- Output: `json-object` - JSON Object (passthrough).
- Output: `json-object` - Value.
- Output: `bool` - Error on missing (passthrough).
- Output: `bool` - Error on empty (passthrough).
- Output: `string` - Error message (passthrough).

## Path Notation

Just like when storing values, using the path notation allows accessing nested values, e.g. `address.city`.

## Tacit Type Conversion

The philosophy here is to make all stored values accessible organically without having to convert them manually. This means the following:

- String -> Int/Float: Convert if the string value is numeric, `0` otherwise.
- String -> Bool: True if string equals `1` or `true` or `yes`, false otherwise (case insensitive).
- String -> Object: Unsupported, returns an empty object.
- Int/Float -> String: Straightforward.
- Int -> Bool: `false` if number equals `0`, `true` otherwise.
- Int -> Float: Straightforward.
- Float -> Int: Round to integer.
- Float -> Bool: Round to integer, then same as Int -> Bool.
- Bool -> String: `true`|`false`.
- Bool -> Int: `1`|`0`.
- Bool -> Float: `1.0`|`0.0` (even if this does not make much sense).
- Null/Missing -> String: Empty string.
- Null/Missing -> Int/Float: `0`
- Null/Missing -> Object: Empty object.
- Null/Missing -> Bool: `false`.
- Array: Treat as Null/Missing (currently not supported).
- Object -> String: Serialize the JSON.
- Object -> Any other type: Treat as Null/Missing.
