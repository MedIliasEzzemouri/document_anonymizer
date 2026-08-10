import re
from typing import Callable, Dict, List, Tuple

NerEngine = Callable[[str], List[Tuple[str, int, int]]]

_TOKEN = re.compile(r"\S+")


def spacy_engine(model_name: str) -> NerEngine:
    import spacy  # lazy: only when actually building the engine
    nlp = spacy.load(model_name)

    def run(text: str) -> List[Tuple[str, int, int]]:
        doc = nlp(text)
        return [(ent.label_, ent.start_char, ent.end_char) for ent in doc.ents]

    return run


def camel_engine() -> NerEngine:
    from camel_tools.ner import NERecognizer  # lazy
    ner = NERecognizer.pretrained()

    def run(text: str) -> List[Tuple[str, int, int]]:
        tokens = list(_TOKEN.finditer(text))
        if not tokens:
            return []
        labels = ner.predict([[m.group() for m in tokens]])[0]  # BIO tags per token
        out: List[Tuple[str, int, int]] = []
        cur_type = None
        cur_start = cur_end = 0
        for m, lab in zip(tokens, labels):
            if not lab or lab == "O":
                if cur_type is not None:
                    out.append((cur_type, cur_start, cur_end))
                    cur_type = None
                continue
            prefix, _, etype = lab.partition("-")
            if prefix == "B" or etype != cur_type:
                if cur_type is not None:
                    out.append((cur_type, cur_start, cur_end))
                cur_type, cur_start, cur_end = etype, m.start(), m.end()
            else:  # I- continuation of the same type
                cur_end = m.end()
        if cur_type is not None:
            out.append((cur_type, cur_start, cur_end))
        return out

    return run


def default_engines() -> Dict[str, NerEngine]:
    engines: Dict[str, NerEngine] = {}
    for key, model in (("spacy-en", "en_core_web_sm"), ("spacy-fr", "fr_core_news_sm")):
        try:
            engines[key] = spacy_engine(model)
        except Exception:
            pass  # model or spaCy not installed — skip this language
    try:
        engines["camel-ar"] = camel_engine()
    except Exception:
        pass
    return engines
