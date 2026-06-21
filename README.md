# MediBot

MediBot is an internal enterprise QnA assistant for MediAssist Health Network.

It includes:
- FastAPI backend with layered RAG architecture
- RBAC-enforced hybrid retrieval (dense + sparse)
- Cross-encoder-style reranking flow
- SQL-RAG path with strict SELECT-only SQL cleaning
- Next.js frontend with login, role badge, collections visibility, chat, retrieval-type display, and source citations

## Project Structure

- backend
  - app/api: versioned endpoints (`/login`, `/chat`, `/collections/{role}`, `/health`)
  - app/auth: role definitions, demo users, token security
  - app/chains: SQL cleaning and SQL-RAG chain
  - app/retrievers: hybrid retrieval with RBAC filters at retrieval layer
  - app/rerankers: reranker interfaces and implementation
  - app/db + app/database: vector-store loader and SQLite executor
  - app/services: orchestration service and LLM client interface
  - app/schemas + app/models: typed contracts and chunk metadata models
  - tests: endpoint, RBAC, SQL cleaning, reranking, metadata tests
- frontend
  - app: Next.js app router pages and global styling
  - components: chat + login UI
  - lib: typed API client

## Quick Start

### Backend
1. Create and activate a virtual environment.
2. Install dependencies:
   `pip install -r backend/requirements.txt`
3. Run backend:
   `uvicorn app.main:app --reload --app-dir backend`
4. Run tests:
   `cd backend && pytest -q`

### Frontend
1. Install dependencies:
   `cd frontend && npm install`
2. Run dev server:
   `npm run dev`
3. Optional build check:
   `npm run build`

## Demo Users

- `dr.mehta` -> `doctor`
- `nurse.priya` -> `nurse`
- `billing.ravi` -> `billing_executive`
- `tech.anand` -> `technician`
- `admin.sys` -> `admin`
