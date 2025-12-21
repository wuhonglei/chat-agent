"""组件工具相关的工具函数"""
from typing import Any


def resolve_ref(schema: dict, ref_path: str, definitions: dict) -> dict:
    """
    解析 JSON Schema 中的 $ref 引用

    Args:
        schema: 包含 $ref 的 schema 对象
        ref_path: $ref 路径，例如 "#/definitions/WeatherNowData"
        definitions: definitions 字典，包含所有定义

    Returns:
        解析后的 schema 对象（展开引用）
    """
    if not ref_path.startswith("#/definitions/"):
        # 只支持 #/definitions/ 格式的引用
        return schema

    ref_name = ref_path.replace("#/definitions/", "")
    if ref_name not in definitions:
        # 引用不存在，返回原始 schema
        return schema

    # 获取引用的定义
    ref_definition = definitions[ref_name]

    # 递归处理引用定义中的 $ref
    if isinstance(ref_definition, dict):
        if "$ref" in ref_definition:
            return resolve_ref(ref_definition, ref_definition["$ref"], definitions)
        # 处理嵌套的 properties 中的 $ref
        if "properties" in ref_definition:
            resolved_properties = {}
            for prop_name, prop_schema in ref_definition["properties"].items():
                if isinstance(prop_schema, dict) and "$ref" in prop_schema:
                    resolved_properties[prop_name] = resolve_ref(
                        prop_schema, prop_schema["$ref"], definitions
                    )
                else:
                    resolved_properties[prop_name] = prop_schema
            ref_definition = {**ref_definition,
                              "properties": resolved_properties}

    return ref_definition


def expand_schema_refs(schema: dict) -> dict:
    """
    展开 JSON Schema 中的所有 $ref 引用

    Args:
        schema: 包含 $ref 引用的 JSON Schema

    Returns:
        展开所有引用后的 JSON Schema
    """
    if not isinstance(schema, dict):
        return schema

    # 获取 definitions
    definitions = schema.get("definitions", {})

    # 递归处理 schema
    def _expand(obj: Any) -> Any:
        if isinstance(obj, dict):
            if "$ref" in obj:
                # 展开引用
                return resolve_ref(obj, obj["$ref"], definitions)
            else:
                # 递归处理字典中的每个值
                return {k: _expand(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            # 递归处理列表中的每个元素
            return [_expand(item) for item in obj]
        else:
            return obj

    expanded = _expand(schema)

    # 移除 definitions（已展开，不再需要）
    if isinstance(expanded, dict) and "definitions" in expanded:
        expanded = {k: v for k, v in expanded.items() if k != "definitions"}

    return expanded


def convert_schema_to_tool_definition(
    component_tool_name: str,
    json_schema: dict,
) -> dict:
    """
    将 JSON Schema 转换为 LLM 可用的 tool 定义格式

    Args:
        component_tool_name: 组件工具名称，例如 'weather'
        json_schema: 组件的 JSON Schema 字典

    Returns:
        LLM tool 定义字典，格式如下：
        {
            "type": "function",
            "function": {
                "name": "component_{component_tool_name}",
                "description": "生成 {component_tool_name} 组件的 props 数据",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "组件类型名称",
                            "enum": ["{component_tool_name}"]
                        },
                        "data": {
                            # 从 JSON schema 转换而来
                            "type": "object",
                            "properties": {...},
                            "required": [...]
                        }
                    },
                    "required": ["type", "data"]
                }
            }
        }
    """
    # 展开所有 $ref 引用
    expanded_schema = expand_schema_refs(json_schema)

    # 提取 properties 和 required
    schema_properties = expanded_schema.get("properties", {})
    schema_required = expanded_schema.get("required", [])

    # 构建 tool 定义
    tool_definition = {
        "type": "function",
        "function": {
            "name": f"component_{component_tool_name}",
            "description": f"生成 {component_tool_name} 组件的 props 数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "组件类型名称",
                        "enum": [component_tool_name],
                    },
                    "data": {
                        "type": "object",
                        "properties": schema_properties,
                        "required": schema_required,
                    },
                },
                "required": ["type", "data"],
            },
        },
    }

    return tool_definition
