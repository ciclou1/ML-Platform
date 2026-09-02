import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.annotation_shapes import validate_annotation_data
from app.core.dataset_files import (
    build_yolo_label_file_index,
    extract_class_names,
    read_image_size,
    read_yaml_payload,
    resolve_dataset_root_from_image_path,
    resolve_storage_path,
    resolve_yolo_label_path,
)
from app.models.annotation import Annotation
from app.models.dataset import Image, Label
from app.repositories.annotation import AnnotationRepository
from app.repositories.annotation_batch import AnnotationBatchItemRepository
from app.repositories.dataset import ImageRepository
from app.repositories.label import LabelRepository
from app.schemas.annotation import AnnotationCreate, AnnotationUpdate


class AnnotationService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AnnotationRepository(session)
        self.image_repo = ImageRepository(session)
        self.label_repo = LabelRepository(session)
        self.batch_item_repo = AnnotationBatchItemRepository(session)
        self.session = session

    async def list_by_image(self, image_id: uuid.UUID) -> list[Annotation]:
        annotations = await self.repo.list_by_image(image_id)
        if annotations:
            return annotations

        image = await self.image_repo.get_by_id(image_id)
        if not image:
            return []

        labels = await self.label_repo.list_by_dataset(image.dataset_id)
        return self._load_from_yolo_label(image, labels)

    async def create_annotation(self, data: AnnotationCreate) -> Annotation:
        validate_annotation_data(data.annotation_type, data.data)
        entity = Annotation(
            image_id=data.image_id,
            label_id=data.label_id,
            annotation_type=data.annotation_type,
            data=data.data,
        )
        result = await self.repo.create(entity)
        await self._mark_batch_item_annotating(data.image_id)
        await self._mark_image_status(data.image_id, "annotated")
        return result

    async def update_annotation(
        self, annotation_id: uuid.UUID, data: AnnotationUpdate
    ) -> Annotation | None:
        entity = await self.repo.get_by_id(annotation_id)
        if not entity:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if update_data.get("data") is not None:
            validate_annotation_data(entity.annotation_type, update_data["data"])
        for field, value in update_data.items():
            setattr(entity, field, value)
        result = await self.repo.update(entity)
        await self._mark_batch_item_annotating(entity.image_id)
        await self._mark_image_status(entity.image_id, "annotated")
        return result

    async def delete_annotation(self, annotation_id: uuid.UUID) -> bool:
        entity = await self.repo.get_by_id(annotation_id)
        if not entity:
            return False
        await self.repo.delete(entity)
        return True

    async def batch_create(self, items: list[AnnotationCreate]) -> list[Annotation]:
        results = []
        for item in items:
            entity = await self.create_annotation(item)
            results.append(entity)
        return results

    async def _mark_batch_item_annotating(self, image_id: uuid.UUID) -> None:
        item = await self.batch_item_repo.get_active_for_image(image_id)
        if item and item.status in {"pending", "rejected"}:
            item.status = "annotating"
            await self.batch_item_repo.update(item)

    async def replace_for_image(
        self, image_id: uuid.UUID, items: list[AnnotationCreate]
    ) -> list[Annotation]:
        """Delete all existing annotations for an image, then create new ones."""
        await self.repo.delete_by_image(image_id)
        results = []
        for item in items:
            entity = await self.create_annotation(item)
            results.append(entity)
        await self._mark_batch_item_annotating(image_id)
        await self._mark_image_status(image_id, "annotated" if results else "unannotated")
        return results

    async def _mark_image_status(self, image_id: uuid.UUID, status: str) -> None:
        image = await self.image_repo.get_by_id(image_id)
        if image and image.annotation_status != status:
            image.annotation_status = status
            await self.image_repo.update(image)

    def _load_from_yolo_label(self, image: Image, labels: list[Label]) -> list[Annotation]:
        label_path = self._resolve_label_path(image)
        if label_path is None or not label_path.exists():
            return []
        if not self._is_label_schema_compatible(image, labels):
            return []

        label_lookup = {index: label for index, label in enumerate(labels)}
        rows = [
            line.strip()
            for line in label_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        annotations: list[Annotation] = []

        for row in rows:
            parts = row.split()
            if len(parts) != 5:
                continue
            try:
                class_index = int(float(parts[0]))
                x_center, y_center, width, height = [float(value) for value in parts[1:]]
            except ValueError:
                continue

            label = label_lookup.get(class_index)
            image_width, image_height = self._resolve_image_size(image)
            if not label or image_width <= 0 or image_height <= 0:
                continue

            abs_width = width * image_width
            abs_height = height * image_height
            abs_x = x_center * image_width - abs_width / 2
            abs_y = y_center * image_height - abs_height / 2

            annotations.append(
                Annotation(
                    id=uuid.uuid4(),
                    image_id=image.id,
                    label_id=label.id,
                    annotation_type="bbox",
                    data={
                        "x": round(abs_x, 2),
                        "y": round(abs_y, 2),
                        "width": round(abs_width, 2),
                        "height": round(abs_height, 2),
                    },
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            annotations[-1].label_name = label.name
            annotations[-1].color = label.color

        return annotations

    @classmethod
    def _resolve_label_path(cls, image: Image) -> Path | None:
        image_path = resolve_storage_path(image.file_path)
        dataset_root = resolve_dataset_root_from_image_path(image_path)
        label_index = build_yolo_label_file_index(dataset_root)
        return resolve_yolo_label_path(
            dataset_root,
            image_path,
            image_split=image.split,
            label_index=label_index,
        )

    @classmethod
    def _resolve_image_size(cls, image: Image) -> tuple[int, int]:
        if image.width > 0 and image.height > 0:
            return image.width, image.height

        image_path = resolve_storage_path(image.file_path)
        if not image_path.exists():
            return 0, 0

        return read_image_size(image_path)

    @classmethod
    def _is_label_schema_compatible(cls, image: Image, labels: list[Label]) -> bool:
        image_path = resolve_storage_path(image.file_path)
        dataset_root = resolve_dataset_root_from_image_path(image_path)
        yaml_path = dataset_root / "data.yaml"
        if not yaml_path.exists():
            return True

        try:
            class_names = extract_class_names(read_yaml_payload(yaml_path))
        except Exception:
            return True

        if not class_names:
            return True
        if len(labels) != len(class_names):
            return False

        ordered_labels = sorted(labels, key=lambda label: (label.sort_order, label.name))
        return all(label.name == class_names[index] for index, label in enumerate(ordered_labels))
