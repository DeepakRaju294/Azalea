def build_adaptive_lesson_instruction(
    starting_mode: str | None,
    explanation_density: str | None = None,
    estimated_state: str | None = None,
    adaptation_note: str | None = None,
    fragile_concepts: list[str] | None = None,
    review_concepts: list[str] | None = None,
    stable_concepts: list[str] | None = None,
    transferable_concepts: list[str] | None = None,
    concepts_to_skip: list[str] | None = None,
    concepts_to_briefly_repair: list[str] | None = None,
    memory_guidance: str | None = None,
    cross_topic_memory_context: str | None = None,
) -> str:
    fragile_concepts = fragile_concepts or []
    review_concepts = review_concepts or []
    stable_concepts = stable_concepts or []
    transferable_concepts = transferable_concepts or []
    concepts_to_skip = concepts_to_skip or []
    concepts_to_briefly_repair = concepts_to_briefly_repair or []

    mode = starting_mode or "full_teach"

    mode_rules = {
        "full_teach": """
The learner chose to be taught from scratch.
Generate a complete, self-contained lesson.
Define all important terms before using them.
Use intuition, components, process, examples, edge cases, and practice.
Do not assume prior knowledge except for stable cross-topic memory explicitly listed below.
""",
        "compressed_refresher": """
The learner has seen this before but may have gaps.
Start with a compressed refresher, not a full reteach.
Only expand on prerequisites or terms that are necessary.
Move quickly into examples and short checks.
Avoid long beginner explanations unless the concept is essential.
""",
        "nuance_first": """
The learner mostly knows this topic.
Skip obvious basics.
Focus on nuance, common mistakes, limitations, edge cases, and transfer.
Use short reminders instead of full explanations.
Include practice that exposes shaky understanding.
""",
        "edge_cases": """
The learner wants reinforcement through tricky cases.
Begin with common mistakes, exceptions, limitations, and edge cases.
Keep foundational explanation minimal.
Use examples that reveal subtle misunderstandings.
""",
        "transfer_practice": """
The learner is comfortable and wants application.
Keep teaching very brief.
Prioritize transfer questions, applied examples, and harder practice.
Only explain after a practice item reveals a gap.
""",
    }

    def bullet_list(items: list[str]) -> str:
        if not items:
            return "- none"
        return "\n".join(f"- {item}" for item in items[:12])

    return f"""
ADAPTIVE LESSON GENERATION MODE

Starting mode: {mode}
Estimated learner state: {estimated_state or "not provided"}
Explanation density: {explanation_density or "not provided"}
Adaptation note: {adaptation_note or "not provided"}

{mode_rules.get(mode, mode_rules["full_teach"])}

Important Azalea rule:
Teach exactly what is needed — not more, not less.
Adaptive feedback must obey the TopicScopeContract. Feedback can change depth, visuals, examples, wording, or practice, but it cannot add out-of-scope sibling or parent topics unless the user explicitly changes the topic.

Cross-topic learner memory:
{cross_topic_memory_context or "No cross-topic memory context was provided."}

Stable concepts:
{bullet_list(stable_concepts)}

Transferable concepts:
{bullet_list(transferable_concepts)}

Concepts to avoid reteaching unless they are required anchors:
{bullet_list(concepts_to_skip)}

Concepts to briefly repair only if needed:
{bullet_list(concepts_to_briefly_repair)}

Current-topic fragile concepts:
{bullet_list(fragile_concepts)}

Concepts due for review:
{bullet_list(review_concepts)}

Memory guidance:
{memory_guidance or "No memory guidance provided."}

Do:
- Build directly from stable and transferable concepts when relevant.
- Briefly reference known concepts instead of reteaching them.
- If a stable concept is needed, use it as an anchor.
- If a fragile concept is needed, repair only the smallest missing piece.
- Keep every topic self-contained enough that no term is undefined.
- Include micro-checks naturally through examples/practice.
- Prefer transfer/application when the learner has transferable prior concepts.
- Make the learner feel like Azalea remembers what they already know.
- Apply the course-type blueprint at the learner's actual level, not the generic full lesson every time.
- For higher starting modes, remove broad context, basic definitions, obvious components, slow normal-case walkthroughs, repeated prerequisite explanation, excessive microchecks, and easy practice.
- For higher starting modes, add harder examples, edge cases, misconception checks, transfer questions, invalid-solution/debugging checks, mixed review, and nuanced multiple choice when relevant.
- Never reduce explanation for the new idea currently being taught; only compress already-known prerequisites, obvious context, mastered review concepts, or repeated basics.
- Do not start with a diagnostic unless the learner requested a diagnostic/test-first flow.
- If the user asks for more detail, add detail only to in-scope content.
- If the user asks for simpler explanation, add prerequisite support without expanding out-of-scope content.
- If the user asks for more examples, add examples for in-scope cases only.
- If the user asks for implementation, add a Coding Implementation continuation only when the current scope or user request allows it.
- If the user asks to deeply learn a prerequisite, create/open a prerequisite mini-path rather than bloating the current topic.

Do not:
- Reteach the entire prerequisite chain if learner memory shows stable knowledge.
- Assume fragile concepts are mastered.
- Ignore cross-topic memory when it is relevant.
- Add advanced material unrelated to the uploaded source.
- Use grading language.
- Say the learner failed.
- Over-explain obvious parts for higher starting modes.
- Generate the same card sequence for all knowledge levels when the learner state implies a different path.
- Use adaptive feedback to teach parent concepts, sibling operations, or prerequisite chains that the current TopicScopeContract excludes.
""".strip()
