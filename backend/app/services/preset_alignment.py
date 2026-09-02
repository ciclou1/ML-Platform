from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.annotation_shapes import translate_annotation_data
from app.core.dataset_files import resolve_storage_path
from app.core.preset_alignment import estimate_phase_shift
from app.exceptions import NotFoundError, ValidationError
from app.repositories.annotation import AnnotationRepository
from app.repositories.dataset import ImageRepository


class PresetAlignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.image_repo = ImageRepository(session)
        self.annotation_repo = AnnotationRepository(session)

    async def estimate(
        self, image_id: uuid.UUID, reference_image_id: uuid.UUID
    ) -> dict[str, float]:
        image, reference = await self._get_image_pair(image_id, reference_image_id)
        dx, dy, confidence = estimate_phase_shift(
            resolve_storage_path(reference.file_path), resolve_storage_path(image.file_path)
        )
        return {"dx": dx, "dy": dy, "confidence": confidence}

    async def apply(
        self, image_id: uuid.UUID, reference_image_id: uuid.UUID, min_confidence: float
    ) -> dict[str, Any]:
        shift = await self.estimate(image_id, reference_image_id)
        if not self._passes_confidence(shift["confidence"], min_confidence):
            raise ValidationError("Preset alignment confidence is below the requested threshold")
        annotations = await self.annotation_repo.list_by_image(image_id)
        for annotation in annotations:
            annotation.data = translate_annotation_data(
                annotation.annotation_type, annotation.data, shift["dx"], shift["dy"]
            )
            await self.annotation_repo.update(annotation)
        return {**shift, "corrected_annotations": len(annotations)}

    @staticmethod
    def _passes_confidence(confidence: float, min_confidence: float) -> bool:
        return min_confidence <= 0 or confidence >= min_confidence

    async def _get_image_pair(self, image_id: uuid.UUID, reference_image_id: uuid.UUID):
        image = await self.image_repo.get_by_id(image_id)
        reference = await self.image_repo.get_by_id(reference_image_id)
        if not image or not reference:
            raise NotFoundError("Image or preset reference image not found")
        if image.dataset_id != reference.dataset_id:
            raise ValidationError("Preset reference image must belong to the same dataset")
        return image, reference
