#!/usr/bin/env python
"""
Integration test to verify the domain layer restructure works correctly
for both Telegram and Discord bots.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from domain import (
    FeatureService,
    MessageService,
    MessageEntity,
    FeatureEntity,
    init_database,
)


def test_message_service():
    """Test MessageService with both Telegram and Discord platforms."""
    print("\n" + "=" * 50)
    print("Testing MessageService")
    print("=" * 50)

    service = MessageService()

    # Test Telegram messages (backward compatibility)
    print("\n1. Testing Telegram messages...")
    result = service.add_telegram_message(
        telegram_message_id=9001,
        text="Hello from Telegram!",
        chat_id=123,
        from_user="telegram_user",
        message_type="text",
    )
    assert result is True, "Failed to add Telegram message"
    print("   ✓ Telegram message added")

    # Test Discord messages
    print("\n2. Testing Discord messages...")
    result = service.add_discord_message(
        discord_message_id=8001,
        text="Hello from Discord!",
        chat_id=456,
        from_user="discord_user",
        message_type="text",
    )
    assert result is True, "Failed to add Discord message"
    print("   ✓ Discord message added")

    # Test generic add_message
    print("\n3. Testing generic add_message...")
    result = service.add_message(
        platform="telegram",
        platform_message_id=9002,
        text="Generic message",
        chat_id=123,
        from_user="generic_user",
        message_type="text",
    )
    assert result is True, "Failed to add generic message"
    print("   ✓ Generic message added")

    # Test get_last_messages (platform-specific)
    print("\n4. Testing get_last_messages...")
    messages = service.get_last_messages(chat_id=123, platform="telegram", limit=5)
    assert len(messages) >= 2, "Failed to get last messages"
    print(f"   ✓ Got {len(messages)} Telegram messages from chat 123")

    messages = service.get_last_messages(chat_id=456, platform="discord", limit=5)
    assert len(messages) >= 1, "Failed to get Discord messages"
    print(f"   ✓ Got {len(messages)} Discord messages from chat 456")

    # Test get_last_message_by_type
    print("\n5. Testing get_last_message_by_type...")
    msg = service.get_last_message_by_type(
        chat_id=123, message_type="text", platform="telegram"
    )
    assert msg is not None, "Failed to get last message by type"
    assert msg.platform == "telegram", "Wrong platform"
    assert msg.message_type == "text", "Wrong message type"
    print(f"   ✓ Last text message: {msg.text[:30]}")

    # Test update_message_text
    print("\n6. Testing update_message_text...")
    result = service.update_message_text(
        platform_message_id=9001, text="Updated Telegram text", platform="telegram"
    )
    assert result is True, "Failed to update message"
    print("   ✓ Message updated")

    # Verify update by getting the specific message
    from domain import MessageRepository

    repo = MessageRepository()
    msg_model = repo.get_by_platform_message_id(9001, platform="telegram")
    assert msg_model is not None, "Message not found"
    assert msg_model.text == "Updated Telegram text", "Message text not updated"
    print("   ✓ Update verified")

    print("\n✅ MessageService tests passed!")


def test_feature_service():
    """Test FeatureService."""
    print("\n" + "=" * 50)
    print("Testing FeatureService")
    print("=" * 50)

    service = FeatureService()

    # Test add_feature
    print("\n1. Testing add_feature...")
    result = service.add_feature("test_feature_integration", status=True)
    assert result is True, "Failed to add feature"
    print("   ✓ Feature added")

    # Test get_feature_status
    print("\n2. Testing get_feature_status...")
    status = service.get_feature_status("test_feature_integration")
    assert status is True, "Wrong feature status"
    print(f"   ✓ Feature status: {status}")

    # Test toggle_feature
    print("\n3. Testing toggle_feature...")
    new_status = service.toggle_feature("test_feature_integration")
    assert new_status is False, "Failed to toggle feature"
    print(f"   ✓ Feature toggled to: {new_status}")

    # Test is_feature_enabled
    print("\n4. Testing is_feature_enabled...")
    enabled = service.is_feature_enabled("test_feature_integration")
    assert enabled is False, "Feature should be disabled"
    print(f"   ✓ Feature enabled: {enabled}")

    # Test remove_feature
    print("\n5. Testing remove_feature...")
    result = service.remove_feature("test_feature_integration")
    assert result is True, "Failed to remove feature"
    print("   ✓ Feature removed")

    # Verify removal
    status = service.get_feature_status("test_feature_integration")
    assert status is None, "Feature should not exist"
    print("   ✓ Removal verified")

    print("\n✅ FeatureService tests passed!")


def test_cross_platform_messages():
    """Test that both platforms use the same table correctly."""
    print("\n" + "=" * 50)
    print("Testing Cross-Platform Messages")
    print("=" * 50)

    service = MessageService()

    # Add messages from different platforms with same chat_id
    print("\n1. Adding messages from different platforms...")
    service.add_telegram_message(
        telegram_message_id=9101, text="Telegram msg", chat_id=999, from_user="user1"
    )
    service.add_discord_message(
        discord_message_id=8101, text="Discord msg", chat_id=999, from_user="user2"
    )
    print("   ✓ Messages added")

    # Get Telegram messages only
    print("\n2. Getting Telegram messages...")
    telegram_msgs = service.get_last_messages(
        chat_id=999, platform="telegram", limit=10
    )
    assert len(telegram_msgs) >= 1, "No Telegram messages found"
    print(f"   ✓ Found {len(telegram_msgs)} Telegram messages")
    for msg in telegram_msgs:
        assert msg.platform == "telegram", "Wrong platform in Telegram query"

    # Get Discord messages only
    print("\n3. Getting Discord messages...")
    discord_msgs = service.get_last_messages(chat_id=999, platform="discord", limit=10)
    assert len(discord_msgs) >= 1, "No Discord messages found"
    print(f"   ✓ Found {len(discord_msgs)} Discord messages")
    for msg in discord_msgs:
        assert msg.platform == "discord", "Wrong platform in Discord query"

    print("\n✅ Cross-platform tests passed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("DOMAIN LAYER RESTRUCTURE INTEGRATION TESTS")
    print("=" * 60)

    # Initialize database
    print("\nInitializing database...")
    init_database()
    print("✓ Database initialized")

    # Run tests
    try:
        test_message_service()
        test_feature_service()
        test_cross_platform_messages()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print(
            "\nThe domain layer restructure is working correctly."
            "\nBoth Telegram and Discord bots can now use the same"
            "\nMessageService and FeatureService instances."
        )
        return 0
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
