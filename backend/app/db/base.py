from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.associations import class_study_paths  
from app.models.azalea_class import AzaleaClass 
from app.models.study_path import StudyPath  
from app.models.topic import Topic  
from app.models.lesson import Lesson  
from app.models.learning_material import LearningMaterial  
from app.models.content_chunk import ContentChunk  
from app.models.practice_attempt import PracticeAttempt
from app.models.study_session import StudySession
from app.models.quick_practice import QuickPracticeAttempt, QuickPracticeQuestion, QuickPracticeSession
