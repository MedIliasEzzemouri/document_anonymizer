import re
from typing import List

from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span

# Sensitive "Label : Value" pairs — the value is tagged with the mapped type.
# Order matters: more specific phrases first (e.g. "Prénom" before "Nom").
_SENSITIVE = [
    (r"Date\s+de\s+naissance", EntityType.DATE),
    (r"Date\s+of\s+birth", EntityType.DATE),
    (r"Birth\s*date", EntityType.DATE),
    (r"Pr[ée]nom", EntityType.PERSON),
    (r"First\s*name", EntityType.PERSON),
    (r"N(?:[°oº]|um[ée]ro)\s*de\s*dossier", EntityType.REF),
    (r"File\s*(?:number|no\.?)", EntityType.REF),
    (r"\bNom\b", EntityType.PERSON),
    (r"\bName\b", EntityType.PERSON),
]

# Any label token ("<keyword>...:") — used to find where a value ends.
_KEYWORDS = (r"(?:Nom|Pr[ée]nom|Date|Montant|Moyen|N[°oº]|Num[ée]ro|Adresse|"
             r"T[ée]l[ée]phone|Email|E-mail|Name|First|File|Birth)")
_ANY_LABEL = re.compile(_KEYWORDS + r"[^:]{0,30}?:", re.IGNORECASE)


class LabelDetector(Detector):
    name = "label"

    def detect(self, text: str) -> List[Entity]:
        found: List[Entity] = []
        for pattern, etype in _SENSITIVE:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                after = text[m.end():]
                colon = re.match(r"\s*:\s*", after)
                if not colon:
                    continue  # not a "Label : value" pair
                val_start = m.end() + colon.end()
                nxt = _ANY_LABEL.search(text, val_start)
                val_end = nxt.start() if nxt else len(text)
                raw = text[val_start:val_end]
                value = raw.strip()
                if not value:
                    continue
                lead = len(raw) - len(raw.lstrip())
                start = val_start + lead
                end = start + len(value)
                found.append(Entity(etype, text[start:end], Span(start, end), self.name))
        return found
