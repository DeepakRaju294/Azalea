import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LearningMaterial(Base):
    __tablename__ = "learning_materials"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    class_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("classes.id"),
        nullable=True,
    )

    study_path_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("study_paths.id"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[str] = mapped_column(String(50), nullable=False)

    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    azalea_class = relationship("AzaleaClass", back_populates="materials")
    study_path = relationship("StudyPath", back_populates="materials")

    chunks = relationship(
        "ContentChunk",
        back_populates="material",
        cascade="all, delete-orphan",
        order_by="ContentChunk.chunk_index",
    )
