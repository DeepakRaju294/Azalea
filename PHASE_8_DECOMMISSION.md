# Phase 8 - Legacy Decommission Plan

Status: **Phase 7 cutover in progress**. Nothing is being removed today. Normal study-path launch now routes to v2 by default, while legacy remains available through explicit opt-out switches.

Last updated: 2026-06-04

## Decommission Criteria

All of the following must be true before any legacy file below is actually deleted:

1. Normal study-path launch uses `/learn-v2` by default. This is currently true for landing-page launch/generate flows; legacy remains available with `?v=1` on frontend routes or `?use_v2=false` on backend generation endpoints.
2. No active study path in the database has a `lesson_json` with `lesson_version != 2` and `generation_status == "ready"`. Old lessons can stay readable through the legacy route during the migration window.
3. At least 30 calendar days have passed since the cutover with no rollback.
4. The v2 compiler contract tests, frontend typecheck/lint, and future v2 smoke/snapshot tests pass on each PR for those 30 days.
5. Error rate on v2 generation is less than or equal to the legacy generation baseline.

## Current Cutover Wiring

- Normal landing-page launch goes to `/learn-v2?topic=<topic_id>` unless the page URL has `?v=1`.
- Direct visits to `/learn` redirect to `/learn-v2` unless the URL has `?v=1`.
- `POST /study-paths/{id}/generate-initial` generates v2 by default. Use `?use_v2=false` for legacy.
- `POST /study-paths/{id}/regenerate` generates v2 by default. Use `?use_v2=false` for legacy.
- `POST /lessons-v2/topics/{id}/generate` writes the compiled v2 lesson into the normal `lessons` table, so `/learn-v2` can reuse cached v2 lessons instead of regenerating on every open.

## Rollback Plan

If the v2 pipeline needs to be rolled back during Phase 7 or Phase 8 prep:

1. In `backend/venv/app/api/routes/study_paths.py`, set `use_v2: bool = False` on:
   - `generate_initial_study_path_content`
   - `regenerate_study_path`
2. In `frontend/app/study-paths/[studyPathId]/page.tsx`, change launch/generate calls to pass `useV2: false`, or visit the landing page with `?v=1`.
3. In `frontend/app/study-paths/[studyPathId]/learn/page.tsx`, remove or disable the Phase 7 redirect `useEffect` near the top of `StudyPathLearnPage`.
4. Stored v2 lessons remain readable via `/learn-v2`; no schema migration is required.

No data is destroyed during cutover. Legacy lessons remain in the `lessons` table with `lesson_version=1` and remain readable through `/learn?v=1` until the legacy route is actually removed.

## Slated For Removal After Stability Window

### Backend

| File | Role |
|---|---|
| `backend/venv/app/services/lean_lesson_generator.py` | Legacy generator: `build_lean_lesson_from_topic_and_chunks`, legacy materializers, and repair passes |
| `backend/venv/app/prompts/lean_lesson_prompt.py` | Legacy lean lesson prompt |
| `backend/venv/app/services/lesson_generator.py` | Older adaptive lesson generator |
| `backend/venv/app/schemas/lesson_cards.py` | Legacy `LessonFlowCard` schema |
| `backend/venv/app/services/llm_client.py` legacy schema blocks | Legacy strict JSON card/render schemas |

### Frontend

| File | Role |
|---|---|
| `frontend/app/study-paths/[studyPathId]/learn/page.tsx` | Legacy learn page and inline visual renderers |
| `frontend/components/visuals_v2/StubVisual.tsx` | Dead placeholder after all 12 base v2 renderers are implemented |

## Keep

- `backend/venv/app/services/topic_generator.py` and `course_type_classifier.py`
- `backend/venv/app/services/visual_compilers/`
- `backend/venv/app/core/course_blueprints.py`
- Practice, quick-practice, class, material, learner-state, and session code
