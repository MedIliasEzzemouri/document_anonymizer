import pytest
from anonymizer.detectors.base import Detector
from anonymizer.entities import Entity, EntityType, Span


def test_cannot_instantiate_abstract_detector():
    with pytest.raises(TypeError):
        Detector()


def test_concrete_subclass_works():
    class Dummy(Detector):
        name = "dummy"

        def detect(self, text):
            return [Entity(EntityType.EMAIL, "x", Span(0, 1), self.name)]

    result = Dummy().detect("anything")
    assert result[0].detector == "dummy"
