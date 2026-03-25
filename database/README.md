# DEPRECATED - Database Module

This directory has been deprecated and migrated to the `domain/` module.

## Migration Summary

The database layer has been refactored following Domain-Driven Design (DDD) principles:

### Old Structure (deprecated)
- `database/connection.py` → `domain/models.py` (db connection)
- `database/models.py` → `domain/models.py` (Peewee models)
- `database/managers.py` → `domain/repositories/` and `domain/services/`
- `database/main.py` → `domain/__init__.py` (init_database)

### New Structure (current)
```
domain/
├── __init__.py              # Main exports (init_database, services)
├── models.py                # Peewee models (Feature, Message, db)
├── entities/                # Domain entities
│   ├── __init__.py
│   ├── feature.py          # FeatureEntity
│   └── message.py          # MessageEntity
├── repositories/            # Data access layer
│   ├── __init__.py
│   ├── base.py             # BaseRepository
│   ├── feature_repository.py
│   └── message_repository.py
└── services/                 # Business logic layer
    ├── __init__.py
    ├── feature_service.py
    └── message_service.py
```

## Key Changes

1. **Platform Agnostic**: Messages now support multiple platforms (telegram, discord)
2. **Repository Pattern**: Clean separation between data access and business logic
3. **Service Layer**: Business logic encapsulated in service classes
4. **Better Testing**: Services can be easily mocked and tested
5. **DDD Architecture**: Domain entities separated from infrastructure models

## Database Schema Changes

The `message` table was migrated:
- Added `platform` column (TEXT, default "telegram")
- Renamed `telegram_message_id` to `platform_message_id`

## Usage

### Old Way (deprecated)
```python
from database.managers import MessageManager

MessageManager.add_message(
    telegram_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    message_type="text",
)
```

### New Way (recommended)
```python
from domain import MessageService

service = MessageService()

# Telegram messages (backward compatible)
service.add_telegram_message(
    telegram_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    message_type="text",
)

# Discord messages
service.add_discord_message(
    discord_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    message_type="text",
)

# Generic (platform-agnostic)
service.add_message(
    platform="telegram",
    platform_message_id=123,
    text="Hello",
    chat_id=456,
    from_user="user",
    message_type="text",
)
```

## Migration Date
March 25, 2026

## Notes

- The old files are kept here for reference only
- All bots (telegrambot, discordbot, steam) have been updated
- No code changes are required as the new API provides backward compatibility
- Database migration was handled automatically by `init_database()`
