# Azalea (local dev)

This repo is a **Next.js** frontend (`frontend/`) + **FastAPI** backend (`backend/`) that uses **Supabase Auth** (JWT) and a **Postgres database** (Supabase-managed recommended).

## 1) Set up environment variables

### Frontend
- Copy `frontend/.env.example` → `frontend/.env.local`
- Fill in:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
  - `NEXT_PUBLIC_API_URL` (default `http://127.0.0.1:8000`)

### Backend
- Copy `backend/.env.example` → `backend/.env`
- Fill in:
  - `DATABASE_URL` (your Supabase Postgres connection string)
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_JWT_SECRET` (Supabase Project Settings → API → JWT Secret)

## 2) Run the backend (FastAPI)

Open a terminal in Cursor at repo root and run:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

# from repo root you can also run with:
# uvicorn app.main:app --reload --port 8000
cd venv
uvicorn app.main:app --reload --port 8000
```

## 3) Run the frontend (Next.js)

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`.

## 4) What to try first (vertical slice)

- Open the homepage
- Create a class
- Create a study path from a prompt (optionally attach a PDF)
- Generate topics + lessons from the study path page
- Start learning via the `learn` view and try practice

## Notes

- **Do not commit** real secrets in `.env` / `.env.local`. This repo includes `.env.example` templates and ignores real env files via `.gitignore`.

