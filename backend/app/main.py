import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env FIRST, before any app module imports (routes/services read model & flag config at import).
# override=True so backend/.env is AUTHORITATIVE over any stale OPENAI_*/AZALEA_* vars left in the shell/OS
# environment (a common cause of 'restarts don't change the model' — load_dotenv defaults to override=False,
# so a stale exported OPENAI_MODEL/OPENAI_MODEL_CONTENT would otherwise win and every call fell back to it).
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

_gf_model = os.getenv("OPENAI_MODEL_CALL_WORKED_EXAMPLE_GF") or os.getenv("OPENAI_MODEL_CONTENT") or os.getenv("OPENAI_MODEL")
print(f"[startup] pid={os.getpid()} backend/.env loaded — worked_example model={_gf_model!r}, "
      f"reasoning_planning={os.getenv('OPENAI_REASONING_PLANNING')!r}, "
      f"retrieval_grounding={os.getenv('AZALEA_RETRIEVAL_GROUNDED_EXAMPLES')!r}", flush=True)

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
    preferences,
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


def ensure_study_path_language_column() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE study_paths "
                "ADD COLUMN IF NOT EXISTS language VARCHAR(32) NOT NULL DEFAULT 'python'"
            )
        )


def ensure_study_path_domain_columns() -> None:
    # Phase-0 domain routing (DOMAIN_ROUTING_AND_TOPIC_GATE_SPEC §3). No alembic in this repo — idempotent ALTER.
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE study_paths ADD COLUMN IF NOT EXISTS domain VARCHAR(40)")
        )
        connection.execute(
            text("ALTER TABLE study_paths ADD COLUMN IF NOT EXISTS domain_provenance JSONB")
        )
        connection.execute(
            text(
                "ALTER TABLE study_paths "
                "ADD COLUMN IF NOT EXISTS classification_status VARCHAR(20) "
                "NOT NULL DEFAULT 'pending'"
            )
        )
        # Phase-1 (D1): pointer to the active immutable StudyPathGeneration snapshot.
        connection.execute(
            text("ALTER TABLE study_paths ADD COLUMN IF NOT EXISTS active_generation_id VARCHAR")
        )
        # Phase-1 (§3): the per-path preference override the learner confirmed in onboarding.
        connection.execute(
            text("ALTER TABLE study_paths ADD COLUMN IF NOT EXISTS selected_preferences JSONB")
        )


def ensure_prereq_link_columns() -> None:
    # PREREQ_LINKS_SPEC §1.4/§4: provenance + operational idempotency for a path created from an
    # open_study_path prerequisite link. No alembic in this repo — idempotent additive ALTERs.
    with engine.begin() as connection:
        for col, ddl in (
            ("origin_path_id", "VARCHAR"),
            ("origin_topic_id", "VARCHAR"),
            ("origin_card_id", "VARCHAR"),
            ("origin_link_text", "TEXT"),
            ("origin_concept_id", "VARCHAR"),
            ("creation_source", "VARCHAR(40) NOT NULL DEFAULT 'user_goal'"),
            ("creation_request_id", "VARCHAR"),
            ("prerequisite_lineage_concept_ids", "JSONB"),
            ("generation_status", "VARCHAR(20) NOT NULL DEFAULT 'complete'"),
        ):
            connection.execute(
                text(f"ALTER TABLE study_paths ADD COLUMN IF NOT EXISTS {col} {ddl}")
            )
        # §4: one path per (user, request_id) — partial so existing NULL rows never collide. This is the
        # operational-idempotency guard (a double-click / retry returns the existing path, never a 2nd).
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_study_paths_user_creation_request "
                "ON study_paths (user_id, creation_request_id) WHERE creation_request_id IS NOT NULL"
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
ensure_study_path_language_column()
ensure_study_path_domain_columns()
ensure_prereq_link_columns()
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
app.include_router(preferences.router, prefix="/preferences", tags=["Preferences"])


@app.get("/")
def root():
    return {"message": "Azalea API is running"}
