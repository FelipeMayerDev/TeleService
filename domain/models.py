from datetime import datetime
from typing import Optional

from peewee import (
    BooleanField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)

db = SqliteDatabase("database.sqlite")


class BaseModel(Model):
    class Meta:
        database = db


class Feature(BaseModel):
    id = IntegerField(primary_key=True)
    name = TextField()
    status = BooleanField(default=True)

    @property
    def is_enabled(self) -> bool:
        return self.status

    class Meta:
        table_name = "feature"


class Message(BaseModel):
    id = IntegerField(primary_key=True)
    platform = TextField(default="telegram")
    platform_message_id = IntegerField()
    text = TextField()
    chat_id = IntegerField()
    from_user = TextField()
    to_user = TextField(null=True)
    reply_to_message_id = IntegerField(null=True)
    reply_text = TextField(null=True)
    message_type = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "message"


def init_database():
    with db:
        if not Feature.table_exists():
            Feature.create_table()

        if not Message.table_exists():
            Message.create_table()
        else:
            columns = [c.name for c in Message._meta.fields.values()]
            if "platform" not in columns:
                db.execute_sql(
                    "ALTER TABLE message ADD COLUMN platform TEXT DEFAULT 'telegram'"
                )
            if (
                "telegram_message_id" in columns
                and "platform_message_id" not in columns
            ):
                db.execute_sql(
                    "ALTER TABLE message RENAME COLUMN telegram_message_id TO platform_message_id"
                )
