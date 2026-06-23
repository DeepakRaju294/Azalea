import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.models.learner_concept_state import LearnerConceptState
from app.models.diagnostic_attempt import DiagnosticAttempt
from app.models.targeted_repair_attempt import TargetedRepairAttempt
from app.models.confusion_event import ConfusionEvent
from app.db.base import Base
from app.db.database import engine
from app.api.routes import (
    classes,
    health,
    lessons,
    lessons_v2,
    materials,
    study_paths,
    topics,
    practice,
    quick_practice,
    study_sessions,
    recommendations,
    learner_state,
)

Base.metadata.create_all(bind=engine)


def ensure_learning_material_scope_columns() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE learning_materials "
                "ADD COLUMN IF NOT EXISTS study_path_id VARCHAR"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE learning_materials "
                "ALTER COLUMN class_id DROP NOT NULL"
            )
        )


def ensure_quick_practice_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE quick_practice_attempts "
                "ADD COLUMN IF NOT EXISTS question_id VARCHAR"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE quick_practice_attempts "
                "ADD COLUMN IF NOT EXISTS question_type VARCHAR"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE quick_practice_attempts "
                "ADD COLUMN IF NOT EXISTS question_json JSONB"
            )
        )


def ensure_quick_practice_title_column() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE quick_practice_sessions "
                "ADD COLUMN IF NOT EXISTS title VARCHAR(255)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE quick_practice_sessions "
                "ADD COLUMN IF NOT EXISTS exact_problem BOOLEAN DEFAULT FALSE NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE quick_practice_questions "
                "ADD COLUMN IF NOT EXISTS hidden_test_cases JSONB"
            )
        )


def ensure_topic_course_type_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS course_type VARCHAR(80)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS secondary_course_types JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS knowledge_level INTEGER"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS practice_target TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS learner_outcome TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS assumed_prerequisites JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS in_scope JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS out_of_scope JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS practice_format VARCHAR(80)"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS difficulty_focus TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS boundary_reason TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS modifiers JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS source_coverage_notes TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS card_blueprint_hint JSONB"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS course_type_reason TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS visual_description TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE topics "
                "ADD COLUMN IF NOT EXISTS decomposition_metadata JSONB"
            )
        )


ensure_learning_material_scope_columns()
ensure_quick_practice_schema()
ensure_quick_practice_title_column()
ensure_topic_course_type_schema()


def ensure_targeted_repair_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS repair_level VARCHAR DEFAULT 'targeted_repair' NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS prior_repair_count INTEGER DEFAULT 0 NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_answer TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_correctness DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_reasoning_quality DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_feedback TEXT"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_completed BOOLEAN DEFAULT FALSE NOT NULL"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_confidence DOUBLE PRECISION"
            )
        )
        connection.execute(
            text(
                "ALTER TABLE targeted_repair_attempts "
                "ADD COLUMN IF NOT EXISTS follow_up_completed_at TIMESTAMPTZ"
            )
        )


ensure_targeted_repair_schema()


def ensure_lesson_generation_status_schema() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE lessons "
                "ADD COLUMN IF NOT EXISTS generation_status VARCHAR(20) "
                "NOT NULL DEFAULT 'ready'"
            )
        )


ensure_lesson_generation_status_schema()

app = FastAPI(title="Azalea API")


def _allowed_cors_origins() -> list[str]:
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    configured = os.getenv("CORS_ORIGINS", "")
    extra = [
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    ]
    return list(dict.fromkeys(defaults + extra))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(classes.router, prefix="/classes", tags=["Classes"])
app.include_router(study_paths.router, prefix="/study-paths", tags=["Study Paths"])
app.include_router(topics.router, tags=["Topics"])
app.include_router(lessons.router, tags=["Lessons"])
app.include_router(lessons_v2.router, tags=["Lessons V2"])
app.include_router(materials.router, tags=["Materials"])
app.include_router(practice.router, tags=["Practice"])
app.include_router(quick_practice.router)
app.include_router(study_sessions.router, prefix="/study-sessions", tags=["Study Sessions"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
app.include_router(learner_state.router, prefix="/learner-state", tags=["Learner State"])


@app.get("/")
def root():
    return {"message": "Azalea API is running"}
