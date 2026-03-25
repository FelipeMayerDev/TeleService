from typing import Optional

from ..entities.feature import FeatureEntity
from ..repositories.feature_repository import FeatureRepository


class FeatureService:
    def __init__(self, repository: Optional[FeatureRepository] = None):
        self.repository = repository or FeatureRepository()

    def add_feature(self, name: str, status: bool = True) -> bool:
        existing = self.repository.get_by_name(name)
        if existing:
            return False

        self.repository.create_feature(name, status)
        return True

    def remove_feature(self, name: str) -> bool:
        return self.repository.remove_by_name(name)

    def toggle_feature(self, name: str) -> Optional[bool]:
        return self.repository.toggle_status(name)

    def get_feature_status(self, name: str) -> Optional[bool]:
        return self.repository.get_status(name)

    def is_feature_enabled(self, name: str) -> bool:
        status = self.repository.get_status(name)
        return status if status is not None else False
