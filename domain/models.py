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


class SteamProfileState(BaseModel):
    """Rastreia o estado dos perfis Steam monitorados."""
    profile = TextField(index=True, unique=True)
    is_playing = BooleanField(default=False)
    game = TextField(null=True)
    game_id = IntegerField(null=True)
    last_notified_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "steam_profile_state"


def claim_game_notification(
    profile: str, game: str, game_id: int | None = None
) -> bool:
    """Atomically claim a person/game transition across all monitor processes."""
    now = datetime.now()
    with db.atomic("IMMEDIATE"):
        state = SteamProfileState.get_or_none(SteamProfileState.profile == profile)
        if state and state.is_playing and state.game == game:
            return False
        if state:
            state.is_playing = True
            state.game = game
            state.game_id = game_id
            state.last_notified_at = now
            state.updated_at = now
            state.save()
        else:
            SteamProfileState.create(
                profile=profile,
                is_playing=True,
                game=game,
                game_id=game_id,
                last_notified_at=now,
                updated_at=now,
            )
    return True


class MediaShare(BaseModel):
    """Quem já enviou cada link de mídia no grupo (detecção de repetidos)."""
    link = TextField(index=True)
    sender = TextField()
    chat_id = IntegerField()
    created_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "media_share"


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

        if not SteamProfileState.table_exists():
            SteamProfileState.create_table()

        if not MediaShare.table_exists():
            MediaShare.create_table()
