from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.api.ownership import get_owned_class, get_owned_material, get_owned_study_path
from app.models.content_chunk import ContentChunk
from app.models.learning_material import LearningMaterial
from app.schemas.content_chunk import ContentChunkRead
from app.schemas.learning_material import LearningMaterialRead, TextMaterialCreate
from app.services.chunker import chunk_text
from app.services.pdf_parser import extract_text_from_pdf_bytes

router = APIRouter()


def create_material_with_chunks(
    db: Session,
    title: str,
    material_type: str,
    raw_text: str,
    class_id: str | None = None,
    study_path_id: str | None = None,
    filename: str | None = None,
) -> LearningMaterial:
    if class_id is None and study_path_id is None:
        raise HTTPException(
            status_code=400,
            detail="Material must be attached to a class or study path.",
        )

    material = LearningMaterial(
        class_id=class_id,
        study_path_id=study_path_id,
        title=title,
        material_type=material_type,
        filename=filename,
        raw_text=raw_text,
    )

    db.add(material)
    db.flush()

    chunks = chunk_text(raw_text)

    for index, chunk in enumerate(chunks):
        db.add(
            ContentChunk(
                material_id=material.id,
                chunk_index=index,
                text=chunk,
            )
        )

    db.commit()
    db.refresh(material)

    return material


@router.post(
    "/classes/{class_id}/materials/pdf",
    response_model=LearningMaterialRead,
)
async def upload_pdf_material(
    class_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()
    extracted_text = extract_text_from_pdf_bytes(file_bytes)

    if not extracted_text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    title = file.filename or "Uploaded PDF"

    material = create_material_with_chunks(
        db=db,
        title=title,
        material_type="pdf",
        raw_text=extracted_text,
        class_id=class_id,
        filename=file.filename,
    )

    return material


@router.post(
    "/classes/{class_id}/materials/text",
    response_model=LearningMaterialRead,
)
def create_text_material(
    class_id: str,
    payload: TextMaterialCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    material = create_material_with_chunks(
        db=db,
        title=payload.title,
        material_type="text",
        raw_text=payload.text,
        class_id=class_id,
        filename=None,
    )

    return material


@router.get(
    "/classes/{class_id}/materials",
    response_model=list[LearningMaterialRead],
)
def list_class_materials(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_class(class_id=class_id, db=db, current_user=current_user)

    return (
        db.query(LearningMaterial)
        .filter(LearningMaterial.class_id == class_id)
        .order_by(LearningMaterial.created_at.desc())
        .all()
    )


@router.post(
    "/study-paths/{study_path_id}/materials/pdf",
    response_model=LearningMaterialRead,
)
async def upload_study_path_pdf_material(
    study_path_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()
    extracted_text = extract_text_from_pdf_bytes(file_bytes)

    if not extracted_text:
        raise HTTPException(status_code=400, detail="No extractable text found in PDF")

    material = create_material_with_chunks(
        db=db,
        title=file.filename or "Uploaded PDF",
        material_type="pdf",
        raw_text=extracted_text,
        study_path_id=study_path_id,
        filename=file.filename,
    )

    return material


@router.post(
    "/study-paths/{study_path_id}/materials/text",
    response_model=LearningMaterialRead,
)
def create_study_path_text_material(
    study_path_id: str,
    payload: TextMaterialCreate,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    material = create_material_with_chunks(
        db=db,
        title=payload.title,
        material_type="text",
        raw_text=payload.text,
        study_path_id=study_path_id,
        filename=None,
    )

    return material


@router.get(
    "/study-paths/{study_path_id}/materials",
    response_model=list[LearningMaterialRead],
)
def list_study_path_materials(
    study_path_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_study_path(
        study_path_id=study_path_id,
        db=db,
        current_user=current_user,
    )

    return (
        db.query(LearningMaterial)
        .filter(LearningMaterial.study_path_id == study_path_id)
        .order_by(LearningMaterial.created_at.desc())
        .all()
    )


@router.get(
    "/materials/{material_id}/chunks",
    response_model=list[ContentChunkRead],
)
def list_material_chunks(
    material_id: str,
    db: Session = Depends(get_db),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    get_owned_material(material_id=material_id, db=db, current_user=current_user)

    return (
        db.query(ContentChunk)
        .filter(ContentChunk.material_id == material_id)
        .order_by(ContentChunk.chunk_index.asc())
        .all()
    )
