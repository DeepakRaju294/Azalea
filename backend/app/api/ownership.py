from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.azalea_class import AzaleaClass
from app.models.lesson import Lesson
from app.models.learning_material import LearningMaterial
from app.models.study_path import StudyPath
from app.models.topic import Topic


def get_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user["user_id"])


def get_owned_class(
    class_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> AzaleaClass:
    azalea_class = (
        db.query(AzaleaClass)
        .filter(AzaleaClass.id == class_id)
        .filter(AzaleaClass.user_id == get_user_id(current_user))
        .first()
    )

    if not azalea_class:
        raise HTTPException(status_code=404, detail="Class not found.")

    return azalea_class


def get_owned_study_path(
    study_path_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> StudyPath:
    study_path = (
        db.query(StudyPath)
        .filter(StudyPath.id == study_path_id)
        .filter(StudyPath.user_id == get_user_id(current_user))
        .first()
    )

    if not study_path:
        raise HTTPException(status_code=404, detail="Study path not found.")

    return study_path


def get_owned_topic(
    topic_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> Topic:
    topic = db.query(Topic).filter(Topic.id == topic_id).first()

    if not topic or not topic.study_path:
        raise HTTPException(status_code=404, detail="Topic not found.")

    if topic.study_path.user_id != get_user_id(current_user):
        raise HTTPException(status_code=404, detail="Topic not found.")

    return topic


def get_owned_material(
    material_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> LearningMaterial:
    material = db.query(LearningMaterial).filter(LearningMaterial.id == material_id).first()

    if not material:
        raise HTTPException(status_code=404, detail="Material not found.")

    owns_class_material = (
        material.azalea_class is not None
        and material.azalea_class.user_id == get_user_id(current_user)
    )
    owns_study_path_material = (
        material.study_path is not None
        and material.study_path.user_id == get_user_id(current_user)
    )

    if not owns_class_material and not owns_study_path_material:
        raise HTTPException(status_code=404, detail="Material not found.")

    return material


def get_owned_lesson(
    lesson_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> Lesson:
    lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson or not lesson.topic or not lesson.topic.study_path:
        raise HTTPException(status_code=404, detail="Lesson not found.")

    if lesson.topic.study_path.user_id != get_user_id(current_user):
        raise HTTPException(status_code=404, detail="Lesson not found.")

    return lesson
