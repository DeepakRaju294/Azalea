"""Milestone C unit 10d — persistence layer (Alembic + 4 models). Offline: validates the models are
registered on Base.metadata with the required columns and the single-active partial unique indexes, and that
the initial migration exposes upgrade/downgrade. Does NOT connect to a database."""

import importlib
import os
import unittest

os.environ.setdefault("OPENAI_API_KEY", "dummy")
os.environ.setdefault("DATABASE_URL", "postgresql://u:p@localhost/x")

from app.db.base import Base


class PersistenceModels(unittest.TestCase):
    def test_four_tables_registered(self):
        need = {"sibling_exercise_claims", "prepared_runtime_bindings", "evidence_packages", "delivery_evidence"}
        self.assertTrue(need <= set(Base.metadata.tables))

    def test_evidence_package_key_columns(self):
        cols = set(Base.metadata.tables["evidence_packages"].columns.keys())
        self.assertTrue({"evidence_id", "evidence_digest", "payload", "verification_completed_at"} <= cols)

    def test_single_active_claim_partial_index(self):
        idx = {i.name: i for i in Base.metadata.tables["sibling_exercise_claims"].indexes}
        self.assertIn("uq_active_exercise_claim", idx)
        self.assertTrue(idx["uq_active_exercise_claim"].unique)

    def test_single_live_preparation_partial_index(self):
        idx = {i.name: i for i in Base.metadata.tables["prepared_runtime_bindings"].indexes}
        self.assertIn("uq_live_preparation_identity", idx)
        self.assertTrue(idx["uq_live_preparation_identity"].unique)

    def test_delivery_evidence_foreign_key_to_evidence(self):
        fks = Base.metadata.tables["delivery_evidence"].foreign_keys
        self.assertTrue(any(fk.column.table.name == "evidence_packages" for fk in fks))

    def test_initial_migration_has_upgrade_downgrade(self):
        mod = importlib.import_module("alembic.versions.0001_runtime_binding_tables") if False else None
        # import by file path (module name starts with a digit)
        import importlib.util
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0001_runtime_binding_tables.py"
        spec = importlib.util.spec_from_file_location("rb_migration_0001", path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
        self.assertEqual(mig.revision, "0001_runtime_binding")
        self.assertIsNone(mig.down_revision)
        self.assertTrue(callable(mig.upgrade) and callable(mig.downgrade))


if __name__ == "__main__":
    unittest.main()
