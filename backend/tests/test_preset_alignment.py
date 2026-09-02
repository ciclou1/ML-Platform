from pathlib import Path

from PIL import Image

from app.core.annotation_shapes import translate_annotation_data
from app.core.preset_alignment import estimate_phase_shift
from app.services.preset_alignment import PresetAlignmentService


def test_translate_annotation_data_preserves_keypoint_visibility() -> None:
    translated = translate_annotation_data(
        "keypoint",
        {"bbox": {"x": 1, "y": 2, "width": 3, "height": 4}, "points": [[5, 6, 1]]},
        10,
        -2,
    )

    assert translated == {
        "bbox": {"x": 11.0, "y": 0.0, "width": 3, "height": 4},
        "points": [[15.0, 4.0, 1]],
    }


def test_phase_correlation_of_same_image_has_no_shift(tmp_path: Path) -> None:
    image_path = tmp_path / "reference.png"
    image = Image.new("L", (32, 32), color=0)
    image.putpixel((8, 12), 255)
    image.putpixel((20, 18), 128)
    image.save(image_path)

    dx, dy, confidence = estimate_phase_shift(image_path, image_path)

    assert (dx, dy) == (0.0, 0.0)
    assert confidence > 0.99


def test_zero_confidence_is_allowed_by_default_threshold() -> None:
    assert PresetAlignmentService._passes_confidence(0.0, 0.0)
    assert not PresetAlignmentService._passes_confidence(0.0, 0.001)
