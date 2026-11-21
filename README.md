# Feature Store & Model Registry

A production-ready, full-stack application designed for machine learning teams to define, materialize, and serve ML features, alongside registering models, tracking metrics, managing lifecycle stages, and establishing end-to-end data lineage.

---

## Table of Contents

1. [Key Capabilities](#key-capabilities)
2. [Architecture &amp; System Flow](#architecture--system-flow)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [Quickstart Setup Guide](#quickstart-setup-guide)
   - [1. Database Initialization (Docker + SQL Server)](#1-database-initialization-docker--sql-server)
   - [2. Database Schema Creation (Alembic or SQL Script)](#2-database-schema-creation-alembic-or-sql-script)
   - [3. Backend Configuration &amp; Launch](#3-backend-configuration--launch)
   - [4. Seed Mock Data](#4-seed-mock-data)
   - [5. Frontend Configuration &amp; Launch](#5-frontend-configuration--launch)
7. [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
8. [Programmatic API Keys Guide](#programmatic-api-keys-guide)
9. [Documentation Directory](#documentation-directory)

---

## Key Capabilities

* **Feature Catalog & Schema**: Group features logically (e.g., `Payments`), define SQL-based transformations, choose data types, assign metadata tags, and track historical lineage.
* **Dual-Storage Materialization Engine**:
  * **Online Store**: Low-latency key-value serving table (`feature_values_online`) for real-time model inference.
  * **Offline Store**: Partitioned time-series historical table (`feature_values_offline`) for training set generation and backtesting.
* **Model Registry & Stage Tracking**:
  * Register models with metadata description and owner relationships.
  * Track versions with custom performance metrics (e.g., ROC-AUC, precision) and model hyperparameter configurations in JSON format.
  * Link model versions directly to the features they were trained on (Lineage).
  * Maintain a complete stage change history (e.g., Staging, Production, Archived).
* **Cron-based Job Scheduler**: Define materialization jobs using cron syntax, backed by `APScheduler`, with a dedicated run log viewer to track execution status, timing, and errors.
* **RBAC & User Auditing**:
  * Four predefined roles: `admin`, `ml_engineer`, `data_scientist`, and `analyst`.
  * Detailed audit logging covering actions like user creation, feature materialization, API key changes, and model promotions.
* **Security & Programmatic Access**:
  * Secure password hashing (Bcrypt) and session validation (JWT Bearer tokens).
  * Generate and manage hashed API keys for automation, CLI utilities, and CI/CD pipelines.

---

## Architecture & System Flow

The system consists of a **FastAPI backend** managing API endpoints and scheduling batch runs, a **React SPA frontend** for visual catalog management, and a **Microsoft SQL Server** instance managing relational entities and online/offline feature storage.

```mermaid
graph TD
    Client[React Frontend / CLI Scripts] -->|JSON API / Auth JWT| API[FastAPI Backend]
    Client -->|X-API-Key Header| API
  
    subgraph FastAPI Application
        API --> Auth[JWT & API Key Validator]
        API --> Services[Materialization / Audit Services]
        API --> Scheduler[APScheduler Background Workers]
    end
  
    subgraph MS SQL Server Database
        Scheduler -->|Runs SQL Source Queries| SampleEvents[feature_store.sample_events]
        Services -->|Batch Ingest| OnlineStore[feature_store.feature_values_online]
        Services -->|Append Historic Logs| OfflineStore[feature_store.feature_values_offline]
      
        Auth -->|Read / Write Users| CoreSchema[core Schema]
        Services -->|Track Model Lineage| RegistrySchema[model_registry Schema]
        Scheduler -->|Register Job Runs| JobsSchema[jobs Schema]
    end
```

---

## Technology Stack

* **Core Logic**: Python 3.9+, HTML5, JavaScript (ES6+).
* **Backend Server**: FastAPI, Uvicorn, Pydantic v2 (Settings configuration).
* **ORM & Migrations**: SQLAlchemy Core/ORM, Alembic database migration framework.
* **Database**: Microsoft SQL Server 2022 (Docker-based container).
* **Background Jobs**: APScheduler (Advanced Python Scheduler) with Cron validation.
* **Frontend Client**: React 18, Vite build tool, React Router v6, Lucide React (Icons), Vanilla CSS (premium theme styles).

---

## Project Structure

```
Feature_store/
│
├── database/
│   └── schema.sql                 # SQL script for initializing MS SQL Server schemas & tables
│
├── backend/
│   ├── alembic.ini                # Alembic database migration config file
│   ├── requirements.txt           # Python backend dependencies
│   ├── alembic/                   # Alembic schema migration versions
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       ├── 05dd462a6641_add_environment.py
│   │       ├── 2326743abe1f_add_validation_rules.py
│   │       └── c035ccd4da68_add_api_key_model.py
│   ├── app/
│   │   ├── main.py                # FastAPI entry point & routers mapping
│   │   ├── api/
│   │   │   ├── deps.py            # JWT token & API Key authorization guards
│   │   │   └── routes/            # Auth, Feature, Model, Jobs, Search, Users APIs
│   │   ├── core/                  # Configurations, logging, and security functions
│   │   ├── db/
│   │   │   ├── base.py            # Global model definitions for metadata binding
│   │   │   ├── session.py         # SQLAlchemy engine connection pools
│   │   │   └── seed.py            # Initial database values loader (User, Features, Jobs)
│   │   ├── jobs/
│   │   │   └── scheduler.py       # APScheduler integration logic
│   │   └── services/
│   │       ├── audit.py           # Structured event logging helpers
│   │       └── materialization.py # Batch materialization query executor
│   └── scripts/
│       └── seed.py                # CLI script to invoke database seeding
│
├── frontend/
│   ├── package.json               # Frontend dependencies & run scripts
│   ├── vite.config.js             # Vite development environment build script
│   ├── index.html                 # Single page application base HTML
│   └── src/
│       ├── main.jsx               # React virtual DOM setup
│       ├── App.jsx                # Layout shell, Sidebar, TopBar, and router configurations
│       ├── api.js                 # Unified fetch abstraction (JWT bearer token injections)
│       ├── styles.css             # Vanilla CSS core theme, typography, tables, and modals
│       ├── components/            # Shared UI components (Sidebar, TopBar, SVG Icons)
│       └── pages/                 # UI views (Dashboard, Catalog, Registry, Jobs, Admin, Login)
│
├── docs/
│   └── ui.md                      # UI routes list and mock wireframe designs
│
├── .env.example                   # Environment configuration template
└── docker-compose.yml             # MS SQL Server database container definition
```

---

## Prerequisites

To run this application, make sure you have installed:

1. **Operating System**: Windows (tested on Windows 10/11) or macOS/Linux.
2. **Docker Desktop**: Needed to spin up the Microsoft SQL Server database.
3. **Python 3.9+**: For running the FastAPI backend.
4. **Node.js v18+**: For compiling and running the Vite frontend app.
5. **ODBC Driver 18 for SQL Server**: Required by `pyodbc` to bridge python to SQL Server. Download from [Microsoft&#39;s official site](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

---

## Quickstart Setup Guide

### 1. Database Initialization (Docker + SQL Server)

From the project root directory, launch the SQL Server developer container:

```powershell
docker compose up -d db
```

Ensure Docker is running and verify the container is active on port `1433`.

### 2. Database Schema Creation (Alembic or SQL Script)

You can choose **one** of two ways to configure the database tables:

#### Option A: Alembic Database Migrations (Recommended)

This uses python-based migrations to establish matching table schemas:

1. Set up the backend virtual environment first (see next step).
2. Inside the `backend/` directory, run:
   ```powershell
   alembic upgrade head
   ```

#### Option B: SQLcmd Native Execution (Manual Script)

Directly run the generated T-SQL script using command line utility:

```powershell
sqlcmd -S localhost -U sa -P Your_password123 -Q "CREATE DATABASE feature_store;"
sqlcmd -S localhost -U sa -P Your_password123 -d feature_store -i database/schema.sql
```

### 3. Backend Configuration & Launch

1. Navigate to the `backend/` directory:
   ```powershell
   cd backend
   ```
2. Create a virtual environment and activate it:
   ```powershell
   python -m venv .venv
   # On Windows (PowerShell):
   .\.venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
3. Install python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Create your local environment file:
   ```powershell
   copy ..\.env.example .env
   ```

   *(Note: If you changed the SQL Server password in `docker-compose.yml`, update `DATABASE_URL` in `.env` accordingly).*
5. Start the FastAPI application server:
   ```powershell
   uvicorn app.main:app --reload
   ```

   The server will startup on [http://localhost:8000](http://localhost:8000). You can browse the Swagger API documentation directly at [http://localhost:8000/docs](http://localhost:8000/docs).

### 4. Seed Mock Data

To populate user accounts, feature definitions, sample transaction tables, and scheduled batch jobs, execute the seed command inside the active virtual environment under `/backend`:

```powershell
python scripts/seed.py
```

### 5. Frontend Configuration & Launch

1. Navigate to the `frontend/` directory:
   ```powershell
   cd ../frontend
   ```
2. Install required Node modules:
   ```powershell
   npm install
   ```
3. Launch the Vite development server:
   ```powershell
   npm run dev
   ```

   Open your browser and navigate to the application console: [http://localhost:5173](http://localhost:5173).

---

## Role-Based Access Control (RBAC)

The system enforces permissions checks based on user roles. The default administrator account seeded in step 4 is:

* **Email**: `admin@featureops.local`
* **Password**: `ChangeMe123!`

### Available Roles:

1. **Admin (`admin`)**: Complete access. Can manage users, roles, view the global audit logs, generate/revoke API keys, and run batch materializations.
2. **ML Engineer (`ml_engineer`)**: Can define new features, configure materialization schedulers, and register models.
3. **Data Scientist (`data_scientist`)**: Can define features, view lineage, register models, and execute manual runs.
4. **Analyst (`analyst`)**: Read-only access to features, model metrics, and job schedules.

---

## Programmatic API Keys Guide

To integrate the Feature Store with outer systems (like training pipelines, Airflow, or GitHub Actions), use programmatic API Keys.

### 1. Generating a Key

1. Log in as the **Admin** user.
2. Go to the **Administration** tab on the Sidebar navigation.
3. Select the **API Keys** tab and click **+ Generate API Key**.
4. Provide a clear descriptive name (e.g. `CI-CD-Deployment-Key`).
5. **Copy the key immediately**. It is displayed *only once* in plain text (`fo_...`).

### 2. Using the Key in Code / CLI

To authenticate, pass the key inside the custom request header:

```bash
curl -X GET "http://localhost:8000/features" \
     -H "X-API-Key: fo_your_plain_text_api_key_here"
```

---
