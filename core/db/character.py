import json
import sqlite3
from datetime import datetime


class CharacterManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cur = conn.cursor()

    def create(self, user_id, char_data: dict) -> int:
        """创建角色卡，返回角色 id。char_data 字段见 schema。"""
        self.cur.execute("""
            INSERT INTO dnd_characters (
                user_id, char_name, race, class_name, level, background,
                str_score, dex_score, con_score, int_score, wis_score, cha_score,
                proficient_skills, hp, ac, equipment, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(user_id),
            char_data["char_name"],
            char_data["race"],
            char_data["class_name"],
            int(char_data.get("level", 1)),
            char_data.get("background", ""),
            int(char_data["str_score"]), int(char_data["dex_score"]),
            int(char_data["con_score"]), int(char_data["int_score"]),
            int(char_data["wis_score"]), int(char_data["cha_score"]),
            json.dumps(char_data.get("proficient_skills", []), ensure_ascii=False),
            int(char_data.get("hp", 0)), int(char_data.get("ac", 10)),
            json.dumps(char_data.get("equipment", []), ensure_ascii=False),
            char_data.get("notes", ""),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ))
        self.conn.commit()
        char_id = self.cur.lastrowid
        if char_id is None:
            raise ValueError("角色创建失败")
        # 第一个角色自动设为当前角色
        if self.current_id(user_id) is None:
            self.set_current(user_id, char_id)
        return char_id

    def get(self, char_id) -> dict | None:
        self.cur.execute("""
            SELECT id, user_id, char_name, race, class_name, level, background,
                   str_score, dex_score, con_score, int_score, wis_score, cha_score,
                   proficient_skills, hp, ac, equipment, notes, created_at, updated_at
            FROM dnd_characters WHERE id = ?
        """, (int(char_id),))
        row = self.cur.fetchone()
        if not row:
            return None
        cols = ["id", "user_id", "char_name", "race", "class_name", "level", "background",
                "str_score", "dex_score", "con_score", "int_score", "wis_score", "cha_score",
                "proficient_skills", "hp", "ac", "equipment", "notes", "created_at", "updated_at"]
        data = dict(zip(cols, row))
        data["proficient_skills"] = json.loads(data["proficient_skills"] or "[]")
        data["equipment"] = json.loads(data["equipment"] or "[]")
        data["notes"] = data.get("notes") or ""
        return data

    def list_by_user(self, user_id) -> list[dict]:
        self.cur.execute("""
            SELECT id FROM dnd_characters
            WHERE user_id = ?
            ORDER BY id ASC
        """, (str(user_id),))
        out = []
        for r in self.cur.fetchall():
            data = self.get(r[0])
            if data:
                out.append(data)
        return out

    def update(self, char_id, **fields) -> bool:
        allowed = {"char_name", "race", "class_name", "level", "background",
                   "str_score", "dex_score", "con_score", "int_score", "wis_score", "cha_score",
                   "hp", "ac", "notes"}
        sets, values = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k} = ?")
                values.append(v)
        if not sets:
            return False
        sets.append("updated_at = ?")
        values.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        values.append(int(char_id))
        self.cur.execute(f"UPDATE dnd_characters SET {', '.join(sets)} WHERE id = ?", values)
        self.conn.commit()
        return True

    def delete(self, char_id) -> None:
        self.cur.execute("DELETE FROM dnd_characters WHERE id = ?", (int(char_id),))
        self.cur.execute("DELETE FROM dnd_current_character WHERE character_id = ?", (int(char_id),))
        self.conn.commit()

    def current_id(self, user_id) -> int | None:
        self.cur.execute(
            "SELECT character_id FROM dnd_current_character WHERE user_id = ?",
            (str(user_id),)
        )
        row = self.cur.fetchone()
        return row[0] if row else None

    def current(self, user_id) -> dict | None:
        cid = self.current_id(user_id)
        return self.get(cid) if cid is not None else None

    def set_current(self, user_id, char_id) -> None:
        self.cur.execute("""
            INSERT INTO dnd_current_character (user_id, character_id)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET character_id = excluded.character_id
        """, (str(user_id), int(char_id)))
        self.conn.commit()

    def clear_current(self, user_id) -> None:
        self.cur.execute("DELETE FROM dnd_current_character WHERE user_id = ?", (str(user_id),))
        self.conn.commit()
