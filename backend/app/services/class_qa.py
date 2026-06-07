from typing import Any

from app.models.content_chunk import ContentChunk
from app.services.llm_client import generate_class_qa_response


SYSTEM_PROMPT = """
You are Azalea, an AI study assistant.

Answer student questions using only the provided class material.

Rules:
- Stay grounded in the provided source chunks.
- If the material does not contain enough information, say what is missing.
- Explain clearly and simply.
- Do not invent unsupported details.
- Cite source numbers naturally in the answer when useful.
- Return only valid JSON.
"""


def answer_class_question(
    question: str,
    chunks: list[ContentChunk],
) -> dict[str, Any]:
    source_text = ""

    for source_number, chunk in enumerate(chunks, start=1):
        material_title = chunk.material.title if chunk.material else "Unknown material"
        material_filename = chunk.material.filename if chunk.material else None

        source_text += f"""
--- SOURCE {source_number} ---
Material: {material_title}
Filename: {material_filename or "No filename"}
Material id: {chunk.material_id}
Chunk id: {chunk.id}
Chunk index: {chunk.chunk_index}

{chunk.text}
"""

    user_prompt = f"""
Student question:
{question}

Class source material:
{source_text}

Return JSON with this exact structure:
{{
  "answer": "A clear answer grounded in the source material.",
  "used_chunk_indexes": [1, 2]
}}

Rules:
- used_chunk_indexes should contain the SOURCE numbers that were most relevant, not the Chunk index values.
- If no source chunk answers the question, use an empty list and explain what is missing.
"""

    data = generate_class_qa_response(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    return {
        "answer": data.get("answer", ""),
        "used_chunk_indexes": data.get("used_chunk_indexes", []),
    }
