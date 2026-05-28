"""BotEro MCP 服务：将闹钟与打卡能力暴露为 LLM Agent 工具。"""

from __future__ import annotations

from botero_mcp._bootstrap import bootstrap, configure_database

bootstrap()
configure_database()

from typing import Any, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from botero_mcp import services
from botero_mcp.context import resolve_user_id

mcp = FastMCP(
    "BotEro",
    instructions=(
        "BotEro 机器人能力工具集（v1：闹钟与打卡查询）。"
        "操作某一用户数据时需传入 user_id（QQ 号），"
        "或在服务端设置环境变量 BOTERO_MCP_DEFAULT_USER_ID。"
        "数据库路径由 BOTERO_DB_PATH 指定，默认为项目根目录 data.db。"
    ),
)


class AlarmCreatePayload(BaseModel):
    """与网页端闹钟表单一致的结构化参数。"""

    content: str = Field(description="提醒正文，不可为空")
    schedule_type: Literal[
        "once_date",
        "once_relative",
        "once_today",
        "daily",
        "interval_days",
        "weekly",
        "monthly",
        "yearly",
    ] = Field(description="触发方式")
    time: str | None = Field(default=None, description="时刻 HH:MM，部分类型必填")
    date: str | None = Field(default=None, description="once_date 时的 YYYY-MM-DD")
    years: int = Field(default=0, description="once_relative：年")
    months: int = Field(default=0, description="once_relative：月")
    days: int = Field(default=0, description="once_relative：日")
    hours: int = Field(default=0, description="once_relative：小时")
    minutes: int = Field(default=0, description="once_relative：分钟")
    interval_days: int = Field(default=1, description="interval_days：每隔 N 天")
    weekday: int | None = Field(default=None, description="weekly：1=周一 … 7=周日")
    day: int | None = Field(default=None, description="monthly/yearly 的日")
    month: int | None = Field(default=None, description="yearly 的月")


def _uid(user_id: str | None) -> str:
    return resolve_user_id(user_id)


@mcp.tool
def list_pending_alarms(user_id: str | None = None) -> str:
    """列出指定用户尚未触发的私聊闹钟（与 /闹钟 一览 相同数据源）。

    Args:
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
    """
    return services.alarm_list(_uid(user_id))


@mcp.tool
def create_alarm_from_text(
    schedule_text: str,
    user_id: str | None = None,
) -> str:
    """用自然语言创建闹钟（与群聊 /闹钟 正文解析规则一致）。

    示例：「明天 8:00 喝水」「每天 9:00 打卡」「3小时后开会」「2026-06-01 10:00 交报告」。

    Args:
        schedule_text: 时间与内容描述（不含 /闹钟 前缀）。
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
    """
    return services.alarm_create_from_text(_uid(user_id), schedule_text)


@mcp.tool
def create_alarm_structured(
    payload: AlarmCreatePayload,
    user_id: str | None = None,
) -> str:
    """用结构化表单创建私聊闹钟（与打卡图库网页端一致）。

    schedule_type 取值：once_date | once_relative | once_today | daily |
    interval_days | weekly | monthly | yearly。须距当前至少 5 分钟。

    Args:
        payload: 闹钟表单字段。
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
    """
    body: dict[str, Any] = payload.model_dump(exclude_none=True)
    return services.alarm_create_structured(_uid(user_id), body)


@mcp.tool
def cancel_pending_alarm(
    alarm_id: int,
    user_id: str | None = None,
) -> str:
    """取消本人未触发的闹钟（与 /闹钟 取消 <编号> 一致）。

    Args:
        alarm_id: 闹钟编号，见 list_pending_alarms。
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
    """
    return services.alarm_cancel(_uid(user_id), alarm_id)


@mcp.tool
def get_weekly_checkin_status(user_id: str | None = None) -> str:
    """查询用户本周打卡概况：周期、本周图片数、是否本周首次、连续打卡 streak。

    Args:
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
    """
    return services.checkin_weekly_status(_uid(user_id))


@mcp.tool
def list_checkin_records(
    user_id: str | None = None,
    year: int | None = None,
    page: int = 1,
    page_size: int = 20,
    images_only: bool = False,
) -> str:
    """分页查询用户打卡记录（默认含无本地图片的记录）。

    Args:
        user_id: QQ 号；省略时使用 BOTERO_MCP_DEFAULT_USER_ID。
        year: 按自然年筛选，如 2025；省略则不限年份。
        page: 页码，从 1 开始。
        page_size: 每页条数，最大 50。
        images_only: 为 true 时仅返回本地仍有图片文件的记录。
    """
    return services.checkin_list_records(
        _uid(user_id),
        year=year,
        page=page,
        page_size=page_size,
        images_only=images_only,
    )


@mcp.tool
def list_weekly_checkin_members() -> str:
    """列出本周（周一 04:00 起算）已完成打卡的用户及首次打卡时间（与 /本周板油 数据源一致）。"""
    return services.checkin_list_week_members()
