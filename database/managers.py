from database.models import Feature, Message


class FeatureManager:
    @staticmethod
    def add_feature(name: str, status: bool) -> bool:
        Feature.create(name=name, status=status)
        return True

    @staticmethod
    def remove_feature(name):
        Feature.get(Feature.name == name).delete_instance()
        return True

    @staticmethod
    def toggle_feature(name):
        feature = Feature.get(Feature.name == name)
        feature.status = not feature.status
        feature.save()
        return True

    @staticmethod
    def get_feature_status(name):
        return Feature.get(Feature.name == name).status


class MessageManager:
    @staticmethod
    def get_message(id):
        return Message.get(Message.id == id)

    @staticmethod
    def add_message(
        telegram_message_id,
        text,
        chat_id,
        from_user,
        to_user=None,
        reply_to_message_id=None,
        reply_text=None,
    ):
        Message.create(
            telegram_message_id=telegram_message_id,
            text=text,
            chat_id=chat_id,
            from_user=from_user,
            to_user=to_user,
            reply_to_message_id=reply_to_message_id,
            reply_text=reply_text,
        )
        return True
