from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CIN = "CIN"
    RIB = "RIB"
    IBAN = "IBAN"
    CREDIT_CARD = "CREDIT_CARD"


@dataclass(frozen=True)
class Span:
    start: int  # inclusive char offset
    end: int    # exclusive char offset


@dataclass
class Entity:
    type: EntityType
    text: str
    span: Span
    detector: str
    score: float = 1.0
    replacement: Optional[str] = None
