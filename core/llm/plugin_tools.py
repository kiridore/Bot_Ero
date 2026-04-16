from __future__ import annotations

from typing import Any, Iterable, TYPE_CHECKING, Type, Union

from core.llm.llm import ToolSpec

if TYPE_CHECKING:  # pragma: no cover
    from core.base import Plugin


DEFAULT_PLUGIN_TOOL_PARAMETERS: dict[str, Any] = {
    # 通用占位：当前插件 function call 的“参数契约”还未细化。
    # 使用 additionalProperties 允许模型在后续扩展时仍能传入未知字段。
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": True,
}


def plugin_class_to_tool_spec(
    plugin_cls: Type[Any],
    *,
    parameters: dict[str, Any] | None = None,
) -> ToolSpec:
    """将插件“类”转换为 LLM ToolSpec。

    说明：
    - 只读取类属性，不会实例化插件（避免触发插件的依赖初始化）。
    - name/description 需要已在插件类上定义。
    """

    tool_name = getattr(plugin_cls, "name", None)
    tool_desc = getattr(plugin_cls, "description", None)
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError(f"{plugin_cls.__name__} missing non-empty class attribute `name`")
    if not isinstance(tool_desc, str) or not tool_desc.strip():
        raise ValueError(f"{plugin_cls.__name__} missing non-empty class attribute `description`")

    return ToolSpec(
        name=tool_name,
        description=tool_desc,
        parameters=dict(parameters or DEFAULT_PLUGIN_TOOL_PARAMETERS),
    )


def plugin_to_tool_spec(
    plugin: Union[Any, Type[Any]],
    *,
    parameters: dict[str, Any] | None = None,
) -> ToolSpec:
    """将插件（类或实例）转换为 LLM ToolSpec。"""

    if isinstance(plugin, type):
        return plugin_class_to_tool_spec(plugin, parameters=parameters)

    tool_name = getattr(plugin, "name", None)
    tool_desc = getattr(plugin, "description", None)
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise ValueError(f"{type(plugin).__name__} missing non-empty attribute `name`")
    if not isinstance(tool_desc, str) or not tool_desc.strip():
        raise ValueError(f"{type(plugin).__name__} missing non-empty attribute `description`")

    return ToolSpec(
        name=tool_name,
        description=tool_desc,
        parameters=dict(parameters or DEFAULT_PLUGIN_TOOL_PARAMETERS),
    )


def plugins_to_tool_specs(
    plugins: Iterable[Union[Any, Type[Any]]],
    *,
    parameters: dict[str, Any] | None = None,
    dedupe_by_name: bool = True,
) -> list[ToolSpec]:
    """将多个插件转换为 ToolSpec 列表。"""

    seen: set[str] = set()
    specs: list[ToolSpec] = []
    for p in plugins:
        spec = plugin_to_tool_spec(p, parameters=parameters)
        if dedupe_by_name:
            if spec.name in seen:
                continue
            seen.add(spec.name)
        specs.append(spec)
    return specs

