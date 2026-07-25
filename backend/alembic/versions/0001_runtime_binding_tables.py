"""runtime binding: sibling_exercise_claims, prepared_runtime_bindings, evidence_packages, delivery_evidence

Revision ID: 0001_runtime_binding
Revises:
Create Date: 2026-07-25

Creates ONLY the four Milestone C runtime-binding tables. Pre-existing Azalea tables are not referenced and
are left untouched, so this is safe to apply to a deployed database that predates Alembic. In such a database
run `alembic stamp head` is NOT appropriate (it would skip this revision); instead apply this revision
directly with `alembic upgrade head` — it only adds new tables.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_runtime_binding"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sibling_exercise_claims",
        sa.Column("claim_id", sa.String(), primary_key=True),
        sa.Column("claim_version", sa.Integer(), nullable=False),
        sa.Column("path_plan_version", sa.String(), nullable=False),
        sa.Column("concept_contract_id", sa.String(), nullable=False),
        sa.Column("variant", sa.String(), nullable=False),
        sa.Column("grammar_id", sa.String(), nullable=False),
        sa.Column("lesson_intent_kind", sa.String(), nullable=False),
        sa.Column("owner_topic_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("superseded_by_claim_id", sa.String(), nullable=True),
        sa.Column("lost_to_topic_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sibling_exercise_claims_path_plan_version", "sibling_exercise_claims", ["path_plan_version"])
    op.create_index(
        "uq_active_exercise_claim", "sibling_exercise_claims",
        ["path_plan_version", "concept_contract_id", "variant", "grammar_id", "lesson_intent_kind"],
        unique=True, postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "prepared_runtime_bindings",
        sa.Column("preparation_id", sa.String(), primary_key=True),
        sa.Column("topic_id", sa.String(), nullable=False),
        sa.Column("preparation_identity_digest", sa.String(), nullable=False),
        sa.Column("path_plan_version", sa.String(), nullable=False),
        sa.Column("sibling_claim_id", sa.String(), nullable=False),
        sa.Column("sibling_claim_version", sa.Integer(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("grammar_version", sa.Integer(), nullable=False),
        sa.Column("pedagogical_policy_version", sa.Integer(), nullable=False),
        sa.Column("resolution_registry_version", sa.Integer(), nullable=False),
        sa.Column("resolution_entry_version", sa.Integer(), nullable=False),
        sa.Column("binding_digest", sa.String(), nullable=False),
        sa.Column("execution_environment_digest", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("status_version", sa.Integer(), nullable=False),
        sa.Column("safety_block_version", sa.Integer(), nullable=False),
        sa.Column("superseded_by_preparation_id", sa.String(), nullable=True),
        sa.Column("active_evidence_id", sa.String(), nullable=True),
        sa.Column("failure_reason", sa.String(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_prepared_runtime_bindings_topic_id", "prepared_runtime_bindings", ["topic_id"])
    op.create_index("ix_prepared_runtime_bindings_identity", "prepared_runtime_bindings", ["preparation_identity_digest"])
    op.create_index(
        "uq_live_preparation_identity", "prepared_runtime_bindings", ["preparation_identity_digest"],
        unique=True, postgresql_where=sa.text("status IN ('preparing', 'ready')"),
    )

    op.create_table(
        "evidence_packages",
        sa.Column("evidence_id", sa.String(), primary_key=True),
        sa.Column("evidence_schema_version", sa.Integer(), nullable=False),
        sa.Column("evidence_digest", sa.String(), nullable=False),
        sa.Column("binding_digest", sa.String(), nullable=False),
        sa.Column("instance_digest", sa.String(), nullable=False),
        sa.Column("resolution_registry_version", sa.Integer(), nullable=False),
        sa.Column("resolution_entry_version", sa.Integer(), nullable=False),
        sa.Column("pedagogical_policy_version", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.String(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("verification_completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_evidence_packages_evidence_digest", "evidence_packages", ["evidence_digest"], unique=True)
    op.create_index("ix_evidence_packages_contract_id", "evidence_packages", ["contract_id"])

    op.create_table(
        "delivery_evidence",
        sa.Column("delivery_evidence_id", sa.String(), primary_key=True),
        sa.Column("evidence_id", sa.String(), sa.ForeignKey("evidence_packages.evidence_id"), nullable=False),
        sa.Column("evidence_digest", sa.String(), nullable=False),
        sa.Column("lesson_id", sa.String(), nullable=False),
        sa.Column("canonical_delivery_payload_digest", sa.String(), nullable=False),
        sa.Column("canonical_delivery_serialization_version", sa.Integer(), nullable=False),
        sa.Column("backend_sanitizer_version", sa.String(), nullable=False),
        sa.Column("structured_renderer_contract_version", sa.String(), nullable=False),
        sa.Column("narration_validator_version", sa.String(), nullable=False),
        sa.Column("narration_fidelity", sa.String(length=16), nullable=False),
        sa.Column("post_sanitization_validation_digest", sa.String(), nullable=False),
        sa.Column("card_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("evidence_id", "canonical_delivery_payload_digest", name="uq_delivery_payload"),
    )
    op.create_index("ix_delivery_evidence_evidence_id", "delivery_evidence", ["evidence_id"])
    op.create_index("ix_delivery_evidence_lesson_id", "delivery_evidence", ["lesson_id"])


def downgrade() -> None:
    op.drop_table("delivery_evidence")
    op.drop_table("evidence_packages")
    op.drop_table("prepared_runtime_bindings")
    op.drop_table("sibling_exercise_claims")
