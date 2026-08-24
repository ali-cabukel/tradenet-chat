from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from tradenet_chat.api.schemas import MessageFeedbackUpdate
from tradenet_chat.db.engine import ensure_chat_message_columns


def test_feedback_update_accepts_up_down_or_null() -> None:
    assert MessageFeedbackUpdate(rating="up").rating == "up"
    assert MessageFeedbackUpdate(rating="down").rating == "down"
    assert MessageFeedbackUpdate(rating=None).rating is None
    assert MessageFeedbackUpdate().rating is None


def test_ensure_chat_message_columns_adds_feedback_fields(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE chat_messages ("
                "id INTEGER PRIMARY KEY, thread_id VARCHAR, role VARCHAR, "
                "content TEXT, created_at DATETIME)"
            )
        )
        ensure_chat_message_columns(connection)
        names = {col["name"] for col in inspect(connection).get_columns("chat_messages")}
    assert {
        "feedback",
        "feedback_at",
        "regenerate_count",
        "regenerated_at",
        "queries",
    } <= names
    with engine.begin() as connection:
        ensure_chat_message_columns(connection)
