# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Receipt Helper is a full-stack web application for splitting expenses among groups. Users create groups with members, add receipts with line items, and the app calculates who owes what based on tax rates and item assignments.

**Tech Stack:**
- **Backend**: FastAPI (Python) + SQLAlchemy (async) + PostgreSQL/SQLite + WebSockets for real-time updates
- **Frontend**: SvelteKit (Svelte 5 with runes) + TypeScript + TailwindCSS v4
- **Database Migrations**: Alembic

## Development Commands

### Backend

```bash
# Run development server (auto-reload on code changes)
cd backend
python main.py

# Run database migrations
cd backend
alembic upgrade head

# Create new migration
cd backend
alembic revision --autogenerate -m "description"
```

The backend runs on port 8000 by default (configurable via `PORT` environment variable).

### Frontend

```bash
# Run development server
cd frontend
npm run dev

# Build for production
cd frontend
npm run build

# Preview production build
cd frontend
npm run preview

# Type checking
cd frontend
npm run check

# Type checking (watch mode)
cd frontend
npm run check:watch
```

The frontend dev server runs on port 5173 by default.

## Architecture

### Backend Architecture

**Core Models** (backend/src/models.py):
- `Group`: Top-level container with unique slug for URL-based access
- `Person`: Members within a group (group-scoped)
- `Receipt`: Expense records with entries, belongs to a group
- `ReceiptEntry`: Individual line items on a receipt

**Key Design Patterns:**
- **Group Isolation**: All data is scoped to groups. People, receipts, and entries are tied to their group via foreign keys with CASCADE delete
- **Get-or-Create Pattern**: When creating receipts/entries via API, person names are accepted as strings and automatically resolved to existing Person records or new ones created (see `crud.py::get_or_create_person`)
- **Async Throughout**: Uses SQLAlchemy async session (`AsyncSession`) with `asyncpg` driver for PostgreSQL
- **Association Tables**: Many-to-many relationships use SQLAlchemy association tables (`receipt_person_association`, `receipt_entry_person_association`)

**API Structure** (backend/src/server.py):
- RESTful endpoints for CRUD operations on groups, people, receipts, and entries
- Routes follow pattern: `/groups/{group_id}/...` for group-scoped resources
- Uses Pydantic schemas (schemas.py) for request/response validation
- Dependency injection pattern for database sessions via `SessionDep`

**Real-time Updates** (backend/src/websocket_manager.py):
- WebSocket connections at `/ws/groups/{group_id}` (currently commented out in server.py)
- ConnectionManager handles group-scoped broadcasts with debouncing (2s buffer)
- Clients receive `refresh_group` messages to trigger UI updates

**Database Configuration**:
- Uses `DATABASE_URL` environment variable (defaults to `postgresql+asyncpg:///receipt_helper`)
- Alembic handles schema migrations (see `backend/alembic/`)

### Frontend Architecture

**Framework**: SvelteKit with Svelte 5 runes (`$state`, `$derived`, etc.)

**Key Files**:
- `frontend/src/lib/api.ts`: Centralized API client with typed request functions
- `frontend/src/lib/utils.ts`: Calculation logic for receipt totals, split costs, tax (7% rate)
- `frontend/src/lib/types.ts`: TypeScript interfaces matching backend schemas
- `frontend/src/lib/stores/realtime.svelte.ts`: WebSocket manager for live updates (uses Svelte 5 runes)

**Routes**:
- `/`: List all groups (frontend/src/routes/+page.svelte)
- `/groups/[id]`: Group detail page with receipts and members (frontend/src/routes/groups/[id]/+page.svelte)

**Components** (frontend/src/lib/components/):
- Reusable UI components for error display, receipt management, group/member editing
- Uses inline Tailwind classes (TailwindCSS v4 with Vite plugin)

**State Management**:
- Uses Svelte 5 runes (`$state`) for component-local state
- `RealtimeStore` class for WebSocket connection state management
- No global state management library needed

**API Communication**:
- Base URL configured via `VITE_BACKEND_HOST` env var (defaults to `http://localhost:8000`)
- Error handling utilities in `api.ts::handleError`

### Data Flow

1. **Receipt Creation**: Frontend sends receipt data with person names as strings → Backend's `crud.create_receipt` resolves/creates Person records → Returns fully populated Receipt with entries
2. **Cost Calculation**: Frontend calculates splits client-side using `utils.ts::calculateReceiptCosts` (split equally or by assignment)
3. **Real-time Sync**: WebSocket broadcasts trigger `onRefreshGroup` callback → Components refetch group data → UI updates

### Important Conventions

- **Person Names**: Backend accepts person names as strings in API requests and auto-creates Person records within the group scope. Never assume Person IDs from frontend.
- **Processed Flag**: Receipts have a `processed` boolean to exclude them from active cost calculations
- **Tax Handling**: Tax rate is hardcoded to 7% in `frontend/src/lib/utils.ts::TAX_RATE`. Entries have a `taxable` boolean flag.
- **Slug vs ID**: Groups have both numeric `id` and URL-safe `slug` for sharing

### Common Pitfalls

- Don't mix async/sync SQLAlchemy patterns - this codebase is fully async
- When adding new Person-related fields, update both the association tables and the get-or-create logic in `crud.py`
- WebSocket endpoints are currently commented out - they exist but need to be re-enabled if real-time features are needed
- Frontend uses Svelte 5 runes syntax, not the older stores API
- Database migrations must be run manually after model changes

### Environment Variables

**Backend**:
- `DATABASE_URL`: PostgreSQL connection string (default: `postgresql+asyncpg:///receipt_helper`)
- `ALLOWED_ORIGINS`: Comma-separated CORS origins (default: `http://localhost:5173`)
- `PORT`: Server port (default: 8000)

**Frontend**:
- `VITE_BACKEND_HOST`: Backend API URL (default: `http://localhost:8000`)
