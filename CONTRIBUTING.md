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
   pip install -r requirements.txt
   pip install -e ../sdk
   ```
3. Run tests:
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
