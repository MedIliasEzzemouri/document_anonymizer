from abc import ABC, abstractmethod
from typing import List

from anonymizer.entities import Entity


class Detector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, text: str) -> List[Entity]:
        ...
