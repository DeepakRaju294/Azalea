from enum import Enum


class TopicType(str, Enum):
    CONCEPT_INTUITION = "concept_intuition"
    TERMINOLOGY_COMPONENTS = "terminology_components"
    PROCESS_WALKTHROUGH = "process_walkthrough"
    ALGORITHM_WALKTHROUGH = "algorithm_walkthrough"
    DATA_STRUCTURE_OPERATION = "data_structure_operation"
    CODING_IMPLEMENTATION = "coding_implementation"
    MATH_FORMULA_METHOD = "math_formula_method"
    PROOF_REASONING = "proof_reasoning"
    COMPARE_DISTINGUISH = "compare_distinguish"
    PROBLEM_SOLVING_APPLICATION = "problem_solving_application"
    SCIENCE_MECHANISM = "science_mechanism"
    STUDY_PATH_INTRODUCTION = "study_path_introduction"

    # Backward-compatible aliases used by older prompt/classifier/validator code.
    MATH_PROOF_REASONING = "math_formula_method"
    COMPARE_DECIDE = "compare_distinguish"
    PROBLEM_SOLVING_PATTERN = "problem_solving_application"
    SYSTEM_WORKFLOW_DEBUGGING = "process_walkthrough"
    APPLICATION_HISTORICAL = "problem_solving_application"
    REVIEW_REFRESH = "problem_solving_application"
    SYSTEM_ARCHITECTURE = "process_walkthrough"
    DEBUGGING_DIAGNOSIS = "process_walkthrough"
    TOOL_WORKFLOW = "process_walkthrough"
    DESIGN_DECISION = "compare_distinguish"
    CASE_STUDY_APPLICATION = "problem_solving_application"
    HISTORICAL_DEVELOPMENT = "problem_solving_application"
    PROCESS_LIFECYCLE = "process_walkthrough"
    TERMINOLOGY_VOCABULARY = "terminology_components"
    EXAM_INTERVIEW_PREP = "problem_solving_application"


# Compatibility alias while the rest of the backend is migrated.
CourseType = TopicType
