import pytest

from app.core.annotation_shapes import assert_exportable, infer_model_task
from app.exceptions import ValidationError
from app.services.dataset import DatasetService


def test_classification_export_and_training_task_are_supported() -> None:
    assert_exportable(["classify"])
    assert infer_model_task(["classify"]) == "classify"


def test_dataset_annotation_types_normalization() -> None:
    assert DatasetService._normalize_annotation_types(None) is None
    assert DatasetService._normalize_annotation_types([]) is None
    assert DatasetService._normalize_annotation_types(["classify"]) == ["classify"]
    assert DatasetService._normalize_annotation_types(["classify", "bbox", "classify"]) == [
        "classify",
        "bbox",
    ]

    with pytest.raises(ValidationError):
        DatasetService._normalize_annotation_types(["bogus"])
