"""Image-only preset alignment using phase correlation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_MAX_ALIGNMENT_DIMENSION = 1024


def estimate_phase_shift(reference_path: Path, image_path: Path) -> tuple[float, float, float]:
    """Return the pixel shift to apply to image annotations and a normalized confidence."""

    reference = _load_gray_image(reference_path)
    image = _load_gray_image(image_path)
    if reference.shape != image.shape:
        image = _resize_gray_image(image, reference.shape)

    cross_power = np.fft.fft2(reference) * np.fft.fft2(image).conj()
    correlation = np.abs(
        np.fft.ifft2(cross_power / np.maximum(np.abs(cross_power), 1e-9))
    )
    peak = int(np.argmax(correlation))
    height, width = correlation.shape
    peak_y, peak_x = divmod(peak, width)
    shift_x = peak_x - width if peak_x > width // 2 else peak_x
    shift_y = peak_y - height if peak_y > height // 2 else peak_y
    # Peak-to-mean normalization is independent of image dimensions. The previous
    # peak-to-sum score is approximately 1/(width * height) even for an exact match.
    peak_to_mean = float(correlation.max() / max(float(correlation.mean()), 1e-9))
    confidence = 1.0 - 1.0 / max(peak_to_mean, 1.0)
    return float(shift_x), float(shift_y), round(confidence, 6)


def _load_gray_image(path: Path) -> np.ndarray:
    with Image.open(path) as opened:
        image = opened.convert("L")
        image.thumbnail((_MAX_ALIGNMENT_DIMENSION, _MAX_ALIGNMENT_DIMENSION))
        return np.asarray(image, dtype=np.float64) / 255.0


def _resize_gray_image(image: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    resized = Image.fromarray(np.uint8(image * 255)).resize(
        (shape[1], shape[0]), Image.Resampling.BILINEAR
    )
    return np.asarray(resized, dtype=np.float64) / 255.0
