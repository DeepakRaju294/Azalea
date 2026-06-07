from datetime import date, datetime, time, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.study_path import StudyPath
from app.models.topic import Topic
from app.schemas.home_recommendation import HomeRecommendationRead

router = APIRouter()


def get_user_id(current_user: dict[str, Any]) -> str:
    return str(current_user["user_id"])


def normalize_datetime(value):
    if value is None:
        return None

    if isinstance(value, datetime):
        normalized = value
    elif isinstance(value, date):
        normalized = datetime.combine(value, time.min)
    else:
        return None

    if normalized.tzinfo is None:
        normalized = normalized.replace(tzinfo=timezone.utc)

    return normalized


def get_topic_estimated_minutes(topic: Topic) -> int | None:
    if getattr(topic, "estimated_minutes", None) is not None:
        return topic.estimated_minutes

    if getattr(topic, "estimated_time_minutes", None) is not None:
        return topic.estimated_time_minutes

    return None


def get_topic_status(topic: Topic) -> str:
    if getattr(topic, "status", None):
        return topic.status

    if getattr(topic, "progress_status", None):
        return topic.progress_status

    return "not_started"


def get_review_due_at(topic: Topic):
    if getattr(topic, "review_due_at", None) is not None:
        return topic.review_due_at

    if getattr(topic, "review_due_date", None) is not None:
        return topic.review_due_date

    return None


def get_review_reason(topic: Topic) -> str | None:
    if getattr(topic, "review_reason", None):
        return topic.review_reason

    if getattr(topic, "review_due_reason", None):
        return topic.review_due_reason

    return None


def get_topic_weak_area(topic: Topic) -> bool:
    if getattr(topic, "has_weak_area", None):
        return True

    if getattr(topic, "weak_area_count", None):
        return topic.weak_area_count > 0

    if getattr(topic, "latest_mistake_type", None):
        return True

    return False


def get_topic_weak_area_reason(topic: Topic) -> str:
    if getattr(topic, "latest_mistake_type", None):
        return f"Recent practice showed a {topic.latest_mistake_type} mistake."

    if getattr(topic, "weak_area_summary", None):
        return topic.weak_area_summary

    return "Recent practice showed this topic may need more work."


def get_study_path_class(study_path: StudyPath):
    owned_classes = [
        azalea_class
        for azalea_class in getattr(study_path, "classes", [])
        if azalea_class.user_id == study_path.user_id
    ]

    if owned_classes:
        return owned_classes[0]

    if getattr(study_path, "azalea_classes", None):
        return study_path.azalea_classes[0]

    return None


def build_recommendation(
    *,
    recommendation_type: str,
    title: str,
    reason: str,
    topic: Topic,
    study_path: StudyPath,
) -> HomeRecommendationRead:
    azalea_class = get_study_path_class(study_path)

    review_due_at_raw = get_review_due_at(topic)
    review_due_at = normalize_datetime(review_due_at_raw)
    review_reason = get_review_reason(topic)

    return HomeRecommendationRead(
        type=recommendation_type,
        title=title,
        reason=reason,
        class_id=azalea_class.id if azalea_class else None,
        class_name=azalea_class.name if azalea_class else None,
        study_path_id=study_path.id,
        study_path_title=study_path.title,
        topic_id=topic.id,
        topic_title=topic.title,
        review_due_at=review_due_at.isoformat() if review_due_at else None,
        review_reason=review_reason,
        minutes_estimate=get_topic_estimated_minutes(topic),
    )


@router.get("/home", response_model=list[HomeRecommendationRead])
def get_home_recommendations(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    user_id = get_user_id(current_user)

    query = (
        db.query(Topic)
        .join(StudyPath, Topic.study_path_id == StudyPath.id)
        .filter(StudyPath.user_id == user_id)
    )

    if hasattr(Topic, "order_index"):
        query = query.order_by(Topic.order_index.asc())
    else:
        query = query.order_by(Topic.id.asc())

    topics = query.all()

    review_due_items: list[HomeRecommendationRead] = []
    weak_area_items: list[HomeRecommendationRead] = []
    in_progress_items: list[HomeRecommendationRead] = []
    not_started_items: list[HomeRecommendationRead] = []

    for topic in topics:
        study_path = getattr(topic, "study_path", None)

        if not study_path:
            study_path = (
                db.query(StudyPath)
                .filter(StudyPath.id == topic.study_path_id)
                .filter(StudyPath.user_id == user_id)
                .first()
            )

        if not study_path or study_path.user_id != user_id:
            continue

        status = get_topic_status(topic)
        review_due_at_raw = get_review_due_at(topic)
        review_due_at = normalize_datetime(review_due_at_raw)

        if review_due_at is not None and review_due_at <= now:
            review_due_items.append(
                build_recommendation(
                    recommendation_type="review_due",
                    title=f"Review {topic.title}",
                    reason=get_review_reason(topic)
                    or "This topic is due for a spaced review check.",
                    topic=topic,
                    study_path=study_path,
                )
            )
            continue

        if get_topic_weak_area(topic):
            weak_area_items.append(
                build_recommendation(
                    recommendation_type="weak_area",
                    title=f"Practice {topic.title}",
                    reason=get_topic_weak_area_reason(topic),
                    topic=topic,
                    study_path=study_path,
                )
            )
            continue

        if status == "in_progress":
            in_progress_items.append(
                build_recommendation(
                    recommendation_type="in_progress",
                    title=f"Continue {topic.title}",
                    reason="You already started this topic. Continue here to keep momentum.",
                    topic=topic,
                    study_path=study_path,
                )
            )
            continue

        if status == "not_started":
            not_started_items.append(
                build_recommendation(
                    recommendation_type="not_started",
                    title=f"Start {topic.title}",
                    reason="This is a recommended next topic in your study path.",
                    topic=topic,
                    study_path=study_path,
                )
            )

    recommendations: list[HomeRecommendationRead] = []

    recommendations.extend(review_due_items[:5])
    recommendations.extend(weak_area_items[:5])
    recommendations.extend(in_progress_items[:5])
    recommendations.extend(not_started_items[:5])

    return recommendations[:12]