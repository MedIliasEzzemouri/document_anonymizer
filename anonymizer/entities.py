from dataclasses import dataclass
from enum import Enum
from typing import Optional


class EntityType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    IBAN = "IBAN"
    RIB = "RIB"
    CREDIT_CARD = "CREDIT_CARD"
    # National ID numbers (one member per country format).
    CIN = "CIN"      # Morocco
    SSN = "SSN"      # United States
    NINO = "NINO"    # United Kingdom
    DNI = "DNI"      # Spain (DNI and NIE)


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
