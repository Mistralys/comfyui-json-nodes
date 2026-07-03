# Research Report: Node Idempotency & Caching Behavior

## Problem Statement

JSON nodes in the workflow appear to trigger image re-generation even when nothing in the workflow has been modified. This report investigates whether the nodes could be the cause and whether their caching configuration is correct.

## Problem Decomposition

1. How does ComfyUI's caching mechanism determine whether to re-execute a node?
2. Does the `not_idempotent=True` flag on `SaveJsonNode` actually prevent caching (as intended)?
3. Could the custom `JSON_OBJECT` type interfere with cache key computation?
4. Can adding output nodes (like `SaveJsonNode`) cause upstream image generation nodes to re-execute?
5. Are any of the 13 JSON nodes misconfigured in a way that breaks caching?

## Context & Constraints

- ComfyUI V3 API (`comfy_api.latest`), no V1 fallback
- 13 nodes total: 4 primitive setters, 1 object setter, 1 merge, 5 getters, 1 to-string, 1 save
- Only `SaveJsonNode` has `is_output_node=True` and `not_idempotent=True`
- No node defines `fingerprint_inputs` (V3) or `IS_CHANGED` (V1)
- Custom connection type: `io.Custom("JSON_OBJECT")` — passes Python `dict` values

## Prior Art & Known Patterns

### Pattern 1: ComfyUI Input-Signature Caching (`CacheKeySetInputSignature`)

- **Description:** ComfyUI's default caching (for the `outputs` cache) computes a cache key from the **prompt data** — the graph topology and widget values — NOT from runtime output values. For each node, the cache key includes:
  1. `class_type` (the node class name)
  2. `is_changed` result (from `fingerprint_inputs` or `IS_CHANGED`; defaults to `False` if neither is defined)
  3. `node_id` (only if `NOT_IDEMPOTENT=True` or `UNIQUE_ID` is in hidden inputs)
  4. Input structure: linked inputs recorded as `("ANCESTOR", ancestor_index, socket)`, constant/widget values recorded as-is
  5. The signatures of ALL ancestor nodes (recursively)
- **Where used:** Core ComfyUI execution engine (`comfy_execution/caching.py`, `execution.py`)
- **Strengths:** Graph-structure-based caching is deterministic and efficient — identical prompts produce identical cache keys regardless of runtime values
- **Weaknesses:** Custom types flowing through connections are invisible to the cache key; caching correctness depends entirely on `fingerprint_inputs`/`IS_CHANGED` being implemented for non-deterministic nodes
- **Fit:** Directly relevant — this is the mechanism that determines whether any node re-executes

### Pattern 2: `to_hashable()` — Cache Key Serialization

- **Description:** ComfyUI converts cache signatures into hashable values using `to_hashable()` (in `comfy_execution/caching.py`). This function handles:
  - Primitives (`int`, `float`, `str`, `bool`, `bytes`, `None`) → returned as-is
  - `Mapping` (dict) → `frozenset` of sorted key-value pairs (recursively hashable)
  - `Sequence` (list, tuple) → `frozenset` of indexed pairs
  - Everything else → `Unhashable()` (contains `float("NaN")`, which guarantees `NaN != NaN`, so cache NEVER matches)
- **Where used:** Cache key computation in `CacheKeySetInputSignature`
- **Strengths:** Handles all JSON-compatible types correctly
- **Weaknesses:** Types like `torch.Tensor` become `Unhashable`, meaning nodes outputting tensors would never cache if their outputs were part of the key — but they're NOT (the key uses graph topology, not runtime values)
- **Fit:** The `JSON_OBJECT` custom type passes Python `dict` values, which `to_hashable()` handles correctly via the `Mapping` branch. **Custom types do NOT affect cache keys** because the cache key records links as `("ANCESTOR", index, socket)`, not actual values.

### Pattern 3: `NOT_IDEMPOTENT` Flag

- **Description:** The V3 Schema docstring states: *"Flags a node as not idempotent; when True, the node will run and not reuse the cached outputs when identical inputs are provided on a **different node** in the graph."* In the caching code, `NOT_IDEMPOTENT` adds `node_id` to the cache signature, making each node instance's cache entry unique — preventing cache SHARING between same-type nodes with identical inputs.
- **Where used:** `CacheKeySetInputSignature.get_immediate_node_signature()` in `comfy_execution/caching.py`
- **Strengths:** Correctly prevents cache collision when two nodes of the same type with identical inputs should produce different side effects
- **Weaknesses:** Does NOT prevent a node from reusing its OWN cached output on subsequent runs. The `node_id` is constant between runs, so the cache key is stable.
- **Fit:** **Critical finding.** The lifecycle skill documentation states `not_idempotent=True` "prevents all caching" — this is incorrect. It only prevents cache sharing between node instances. To truly force re-execution every run, a node MUST implement `fingerprint_inputs` (V3) or `IS_CHANGED` (V1) that returns a different value each time.

### Pattern 4: `fingerprint_inputs` / `IS_CHANGED`

- **Description:** The `IsChangedCache` in `execution.py` checks whether a node class has `fingerprint_inputs` (V3) or `IS_CHANGED` (V1). If defined, the method is called with the same arguments as `execute()`, and its return value is compared to the previous run. A different return value causes re-execution. If neither is defined, the `is_changed` field in the cache signature is set to `False` (a constant), meaning the node is considered unchanged.
- **Where used:** `IsChangedCache.get()` in `execution.py`
- **Strengths:** Provides explicit control over cache invalidation for non-deterministic nodes (e.g., random values, file watchers, timestamp-dependent operations)
- **Weaknesses:** Must be explicitly implemented — no automatic inference from `is_output_node` or `not_idempotent`
- **Fit:** **SaveJsonNode is missing this.** Without `fingerprint_inputs`, it will be cached after first execution and never write to disk again (until a widget value or connection changes). This is a genuine bug, though it is a separate issue from the user's reported image regeneration problem.

### Pattern 5: Output Node Dependency Chains

- **Description:** ComfyUI identifies output nodes (`is_output_node=True`) and traces backward to build dependency chains. Each output node creates an independent chain. Nodes shared between chains are evaluated once and cached. Adding a new output node (like `SaveJsonNode`) creates an additional chain but does NOT force re-evaluation of nodes in other chains.
- **Where used:** `ExecutionList.add_node()` in `comfy_execution/graph.py`, `execute_async()` in `execution.py`
- **Strengths:** Multiple output nodes can share upstream nodes without redundant computation
- **Weaknesses:** None relevant to this investigation
- **Fit:** Adding `SaveJsonNode` to a workflow creates a new dependency chain. Shared upstream nodes (e.g., text encoders, model loaders) are cached independently. **This should NOT cause image regeneration.**

## Comparative Evaluation

| Criterion | `not_idempotent=True` alone | `fingerprint_inputs` (return changing value) | Both combined |
|---|---|---|---|
| **Prevents cache sharing between instances** | Yes | No | Yes |
| **Forces re-execution every run** | **No** | Yes | Yes |
| **Affects upstream node caching** | No | No | No |
| **Could cause image regeneration** | No | No | No |
| **Correct for SaveJsonNode** | Insufficient | Necessary | Ideal |

## Current State of All 13 Nodes

| Node | `not_idempotent` | `is_output_node` | `fingerprint_inputs` | Caching behavior |
|---|---|---|---|---|
| JsonStringNode | No | No | No | Default (cached when inputs unchanged) ✅ |
| JsonIntNode | No | No | No | Default ✅ |
| JsonFloatNode | No | No | No | Default ✅ |
| JsonBooleanNode | No | No | No | Default ✅ |
| JsonObjectNode | No | No | No | Default ✅ |
| JsonMergeObjectsNode | No | No | No | Default ✅ |
| JsonGetStringNode | No | No | No | Default ✅ |
| JsonGetIntNode | No | No | No | Default ✅ |
| JsonGetFloatNode | No | No | No | Default ✅ |
| JsonGetBoolNode | No | No | No | Default ✅ |
| JsonGetObjectNode | No | No | No | Default ✅ |
| JsonToStringNode | No | No | No | Default ✅ |
| SaveJsonNode | **Yes** | **Yes** | **No** | ⚠️ Cached after first run — **bug** |

## Recommendation

### 1. The JSON nodes are NOT causing image regeneration

Based on analysis of ComfyUI's caching mechanism:

- **Cache keys are computed from graph topology and widget values**, not from runtime data flowing through custom types like `JSON_OBJECT`. Adding JSON nodes to a workflow does not change the cache keys of image generation nodes.
- **Adding `SaveJsonNode` as an output node** creates an independent dependency chain. Shared upstream nodes are cached and not re-evaluated.
- **None of the 12 non-save nodes have any caching directives** that could interfere with upstream caching. They use default behavior (cached when inputs unchanged), which is correct for deterministic, pure-function nodes.

### 2. Likely causes of image regeneration to investigate

The image regeneration is most likely caused by something else in the workflow:

- **Auto-incrementing seed**: A `KSampler` with `control_after_generate` set to `randomize` or `increment` will produce a new seed each run, changing its cache key and forcing re-execution of itself and all downstream nodes. This is normal ComfyUI behavior.
- **`IS_CHANGED` on upstream nodes**: Nodes like `LoadImage` have `IS_CHANGED` methods that check file modification timestamps. If the source file is modified between runs, these nodes invalidate their cache.
- **Cache eviction**: Under RAM pressure or with LRU caching, older cache entries may be evicted, causing re-execution.

### 3. SaveJsonNode has a genuine caching bug (separate issue)

`not_idempotent=True` does **not** prevent a node from reusing its own cached output. The flag's actual behavior (per the V3 API docstring) is: *"the node will run and not reuse the cached outputs when identical inputs are provided on a **different node** in the graph."*

Without `fingerprint_inputs`, SaveJsonNode will be cached after its first execution and will NOT write to disk on subsequent runs (until a widget value or connection changes). This is almost certainly unintended for a file-writing node.

**Fix:** Add `fingerprint_inputs` to `SaveJsonNode`:

```python
@classmethod
def fingerprint_inputs(cls, **kwargs):
    # Return a unique value each run to force re-execution.
    # SaveJsonNode writes files, so it must never use cached results.
    import time
    return time.time()
```

This matches the pattern used by ComfyUI's built-in `websocket_image_save.py`:
```python
@classmethod
def IS_CHANGED(s, images):
    return time.time()
```

### 4. Lifecycle skill documentation should be corrected

The `comfyui-node-lifecycle` skill states that `not_idempotent=True` "prevents all caching." This is inaccurate. It prevents cache **sharing** between instances, not caching itself. The skill should be updated to reflect the actual behavior and recommend `fingerprint_inputs` for nodes that must always re-execute.

## Open Questions

- **Workflow specifics**: Without seeing the exact workflow, we cannot definitively rule out a topology-specific interaction. If the user can confirm whether images regenerate with only the setter/getter nodes (no SaveJsonNode), that would isolate whether SaveJsonNode's output-node status plays any role.
- **ComfyUI version**: The caching behavior analyzed here is from the current `master` branch of `Comfy-Org/ComfyUI`. Older versions may behave differently.
- **Cache type**: The analysis assumes the default `CacheKeySetInputSignature` caching. Users with `--cache-none` or custom cache configurations may see different behavior.

## References

- ComfyUI caching implementation: [`comfy_execution/caching.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_execution/caching.py) — `CacheKeySetInputSignature`, `to_hashable()`, `Unhashable`
- ComfyUI execution engine: [`execution.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/execution.py) — `IsChangedCache`, `execute()`, `execute_async()`
- ComfyUI graph traversal: [`comfy_execution/graph.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_execution/graph.py) — `ExecutionList`, `TopologicalSort`
- V3 API Schema definition: [`comfy_api/latest/_io.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy_api/latest/_io.py) — `Schema.not_idempotent` docstring, `NOT_IDEMPOTENT` class property
- V3 `NOT_IDEMPOTENT` docstring: *"Flags a node as not idempotent; when True, the node will run and not reuse the cached outputs when identical inputs are provided on a different node in the graph."*
- Built-in IS_CHANGED example: [`custom_nodes/websocket_image_save.py`](https://github.com/Comfy-Org/ComfyUI/blob/master/custom_nodes/websocket_image_save.py) — `IS_CHANGED` returning `time.time()`
