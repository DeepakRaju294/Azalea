from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_user_id
from app.models.quick_practice import (
    QuickPracticeAttempt,
    QuickPracticeQuestion,
    QuickPracticeSession,
)
from app.schemas.practice import CodeRunResponse, PracticeHintResponse
from app.schemas.quick_practice import (
    QuickPracticeAttemptRead,
    QuickPracticeCodeRunRequest,
    QuickPracticeHintRequest,
    QuickPracticeQuestionRead,
    QuickPracticeQuestionSetRequest,
    QuickPracticeSessionCreate,
    QuickPracticeSessionRead,
    QuickPracticeSubmitRequest,
    QuickPracticeSubmitResponse,
)
from app.services.code_runner import run_code_against_tests
from app.services.llm_client import generate_title
from app.services.pdf_parser import extract_text_from_pdf_bytes
from app.services.practice_evaluator import (
    evaluate_practice_answer,
    generate_exact_problem_practice_question,
    generate_practice_hint,
    generate_quick_practice_question,
    generate_quick_practice_question_set,
)

router = APIRouter(prefix="/quick-practice", tags=["Quick Practice"])


def get_owned_quick_practice_session(
    session_id: str,
    db: Session,
    current_user: dict[str, Any],
) -> QuickPracticeSession:
    session = (
        db.query(QuickPracticeSession)
        .filter(QuickPracticeSession.id == session_id)
        .filter(QuickPracticeSession.user_id == get_user_id(current_user))
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Practice session not found.")

    return session


def build_session_context(session: QuickPracticeSession) -> str:
    parts = [
        f"Practice focus: {session.prompt}",
        (
            f"Uploaded source file: {session.source_filename}\n{session.source_text}"
            if session.source_text
            else "No uploaded source material."
        ),
    ]

    return "\n\n".join(parts)


def build_question_evaluation_context(
    session: QuickPracticeSession,
    question: QuickPracticeQuestion | None,
) -> str:
    context = build_session_context(session)

    if not question:
        return context

    question_parts = [
        context,
        "Saved question metadata:",
        f"Type: {question.question_type}",
        f"Topic: {question.topic or 'unknown'}",
        f"Skill target: {question.skill_target or 'unknown'}",
        f"Difficulty: {question.difficulty or 'unknown'}",
    ]

    if question.correct_answer:
        question_parts.append(f"Private answer key: {question.correct_answer}")

    if question.explanation:
        question_parts.append(f"Private explanation: {question.explanation}")

    if question.choices:
        question_parts.append(f"Choices: {question.choices}")

    if question.hidden_test_cases:
        question_parts.append(
            f"Hidden test count: {len(question.hidden_test_cases)}"
        )

    return "\n\n".join(question_parts)


def build_quick_practice_adaptive_response(evaluation: dict[str, Any]) -> dict[str, Any]:
    performance_level = evaluation.get("performance_level") or "weak"
    next_action = evaluation.get("next_action") or "minimal_repair"

    if performance_level == "strong":
        message = "Strong. Keep moving or try a harder mixed question."
        should_continue = True
        should_generate_repair = False
        suggested_mode = "continue"
    elif performance_level == "fragile":
        message = "Mostly there. Try one edge-case variation before counting this stable."
        should_continue = False
        should_generate_repair = False
        suggested_mode = "edge_case_check"
    elif performance_level == "minor_mistake":
        message = "Small miss. Do a targeted follow-up to fix the detail."
        should_continue = False
        should_generate_repair = True
        suggested_mode = "targeted_follow_up"
    else:
        message = "This needs a minimal repair before more practice."
        should_continue = False
        should_generate_repair = True
        suggested_mode = "minimal_repair"

    return {
        "message": message,
        "performance_level": performance_level,
        "next_action": next_action,
        "suggested_mode": suggested_mode,
        "should_continue": should_continue,
        "should_generate_repair": should_generate_repair,
        "concept_to_review": evaluation.get("mistake_type"),
        "follow_up_question": evaluation.get("follow_up_question"),
    }


def build_attempt_context(attempts: list[QuickPracticeAttempt]) -> str:
    if not attempts:
        return ""

    lines: list[str] = []

    for attempt in attempts[:5]:
        lines.append(
            "\n".join(
                [
                    f"Question: {attempt.question}",
                    f"Answer: {attempt.user_answer}",
                    f"Performance: {attempt.performance_level or 'unknown'}",
                    f"Mistake: {attempt.mistake_type or 'none'}",
                    f"Feedback: {attempt.feedback or 'none'}",
                ]
            )
        )

    return "\n\n".join(lines)


def get_owned_quick_practice_question(
    question_id: str,
    session: QuickPracticeSession,
    db: Session,
) -> QuickPracticeQuestion:
    question = (
        db.query(QuickPracticeQuestion)
        .filter(QuickPracticeQuestion.id == question_id)
        .filter(QuickPracticeQuestion.session_id == session.id)
        .first()
    )

    if not question:
        raise HTTPException(status_code=404, detail="Practice question not found.")

    return question


def question_to_snapshot(question: QuickPracticeQuestion) -> dict[str, Any]:
    return {
        "id": question.id,
        "question_type": question.question_type,
        "topic": question.topic,
        "skill_target": question.skill_target,
        "difficulty": question.difficulty,
        "question_text": question.question_text,
        "choices": question.choices or [],
        "given": question.given or [],
        "starter_code": question.starter_code,
        "language": question.language,
        "test_cases": question.test_cases or [],
        "source_reference": question.source_reference,
    }


def create_question_from_result(
    session: QuickPracticeSession,
    result: dict[str, Any],
    order_index: int,
) -> QuickPracticeQuestion:
    return QuickPracticeQuestion(
        session_id=session.id,
        question_type=result["question_type"],
        topic=result["topic"],
        skill_target=result["skill_target"],
        difficulty=result["difficulty"],
        question_text=result["question_text"],
        choices=result["choices"],
        given=result["given"],
        starter_code=result["starter_code"],
        language=result["language"],
        test_cases=result["test_cases"],
        hidden_test_cases=result.get("hidden_test_cases") or [],
        correct_answer=result["correct_answer"],
        explanation=result["explanation"],
        source_reference=result["source_reference"] or session.source_filename,
        reason=result["reason"],
        order_index=order_index,
    )


@router.post("/", response_model=QuickPracticeSessionRead)
def create_quick_practice_session(
    payload: QuickPracticeSessionCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    if not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="Practice prompt cannot be empty.")

    title = generate_title(payload.prompt.strip())

    session = QuickPracticeSession(
        user_id=get_user_id(current_user),
        prompt=payload.prompt.strip(),
        title=title,
        exact_problem=payload.exact_problem,
    )

    db.add(session)
    db.flush()

    if payload.exact_problem:
        result = generate_exact_problem_practice_question(payload.prompt.strip())
        question = create_question_from_result(
            session=session,
            result=result,
            order_index=1,
        )
        session.current_question = result["question_text"]
        db.add(question)

    db.commit()
    db.refresh(session)

    return session


@router.get("/", response_model=list[QuickPracticeSessionRead])
def list_quick_practice_sessions(
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return (
        db.query(QuickPracticeSession)
        .filter(QuickPracticeSession.user_id == get_user_id(current_user))
        .order_by(QuickPracticeSession.created_at.desc())
        .limit(30)
        .all()
    )


@router.get("/{session_id}", response_model=QuickPracticeSessionRead)
def get_quick_practice_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    return get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )


@router.post("/{session_id}/materials/pdf", response_model=QuickPracticeSessionRead)
async def upload_quick_practice_pdf(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    extracted_text = extract_text_from_pdf_bytes(file_bytes)

    if not extracted_text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF.")

    session.source_text = extracted_text
    session.source_filename = file.filename

    db.commit()
    db.refresh(session)

    return session


@router.get("/{session_id}/questions", response_model=list[QuickPracticeQuestionRead])
def list_quick_practice_questions(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    return (
        db.query(QuickPracticeQuestion)
        .filter(QuickPracticeQuestion.session_id == session.id)
        .order_by(QuickPracticeQuestion.order_index.asc())
        .limit(30)
        .all()
    )


@router.get(
    "/{session_id}/questions/{question_id}",
    response_model=QuickPracticeQuestionRead,
)
def get_quick_practice_question(
    session_id: str,
    question_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    return get_owned_quick_practice_question(
        question_id=question_id,
        session=session,
        db=db,
    )


@router.post("/{session_id}/question", response_model=QuickPracticeQuestionRead)
def create_quick_practice_question(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    attempts = (
        db.query(QuickPracticeAttempt)
        .filter(QuickPracticeAttempt.session_id == session.id)
        .order_by(QuickPracticeAttempt.created_at.desc())
        .limit(5)
        .all()
    )

    result = generate_quick_practice_question(
        prompt=session.prompt,
        source_text=session.source_text,
        previous_attempts_context=build_attempt_context(attempts),
    )

    existing_question_count = (
        db.query(QuickPracticeQuestion)
        .filter(QuickPracticeQuestion.session_id == session.id)
        .count()
    )

    question = create_question_from_result(
        session=session,
        result=result,
        order_index=existing_question_count + 1,
    )

    session.current_question = result["question_text"]
    db.add(question)
    db.commit()
    db.refresh(question)

    return question


@router.post(
    "/{session_id}/questions/generate-set",
    response_model=list[QuickPracticeQuestionRead],
)
def create_quick_practice_question_set(
    session_id: str,
    payload: QuickPracticeQuestionSetRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    if payload.replace_existing:
        (
            db.query(QuickPracticeQuestion)
            .filter(QuickPracticeQuestion.session_id == session.id)
            .delete(synchronize_session=False)
        )
        db.flush()

    existing_question_count = (
        db.query(QuickPracticeQuestion)
        .filter(QuickPracticeQuestion.session_id == session.id)
        .count()
    )

    results = generate_quick_practice_question_set(
        prompt=session.prompt,
        source_text=session.source_text,
        count=payload.count,
    )

    if not results:
        raise HTTPException(
            status_code=400,
            detail="No practice questions could be generated from this session.",
        )

    questions = [
        create_question_from_result(
            session=session,
            result=result,
            order_index=existing_question_count + index + 1,
        )
        for index, result in enumerate(results)
    ]

    session.current_question = questions[0].question_text
    db.add_all(questions)
    db.commit()

    for question in questions:
        db.refresh(question)

    return questions


@router.post("/{session_id}/hint", response_model=PracticeHintResponse)
def create_quick_practice_hint(
    session_id: str,
    payload: QuickPracticeHintRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )
    question_text = payload.question

    if payload.question_id:
        question = get_owned_quick_practice_question(
            question_id=payload.question_id,
            session=session,
            db=db,
        )
        question_text = question.question_text

    if not question_text:
        raise HTTPException(status_code=400, detail="Question is required.")

    return generate_practice_hint(
        question=question_text,
        user_partial_answer=payload.user_partial_answer,
        lesson_context=build_session_context(session),
    )


@router.post("/{session_id}/run-code", response_model=CodeRunResponse)
def run_quick_practice_code(
    session_id: str,
    payload: QuickPracticeCodeRunRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    if not payload.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")

    question = None
    visible_cases = payload.test_cases
    hidden_cases: list[dict[str, Any]] = []

    if payload.question_id:
        question = get_owned_quick_practice_question(
            question_id=payload.question_id,
            session=session,
            db=db,
        )
        visible_cases = question.test_cases or []
        hidden_cases = question.hidden_test_cases or []

    visible_result = run_code_against_tests(
        code=payload.code,
        language=payload.language or (question.language if question else None),
        test_cases=visible_cases,
    )
    hidden_result = (
        run_code_against_tests(
            code=payload.code,
            language=payload.language or (question.language if question else None),
            test_cases=hidden_cases,
        )
        if hidden_cases
        else {
            "passed": 0,
            "total": 0,
            "all_passed": True,
            "error": None,
            "cases": [],
        }
    )

    visible_error = visible_result.get("error")
    hidden_error = hidden_result.get("error")
    error = visible_error or hidden_error
    passed = int(visible_result["passed"]) + int(hidden_result["passed"])
    total = int(visible_result["total"]) + int(hidden_result["total"])

    return {
        "language": visible_result["language"],
        "passed": passed,
        "total": total,
        "all_passed": total > 0 and passed == total and not error,
        "error": error,
        "hidden_passed": hidden_result["passed"],
        "hidden_total": hidden_result["total"],
        "cases": visible_result["cases"],
    }


@router.post("/{session_id}/submit", response_model=QuickPracticeSubmitResponse)
def submit_quick_practice_answer(
    session_id: str,
    payload: QuickPracticeSubmitRequest,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    if not payload.user_answer.strip():
        raise HTTPException(status_code=400, detail="Answer cannot be empty.")

    question = None
    question_text = payload.question

    if payload.question_id:
        question = get_owned_quick_practice_question(
            question_id=payload.question_id,
            session=session,
            db=db,
        )
        question_text = question.question_text

    if not question_text:
        raise HTTPException(status_code=400, detail="Question is required.")

    evaluation = evaluate_practice_answer(
        question=question_text,
        user_answer=payload.user_answer,
        lesson_context=build_question_evaluation_context(session, question),
        hint_used=payload.hint_used,
    )
    adaptive_response = build_quick_practice_adaptive_response(evaluation)

    attempt = QuickPracticeAttempt(
        session_id=session.id,
        question_id=question.id if question else None,
        question=question_text,
        question_type=question.question_type if question else None,
        question_json=question_to_snapshot(question) if question else None,
        user_answer=payload.user_answer,
        is_correct=evaluation["is_correct"],
        performance_level=evaluation["performance_level"],
        mistake_type=evaluation["mistake_type"],
        feedback=evaluation["feedback"],
        hint_used=payload.hint_used,
        follow_up_question=evaluation["follow_up_question"],
        next_action=evaluation["next_action"],
    )

    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return QuickPracticeSubmitResponse(
        attempt_id=attempt.id,
        is_correct=attempt.is_correct,
        performance_level=attempt.performance_level,
        mistake_type=attempt.mistake_type,
        feedback=attempt.feedback,
        follow_up_question=attempt.follow_up_question,
        next_action=attempt.next_action,
        adaptive_response=adaptive_response,
        created_at=attempt.created_at,
    )


@router.get("/{session_id}/attempts", response_model=list[QuickPracticeAttemptRead])
def list_quick_practice_attempts(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    session = get_owned_quick_practice_session(
        session_id=session_id,
        db=db,
        current_user=current_user,
    )

    return (
        db.query(QuickPracticeAttempt)
        .filter(QuickPracticeAttempt.session_id == session.id)
        .order_by(QuickPracticeAttempt.created_at.desc())
        .limit(30)
        .all()
    )
