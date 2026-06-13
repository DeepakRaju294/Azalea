# Azalea (local dev)

This repo is a **Next.js** frontend (`frontend/`) + **FastAPI** backend
(`backend/`) that uses **Supabase Auth** (JWT) and a **Postgres database**
(Supabase-managed recommended).

## 1) Set Up Environment Variables

### Frontend

- Copy `frontend/.env.example` to `frontend/.env.local`
- Fill in:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`)

### Backend

- Copy `backend/.env.example` to `backend/.env`
- Fill in:
  - `DATABASE_URL` (your Supabase Postgres connection string)
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_JWT_SECRET` (Supabase Project Settings > API > JWT Secret)
  - `CORS_ORIGINS` (optional, comma-separated deployed frontend origins)

## 2) Run The Backend (FastAPI)

Open a terminal at the repo root and run:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Keep the virtual environment in `.venv/`. The backend app source lives in
`backend/app/`; do not run the server from inside a `venv` directory.

## 3) Run The Frontend (Next.js)

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`.

## 4) What To Try First

- Open the homepage
- Create a class
- Create a study path from a prompt (optionally attach a PDF)
- Generate topics + lessons from the study path page
- Start learning via the `learn` view and try practice

## Notes

- **Do not commit** real secrets in `.env` / `.env.local`. This repo includes
  `.env.example` templates and ignores real env files via `.gitignore`.
- Local development uses lightweight startup schema checks in
  `backend/app/main.py`. For production, prefer moving schema changes into
  Alembic migrations or a dedicated database setup step.
