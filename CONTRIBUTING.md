# Contributing to Feature Store & Model Registry

Thank you for your interest in contributing! We welcome contributions to the core engine, UI client, Python SDK, and documentation.

## Local Development Workflow

### Backend Setup
1. Create and activate a Python virtual environment:
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements-test.txt
   pip install -e ../sdk
   ```
3. Start the disposable PostgreSQL and Redis services from the repository root, then run tests:
   ```bash
   docker compose -p featureops-p0-test -f docker-compose.test.yml up -d --wait
   ```
   Tests use a dedicated database ending in `_test`, migrate it and create fixtures, and never use the application database in `backend/.env`. See [P0 operation and verification](docs/P0_IMPLEMENTATION.md) for connection overrides.

   ```bash
   pytest tests/ -v
   ```

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   npm install
   ```
2. Run development server:
   ```bash
   npm run dev
   ```
3. Test production build:
   ```bash
   npm run build
   ```

## Pull Request Guidelines

1. Ensure all backend tests pass (`pytest tests/`).
2. Ensure the Vite frontend builds cleanly without warnings (`npm run build`).
3. Maintain clean commits and provide clear PR descriptions explaining the changes.
