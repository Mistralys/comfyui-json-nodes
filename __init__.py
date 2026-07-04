"""Extension registration for ComfyUI JSON Nodes."""

from typing_extensions import override
from comfy_api.latest import ComfyExtension, io

from .nodes import (
    JsonStringNode,
    JsonIntNode,
    JsonFloatNode,
    JsonBooleanNode,
    JsonObjectNode,
    JsonMergeObjectsNode,
    JsonRerouteNode,
    JsonGetStringNode,
    JsonGetIntNode,
    JsonGetFloatNode,
    JsonGetBoolNode,
    JsonGetObjectNode,
    JsonToStringNode,
    LoadJsonNode,
    SaveJsonNode,
)


class JsonNodesExtension(ComfyExtension):
    @override
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            JsonStringNode,
            JsonIntNode,
            JsonFloatNode,
            JsonBooleanNode,
            JsonObjectNode,
            JsonMergeObjectsNode,
            JsonRerouteNode,
            JsonGetStringNode,
            JsonGetIntNode,
            JsonGetFloatNode,
            JsonGetBoolNode,
            JsonGetObjectNode,
            JsonToStringNode,
            LoadJsonNode,
            SaveJsonNode,
        ]


async def comfy_entrypoint() -> JsonNodesExtension:
    return JsonNodesExtension()
