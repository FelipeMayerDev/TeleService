from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FeatureEntity:
    name: str
    status: bool = True

    def is_enabled(self) -> bool:
        return self.status

    def toggle(self) -> "FeatureEntity":
        return FeatureEntity(name=self.name, status=not self.status)
