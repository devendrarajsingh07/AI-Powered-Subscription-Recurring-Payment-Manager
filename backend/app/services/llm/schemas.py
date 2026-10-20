"""Conservative Gemini JSON Schema subset; strict server models remain authoritative.

Inline local $defs references and translate nullable anyOf into type arrays. Discard annotation
and validation keywords unsupported by this adapter. Do not weaken the original Pydantic schema.
See https://ai.google.dev/gemini-api/docs/structured-output#json_schema_support .
"""

from copy import deepcopy

KEYWORDS = {
    "type",
    "description",
    "enum",
    "format",
    "properties",
    "required",
    "items",
    "additionalProperties",
    "minimum",
    "maximum",
    "minItems",
    "maxItems",
}


def provider_schema(schema):
    source = deepcopy(schema)

    def convert(node, depth=0):
        if depth > 12 or not isinstance(node, dict):
            raise ValueError("Unsupported provider schema")
        if "$ref" in node:
            reference = node["$ref"]
            if not reference.startswith("#/$defs/"):
                raise ValueError("Only local provider schema references are supported")
            return convert(source["$defs"][reference.removeprefix("#/$defs/")], depth + 1)
        if "anyOf" in node:
            options = node["anyOf"]
            real = [option for option in options if option.get("type") != "null"]
            if len(real) != 1 or len(options) != 2:
                raise ValueError("Only nullable provider schema unions are supported")
            result = convert(real[0], depth + 1)
            result["type"] = [result["type"], "null"]
            return result
        result = {}
        for key, value in node.items():
            if key not in KEYWORDS:
                continue
            if key == "properties":
                result[key] = {name: convert(item, depth + 1) for name, item in value.items()}
            elif key == "items" or key == "additionalProperties" and isinstance(value, dict):
                result[key] = convert(value, depth + 1)
            else:
                result[key] = deepcopy(value)
        return result

    return convert(source)
