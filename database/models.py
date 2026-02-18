from datetime import datetime

from peewee import BooleanField, DateTimeField, IntegerField, TextField

from .connection import db


class Feature(db.Model):
    id = IntegerField(primary_key=True)
    name = TextField()
    status = BooleanField(default=True)

    @property
    def is_enabled(self):
        return self.status


class Message(db.Model):
    id = IntegerField(primary_key=True)
    text = TextField()
    telegram_message_id = IntegerField()
    chat_id = IntegerField()
    from_user = TextField()
    to_user = TextField(null=True)
    reply_to_message_id = IntegerField(null=True)
    reply_text = TextField(null=True)
    message_type = TextField(null=True)
    created_at = DateTimeField(default=datetime.now)
