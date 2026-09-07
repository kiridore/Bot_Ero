"""周报脏数据清理脚本：删除指定 week_key（或某日期之前）的 weekly_reports 行。

背景：周报功能 2026-08-16 上线，启动补偿曾为消息日志未覆盖的历史周生成空/残缺周报
（如 2026-08-03、2026-08-10 两期）。配合 plugins/weekly_report 的日志覆盖校验使用：
先停 bot，跑本脚本清理，再部署带校验的新代码启动，避免旧代码重启时补漏复活脏数据。

触碰**真实 data.db**（非测试），须在项目根目录运行：
    python scripts/purge_weekly_reports.py --week-key 2026-08-03 --week-key 2026-08-10
    python scripts/purge_weekly_reports.py --before 2026-08-17
"""

import argparse
import json
import sqlite3

from core import config


def _describe(row) -> str:
    week_key, group_id, created_at, data_json = row
    try:
        period = json.loads(data_json).get("period", {})
        detail = f"第 {period.get('issue', '?')} 期，{period.get('total_messages', '?')} 条消息"
    except (ValueError, TypeError):
        detail = "data_json 解析失败"
    return f"  week_key={week_key}  group={group_id}  created_at={created_at}  ({detail})"


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 weekly_reports 脏数据（真实 data.db）")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--week-key", action="append", default=[], metavar="YYYY-MM-DD",
        help="要删除的周报 week_key（可多次传入）",
    )
    selector.add_argument(
        "--before", metavar="YYYY-MM-DD",
        help="删除 week_key 小于该日期的全部周报",
    )
    parser.add_argument("--yes", action="store_true", help="跳过确认直接删除")
    args = parser.parse_args()

    conn = sqlite3.connect(str(config.DB_PATH))
    cur = conn.cursor()
    try:
        if args.week_key:
            keys = args.week_key
        else:
            cur.execute(
                "SELECT week_key FROM weekly_reports WHERE week_key < ? ORDER BY week_key",
                (args.before,),
            )
            keys = [row[0] for row in cur.fetchall()]
        if not keys:
            print("没有匹配的周报记录，无需清理。")
            return

        for key in keys:
            cur.execute(
                "SELECT week_key, group_id, created_at, data_json FROM weekly_reports"
                " WHERE week_key = ?",
                (key,),
            )
            for row in cur.fetchall():
                print(_describe(row))

        if not args.yes and input(f"确认删除以上 {len(keys)} 个 week_key 的周报？(y/N) ").strip().lower() != "y":
            print("已取消。")
            return

        deleted = 0
        for key in keys:
            cur.execute("DELETE FROM weekly_reports WHERE week_key = ?", (key,))
            deleted += cur.rowcount
        conn.commit()
        print(f"已删除 {deleted} 行。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
