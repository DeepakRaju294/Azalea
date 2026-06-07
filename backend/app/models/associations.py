from sqlalchemy import Table, Column, ForeignKey, String
from app.db.base import Base

class_study_paths = Table(
    "class_study_paths",
    Base.metadata,
    Column("class_id", String, ForeignKey("classes.id"), primary_key=True),
    Column("study_path_id", String, ForeignKey("study_paths.id"), primary_key=True),
)