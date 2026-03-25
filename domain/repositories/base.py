from typing import Generic, Optional, TypeVar

from ..models import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    def __init__(self, model: type[T]):
        self.model = model

    def create(self, **kwargs) -> T:
        return self.model.create(**kwargs)

    def get_by_id(self, id: int) -> Optional[T]:
        try:
            return self.model.get_by_id(id)
        except self.model.DoesNotExist:
            return None

    def get(self, **kwargs) -> Optional[T]:
        try:
            return self.model.get(**kwargs)
        except self.model.DoesNotExist:
            return None

    def update(self, instance: T, **kwargs) -> int:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        return instance.save()

    def delete(self, instance: T) -> int:
        return instance.delete_instance()

    def list(self, limit: Optional[int] = None, **kwargs) -> list[T]:
        query = self.model.select()
        if kwargs:
            query = query.filter(**kwargs)
        if limit:
            query = query.limit(limit)
        return list(query)
