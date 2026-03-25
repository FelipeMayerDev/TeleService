from typing import Optional

from ..models import Feature
from ..entities.feature import FeatureEntity
from .base import BaseRepository


class FeatureRepository(BaseRepository[Feature]):
    def __init__(self):
        super().__init__(Feature)

    def get_by_name(self, name: str) -> Optional[Feature]:
        try:
            return self.model.get(self.model.name == name)
        except Feature.DoesNotExist:
            return None

    def create_feature(self, name: str, status: bool) -> Feature:
        return self.create(name=name, status=status)

    def update_status(self, name: str, status: bool) -> bool:
        feature = self.get_by_name(name)
        if feature:
            self.update(feature, status=status)
            return True
        return False

    def toggle_status(self, name: str) -> Optional[bool]:
        feature = self.get_by_name(name)
        if feature:
            new_status = not feature.status
            self.update(feature, status=new_status)
            return new_status
        return None

    def get_status(self, name: str) -> Optional[bool]:
        feature = self.get_by_name(name)
        if feature:
            return feature.status
        return None

    def remove_by_name(self, name: str) -> bool:
        feature = self.get_by_name(name)
        if feature:
            self.delete(feature)
            return True
        return False
