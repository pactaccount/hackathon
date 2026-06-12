"""Robin — ClickHouse Memory Client"""
import json
import certifi
from datetime import datetime, timezone
from typing import Any

import clickhouse_connect
import structlog

from config import settings

log = structlog.get_logger()


class ClickHouseClient:
    def __init__(self):
        self._client = None

    def _connect(self):
        if self._client is None:
            self._client = clickhouse_connect.get_client(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                username=settings.CLICKHOUSE_USER,
                password=settings.CLICKHOUSE_PASSWORD,
                database=settings.CLICKHOUSE_DATABASE,
                secure=True,
                verify=certifi.where(),
            )
        return self._client

    def ensure_schema(self):
        c = self._connect()
        tables = [
            """CREATE TABLE IF NOT EXISTS conversations (
                id String, user_id String, session_id String,
                role String, content String,
                created_at DateTime64(3, 'UTC') DEFAULT now()
            ) ENGINE = MergeTree() ORDER BY (user_id, created_at)""",

            """CREATE TABLE IF NOT EXISTS user_profile (
                user_id String, key String, value String,
                updated_at DateTime64(3, 'UTC') DEFAULT now()
            ) ENGINE = ReplacingMergeTree(updated_at) ORDER BY (user_id, key)""",

            """CREATE TABLE IF NOT EXISTS calendar_events (
                user_id String, event_id String, title String,
                start_time DateTime64(3, 'UTC'), end_time DateTime64(3, 'UTC'),
                location String DEFAULT '', description String DEFAULT '',
                synced_at DateTime64(3, 'UTC') DEFAULT now()
            ) ENGINE = ReplacingMergeTree(synced_at) ORDER BY (user_id, event_id)""",

            """CREATE TABLE IF NOT EXISTS tool_executions (
                run_id String, user_id String, provider String,
                tool_name String DEFAULT '', result String DEFAULT '',
                executed_at DateTime64(3, 'UTC') DEFAULT now()
            ) ENGINE = MergeTree() ORDER BY (user_id, executed_at)""",
        ]
        for sql in tables:
            c.command(sql)
        log.info("clickhouse_schema_ready")

    def save_message(self, user_id: str, session_id: str, role: str, content: str, msg_id: str):
        c = self._connect()
        c.insert("conversations", [[msg_id, user_id, session_id, role, content,
                                    datetime.now(timezone.utc)]])

    def get_history(self, user_id: str, limit: int = 10) -> list[dict]:
        c = self._connect()
        result = c.query(
            "SELECT role, content FROM conversations WHERE user_id = {uid:String} "
            "ORDER BY created_at DESC LIMIT {lim:Int32}",
            parameters={"uid": user_id, "lim": limit}
        )
        rows = [{"role": r[0], "content": r[1]} for r in result.result_set]
        return list(reversed(rows))

    def get_all_history(self, user_id: str, limit: int = 50) -> list[dict]:
        c = self._connect()
        result = c.query(
            "SELECT role, content, created_at FROM conversations WHERE user_id = {uid:String} "
            "ORDER BY created_at DESC LIMIT {lim:Int32}",
            parameters={"uid": user_id, "lim": limit}
        )
        return [{"role": r[0], "content": r[1], "created_at": str(r[2])} for r in result.result_set]

    def get_user_profile(self, user_id: str) -> dict:
        c = self._connect()
        result = c.query(
            "SELECT key, value FROM user_profile WHERE user_id = {uid:String}",
            parameters={"uid": user_id}
        )
        return {r[0]: r[1] for r in result.result_set}

    def set_user_profile(self, user_id: str, key: str, value: str):
        c = self._connect()
        c.insert("user_profile", [[user_id, key, value, datetime.now(timezone.utc)]])

    def get_today_calendar(self, user_id: str) -> list[dict]:
        c = self._connect()
        result = c.query(
            "SELECT event_id, title, start_time, end_time, location FROM calendar_events "
            "WHERE user_id = {uid:String} AND toDate(start_time) = today() ORDER BY start_time",
            parameters={"uid": user_id}
        )
        return [{"event_id": r[0], "title": r[1], "start": str(r[2]),
                 "end": str(r[3]), "location": r[4]} for r in result.result_set]

    def count_messages(self, user_id: str) -> int:
        c = self._connect()
        result = c.query(
            "SELECT count() FROM conversations WHERE user_id = {uid:String} AND role = 'user'",
            parameters={"uid": user_id}
        )
        return result.result_set[0][0] if result.result_set else 0


ch_client = ClickHouseClient()
