<div align="center">

# 🛡️ Chargeback Shield


**Explainable, Deterministic & Secure Dispute Intelligence Platform**

<br/>

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)
![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6.svg)
![Tests](https://img.shields.io/badge/Tests-698%2F698%20PASSED-brightgreen.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)
![Production](https://img.shields.io/badge/Production-Ready-green.svg)

</div>

---


## 🚀 Overview

**Chargeback Shield** is an end-to-end, enterprise-grade dispute intelligence and representment system built to handle payment chargebacks with mathematical precision, strict financial safety, and full operational explainability.

Chargeback Shield transforms fragmented, high-friction dispute management into a controlled, deterministic 15-stage lifecycle:

```
Dispute → Evidence → Processing → Extraction → Matching → Policy → Draft → Human Review → Preflight → Submission → Reconciliation → Lifecycle → Operations → Analytics → Audit
```

### Core Architecture Principle

> **"Generate locally → Review locally → Authorize locally → Submit through one controlled boundary → Reconcile safely → Audit everything."**

The platform guarantees that AI assistances and automated algorithms generate recommendations locally, while external network mutations (such as Razorpay dispute contests) are strictly isolated behind a single, immutably guarded boundary with full human review oversight and financial identity protection.

---

## 🎯 Problem Statement

Payment dispute management for online merchants and payment service providers faces severe operational challenges:

- **Fragmented & Unstructured Evidence**: Evidence files (invoices, receipts, logs, tracking details) are scattered across disparate formats and systems.
- **Manual & Slow Investigation**: Human teams spend hours manually matching claims against transaction records.
- **Inconsistent Decisions**: Dispute responses vary based on individual reviewer experience, leading to lost representments.
- **Unsupported & Unverifiable Claims**: Contest drafts often fail because claims cannot be mapped back to concrete evidence artifacts.
- **Risky External Execution**: Retrying failed API requests blindly can cause duplicate submissions, invalid API states, or compliance breaches.
- **Ambiguous External API Outcomes**: Network timeouts lead to `UNKNOWN` submission states, risking duplicate external representment.
- **Weak Audit Trails & Provenance**: Inability to reconstruct how a decision was reached months after submission.
- **Lack of Operational Visibility & SLA Misses**: No real-time tracking of dispute stage bottlenecks, upcoming evidence submission deadlines, or win/loss trends.

---

## 💡 Solution

Chargeback Shield solves these operational failures through a deterministic, evidence-grounded workflow:

1. **Ingest Dispute**: Capture incoming dispute webhooks or batch syncs from payment gateways.
2. **Collect Evidence**: Securely ingest structured and unstructured evidence files with SHA-256 fingerprinting.
3. **Process Evidence**: Rasterize and extract clean OCR text with size, format, and magic-byte validation.
4. **Extract Structured Facts**: Parse raw text into verified domain facts (Payment IDs, Amounts, Delivery Dates, Fulfillment Proof).
5. **Match Facts**: Evaluate observed evidence facts against expected transaction facts.
6. **Apply Deterministic Policy**: Run rule-based policy evaluation to compute evidence coverage and contest eligibility.
7. **Generate Explainable Draft**: Produce contest drafts where every single claim links to underlying evidence IDs and match records.
8. **Human Review**: Provide a dedicated review workspace for human operators to inspect, flag, edit, or approve drafts.
9. **Preflight Authorization**: Enforce automated preflight gate checks (checking authorization, review staleness, and schema validity).
10. **Controlled Submission**: Route authorized submissions through a single, isolated Razorpay mutation boundary.
11. **Safe Reconciliation**: Resolve network timeouts or ambiguous API responses via read-only status lookups—**never blind retries**.
12. **Lifecycle Synchronization**: Maintain real-time state synchronization across all internal and gateway states.
13. **Operations Monitoring**: Provide real-time operational health metrics, alert management, and SLA deadline tracking.
14. **Executive Analytics**: Deliver actionable insights on win/loss ratios, evidence quality, and reviewer throughput.
15. **Audit & Compliance**: Maintain immutable, append-only audit logs with canonical SHA-256 export verification.

---

## ⭐ Key Differentiators

- 🔗 **Evidence-Grounded Claims**: Every claim in a contest draft contains direct, traceable references back to specific extracted evidence artifacts.
- ⚡ **Deterministic Fact Matching**: Compares expected transaction fields against extracted evidence facts with strict rule evaluation.
- 📐 **Deterministic Policy Engine**: Evaluates evidence sufficiency using versioned, immutable policy rules without hidden LLM decision control.
- 👤 **Human-in-the-Loop Review**: Human review is mandatory for policy-flagged or high-value disputes before submission authorization.
- 🔒 **Financial Identity Immutability**: Critical financial identities (`payment_id`, `amount`, `currency`) are locked from the database record and can never be modified by client requests.
- 🚧 **Single Razorpay Mutation Boundary**: Only the dedicated `ContestSubmissionClient` can execute external dispute contest API calls.
- 🛑 **Zero Blind Retries**: Network timeouts never trigger automated retry requests, preventing duplicate external representments.
- 🔄 **UNKNOWN State Recovery**: Ambiguous submission responses transition to `UNKNOWN` and are reconciled safely via read-only status checks.
- 🔏 **SHA-256 Fingerprinting**: Every ingested file, processed artifact, and audit log export is cryptographic hash-verified.
- 📜 **Append-Only Auditability**: All state transitions, human actions, and API events are recorded in an append-only audit log.
- ⏱️ **Operational SLA Monitoring**: Tracks dispute submission deadlines and alerts teams to impending SLA breaches.
- 🛡️ **Security Boundary Enforcement**: Strict Pydantic models with `extra="forbid"`, path traversal defense, and SQL injection prevention.
- 🛟 **Disaster Recovery & Backup**: Automated, point-in-time database and evidence storage backup, verification, and restoration scripts.
- 📈 **Production Observability**: Full metric breakdown featuring P50/P95/P99 latency tracking, error rates, and system dependency health.

---

## 🏗️ System Architecture

![Chargeback Shield Architecture](./chargeback%20shield-cleaned.png)


> **Security Guarantee**: No service or endpoint outside `ContestSubmissionClient` holds credentials or routes capable of invoking the external Razorpay dispute contest API.

---

## 🔐 Security Architecture

Chargeback Shield is architected under strict zero-trust financial security principles.

### Financial Immutability
Core transaction identities—`payment_id`, `amount`, and `currency`—are anchored upon dispute ingestion. The backend strictly rejects any request attempting to override or inject these parameters.

### Submission Isolation
External mutations are locked behind a single execution boundary:
- Only `ContestSubmissionClient` possesses the execution path for submitting evidence to Razorpay.
- REST endpoints enforce strict state transition checks (`APPROVED` → `READY` → `SUBMITTED`).

### Forbidden Operations
The platform explicitly enforces backend safeguards that forbid:
- ❌ Automatic dispute accept or auto-reject without policy evaluation.
- ❌ Refund creation or financial account mutation.
- ❌ Unsanitized external HTTP requests or arbitrary URL fetching.
- ❌ Blind retries on network failures or ambiguous gateway responses.

### Request Security
- **Strict Pydantic Validation**: All input schemas set `extra = "forbid"` to prevent mass-assignment attacks.
- **Injection Defense**: SQL parameters are fully bound via SQLAlchemy ORM; query parameters are sanitized to prevent sort and path injection.
- **Sanitized Logging**: API credentials, webhooks secrets, and tokens are scrubbed prior to writing log output.
- **Security Headers & Correlation**: Every request receives a unique `X-Correlation-ID` and is guarded by standard security headers.

### Prompt Injection & OCR Safety
Text extracted via OCR or external evidence documents is treated strictly as **untrusted user data**. Extracted evidence text cannot alter execution control flow, bypass human review gates, or override deterministic policy rules.

---

## 🧠 Explainability & Provenance

Every decision generated by Chargeback Shield provides full factual provenance tracing:

```
Claim → Factual Argument → MatchResult → ExtractedEvidence → ProcessedArtifact → EvidenceDocument
```

### Provenance Tracking Data Structure
- `source_evidence_ids`: References specific evidence documents supporting the claim.
- `source_match_result_ids`: Links to the exact deterministic match evaluation.
- `source_fact_names`: Identifies the verified domain facts (e.g., `tracking_number`, `delivery_date`).
- `sha256_hash`: Cryptographic proof verifying evidence document integrity.

> *"Every important claim in a contest draft is traceable directly back to verified evidence artifacts."*

---

## 👤 Human Review Workspace

Automated recommendations require human validation before external submission. The **Human Review Workspace** (`/review`) provides operators with complete control:

- **Evidence Explorer**: View and inspect uploaded receipts, invoices, and fulfillment proofs side-by-side.
- **Fact & Match Viewer**: Inspect extracted facts alongside expected transaction metadata.
- **Policy Explanation**: View detailed policy evaluation rules, pass/fail status, and coverage metrics.
- **Draft Generator & Editor**: Review the generated contest text with highlighted evidence citations.
- **Review Controls**: Mark disputes as **Approved**, **Rejected**, or **Flagged for Action**.
- **Stale Draft Protection**: Automatic invalidation if underlying evidence or transaction metadata changes after draft generation.

---

## 🧪 Preflight & Controlled Submission

Approval alone does **not** trigger external API calls. Chargeback Shield enforces a strict distinction between **APPROVED** and **READY**:

```
Human Review → APPROVED → Preflight Gate Checks → READY → Submission Authorization → Controlled Submission
```

### Automated Preflight Checks
1. **State Validation**: Asserts dispute is in an `APPROVED` state.
2. **Draft Staleness Check**: Verifies evidence hash has not changed since review.
3. **Payload Schema Validation**: Ensures required Razorpay fields and file attachments adhere to gateway specs.
4. **Authorization Lock**: Obtains a Compare-And-Swap (CAS) state lock to prevent concurrent submissions.

---

## 🔄 UNKNOWN State Recovery

Network dropouts or API timeouts during submission represent major operational risks. Chargeback Shield handles ambiguous states through a zero-risk reconciliation strategy:

```
Submit Request → Timeout / Ambiguous Response → State set to UNKNOWN → No Blind Retry → Read-Only Status Check → Reconcile State Locally → Audit Log
```

1. If an API request times out, the local status transitions to `UNKNOWN` (marked `SUBMISSION_IN_PROGRESS`).
2. Automated retries are **strictly prohibited**.
3. A background reconciliation worker executes a **read-only status query** against Razorpay.
4. If Razorpay shows the dispute as contested, the local state reconciles to `SUBMITTED`. If not, it safely reverts to `READY`.

---

## 📊 Operations & Analytics

### Operations Command Center (`/operations`)
- **System Health & Alert Monitoring**: Real-time status of database, storage, and API dependencies.
- **SLA Deadline Tracking**: Countdown timers highlighting disputes approaching submission deadlines.
- **Reconciliation Queue**: Active tracking of unresolved `UNKNOWN` or pending reconciliation states.

### Executive Analytics (`/analytics`)
- **Dispute Performance**: Win rates, representment volume, and financial recovery amounts.
- **Evidence & Policy Metrics**: Average evidence coverage scores, policy pass/fail distributions.
- **Reviewer Throughput**: Average human review resolution time and approval ratios.

---

## 🔍 Audit & Compliance

Chargeback Shield features a read-only audit engine (`/audit`) guided by the core philosophy:

> **"OBSERVE → TRACE → REPORT → NEVER MUTATE"**

- **Complete Dispute Timelines**: Immutable chronological log of every system event, evidence upload, and state transition.
- **Policy Compliance Reports**: Exportable evidence provenance reports for internal or regulatory audits.
- **SHA-256 Tamper Detection**: Canonical JSON hashing guarantees export records cannot be modified retroactively.

---

## 🖥️ Frontend Control Center

The React 18 / Vite frontend provides specialized routes for operational roles:

| Route | View Name | Primary Function |
|---|---|---|
| `/` | Executive Overview | High-level metrics, dispute counts, and system status |
| `/disputes` | Dispute Management | Search, filter, and manage active dispute records |
| `/evidence` | Evidence Management | Inspect uploaded files, OCR text, and SHA-256 hashes |
| `/matching` | Fact Matching | Inspect expected vs. observed evidence matching |
| `/policy` | Policy Evaluation | View deterministic policy rule outcomes and coverage |
| `/draft` | Contest Draft Generator | Generate explainable, evidence-backed contest letters |
| `/review` | Human Review Workspace | Operator review workspace for approving/rejecting drafts |
| `/preflight` | Preflight Gate | Pre-submission authorization and validation checks |
| `/submission` | Submission Boundary | Isolated gateway submission triggers and logs |
| `/lifecycle` | Dispute Lifecycle | End-to-end stage visualization and transition history |
| `/operations` | Operations Command | Operational alerts, SLA tracking, and exception queues |
| `/analytics` | Executive Analytics | Financial win rates, throughput, and performance charts |
| `/audit` | Audit & Compliance | Immutable timeline logs, provenance reports, and export hashes |
| `/observability` | System Observability | Latency metrics (P50/P95/P99), error rates, and system health |
| `/demo` | Guided Hackathon Demo | 5-minute interactive walkthrough mode |
| `/presentation` | Executive Deck | Presentation view outlining architectural highlights |

---

## 🧰 Technology Stack

### Backend Core
- **Python 3.11**: Primary runtime language.
- **FastAPI (0.109+)**: High-performance asynchronous web framework.
- **Pydantic (v2)**: Strict data validation and schema enforcement.
- **SQLAlchemy (2.0+)**: Async ORM for persistent data management.
- **SQLite (aiosqlite)**: Async database backend (PostgreSQL ready).
- **pytest**: Test automation framework.

### Frontend UI
- **React 18.3**: Component-based UI library.
- **TypeScript 5.7**: Type-safe client-side application logic.
- **Vite 6**: Fast frontend tooling and bundler.
- **Tailwind CSS 3.4**: Modern utility-first styling system.
- **React Router v6**: Single-page application client routing.
- **Lucide React**: Modern icon set.

### Infrastructure & Security
- **Docker & Docker Compose**: Containerized multi-service deployment.
- **NGINX**: Reverse proxy and static file server.
- **SHA-256**: Cryptographic hashing for file integrity and audit verification.
- **AST Static Analysis**: Automated architecture validation enforcing boundary isolation.

---

## 📁 Project Structure

```
chargeback-shield/
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI endpoint routers
│   │   ├── core/               # Middleware, errors, observability, startup validation
│   │   ├── models/             # SQLAlchemy database ORM models
│   │   ├── policies/           # Deterministic policy rules and evaluation engine
│   │   ├── schemas/            # Pydantic data validation schemas
│   │   ├── services/           # Business logic, matching, and submission clients
│   │   ├── config.py           # Application settings and environment configuration
│   │   ├── database.py         # Async database session management
│   │   └── main.py             # FastAPI application entry point
│   └── tests/                  # Unit, integration, security, and observability tests
├── frontend/
│   ├── src/
│   │   ├── api/                # Type-safe API client and endpoints
│   │   ├── components/         # Modular UI components, layout, and observability panels
│   │   ├── pages/              # 16 full-featured application view pages
│   │   ├── App.tsx             # Root application and route configuration
│   │   └── main.tsx            # Vite entry point
│   ├── tests/                  # Frontend E2E and security unit tests
│   ├── Dockerfile              # Production multi-stage NGINX build
│   └── vite.config.ts          # Vite build and proxy configuration
├── deploy/
│   └── nginx/                  # Production NGINX reverse proxy configuration
├── docs/                       # Complete architectural signoffs, runbooks, and audit guides
├── scripts/                    # Backup, restore, and database verification scripts
├── docker-compose.yml          # Production container deployment definition
├── requirements.txt            # Backend Python dependencies
├── .env.example                # Development environment variable template
├── .env.production.example     # Production environment variable template
└── README.md                   # Project documentation homepage
```

---

## ⚙️ Installation & Local Setup

### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & `npm`
- **Git**

### 1. Repository Setup
```bash
git clone https://github.com/karthikk20234119-cmd/ChargeBack-Shield.git
cd chargeback-shield
```

### 2. Backend Setup
```bash
# Create and activate Python virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / macOS:
source venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt

# Create local development environment configuration
cp .env.example .env

# Run FastAPI backend server
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
> Backend API will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 3. Frontend Setup
```bash
# Navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Run Vite development server
npm run dev
```
> Frontend application will be available at [http://localhost:3000](http://localhost:3000)

> ⚠️ **Security Warning**: *Never commit real API keys or production credentials to source control.*

---

## 🐳 Docker Deployment

The application is fully containerized for production using Docker and Docker Compose.

### Docker Architecture
- **reverse-proxy**: NGINX routing external traffic (`:80`) to frontend and backend services.
- **frontend**: High-performance production NGINX container serving built static React assets.
- **backend**: Python 3.11 Uvicorn container running FastAPI with persistent volume mounts.

### Commands

```bash
# Validate Docker Compose configuration
docker compose config

# Build container images
docker compose build

# Start services in background
docker compose up -d

# Check service container status
docker compose ps

# View backend container logs
docker compose logs -f backend
```

---

## ❤️ Health & Observability

Chargeback Shield provides comprehensive system health endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | `GET` | Basic service availability health check |
| `/api/health/live` | `GET` | Liveness probe for container orchestrators |
| `/api/health/ready` | `GET` | Readiness probe verifying database & storage connectivity |
| `/api/observability/metrics` | `GET` | Latency breakdown (P50/P95/P99), request counts, and error rates |
| `/api/observability/summary` | `GET` | System health summary, dependency statuses, and SLA compliance |

---

## 🧪 Testing & Verification

The project enforces continuous quality control backed by an extensive test suite:

### 🏆 Verified Test Baseline
```
============================== 698 PASSED ==============================
- Unit & Integration Tests:     100% PASSED
- Security & Boundary Audits:   100% PASSED
- AST Architecture Validation:  100% PASSED
- Performance & SLA Tests:      100% PASSED
- Disaster Recovery Tests:      100% PASSED
```

### Running Tests

```bash
# Run complete backend test suite
pytest

# Run security & boundary tests only
pytest backend/tests/security/

# Run performance & SLA tests
pytest tests/performance/

# Run disaster recovery & backup verification tests
pytest tests/deployment/test_disaster_recovery.py

# Run frontend production build & type check
cd frontend && npm run build
```

---

## 📈 Production Readiness

Chargeback Shield includes production engineering safeguards:

- ✅ **Container Hardening**: Multi-stage Docker builds executing under non-root user permissions.
- ✅ **Automated Backups**: Scripted point-in-time database and storage backup routines (`scripts/backup_production.py`).
- ✅ **Verified Disaster Recovery**: Full database restoration and integrity verification (`scripts/restore_production.py`).
- ✅ **AST Code Auditing**: Automated static code inspection ensuring no direct gateway mutations bypass isolation boundaries.
- ✅ **Operations & Incident Runbooks**: Detailed operational emergency runbooks (`docs/post-go-live-operations-runbook.md`).

---

## 🎬 Hackathon Demo Walkthrough

An interactive 5-minute hackathon demo script is built directly into the UI at `/demo` and `/presentation`:

| Time | Stage | Feature Highlighted |
|---|---|---|
| `00:00` | Problem | High friction, fragmented evidence, and manual dispute overhead |
| `00:30` | Ingestion | Disputing incoming webhook & ingesting multi-format evidence |
| `01:00` | Fact Extraction | Extracting OCR data with SHA-256 fingerprint verification |
| `01:40` | Matching & Policy | Deterministic fact matching and rule-based policy evaluation |
| `02:15` | Explainable Draft | Generating contest letters with direct evidence provenance links |
| `02:50` | Human Review | Operator review workspace, flag inspection, and draft approval |
| `03:30` | Preflight Gate | Preflight validation and isolated boundary submission |
| `04:00` | UNKNOWN Recovery | Safe reconciliation handling without blind retries |
| `04:25` | Operations | Real-time SLA countdown timers, alerts, and system health |
| `04:45` | Value Summary | Summary of security, auditability, and operational control |

> 📌 *Note: The demo view utilizes safe synthetic fixtures (`DEMO DATA — NOT LIVE RAZORPAY DATA`).*

---

## 🏆 Why This Project Matters

- **Drastic Reduction in Manual Friction**: Automates up to 80% of repetitive evidence matching tasks while keeping human operators in control of final submissions.
- **Full Operational Explainability**: Eliminates "black box" decisions by ensuring every claim is backed by verified evidence.
- **Enterprise Financial Safety**: Prevents costly duplicate submissions, unauthorized API mutations, and financial parameter tampering.
- **Production-Grade Engineering**: Includes complete containerization, disaster recovery, observability, and auditability out-of-the-box.

---

## 🗺️ Roadmap (Future Scope)

- 🗄️ **Managed PostgreSQL Support**: Native configuration option for managed enterprise cloud databases (Google Cloud SQL / AWS RDS).
- 📊 **OpenTelemetry Distributed Tracing**: Native export integration for Jaeger and Prometheus metrics.
- 🔐 **Enterprise SSO & Fine-Grained RBAC**: Integration with OAuth2/OIDC providers (Okta, Auth0) for multi-role team access.
- 📬 **Advanced Webhook Engine**: Configurable outgoing webhooks for merchant ERP and CRM notifications.
- 📄 **Automated PDF Audit Package Export**: One-click generation of encrypted compliance bundles for legal teams.

---

## 📚 Documentation Index

For deeper architectural signoffs and technical documentation, refer to:

- [Final Project Signoff](docs/FINAL-PROJECT-SIGNOFF.md)
- [Final Documentation Index](docs/FINAL_DOCUMENTATION_INDEX.md)
- [Production Security Signoff](docs/final-security-signoff.md)
- [Production Release Manifest v1.0.0](docs/production-release-v1.0.0.md)
- [Go-Live Checklist](docs/production-go-live-checklist.md)
- [Post Go-Live Operations Runbook](docs/post-go-live-operations-runbook.md)
- [Incident Response Protocol](docs/production-incident-response.md)
- [Hackathon Demo Script](docs/hackathon-3-5-minute-demo-script.md)
- [Judging & Value Proposition](docs/judging-value-proposition.md)

---

## 🛡️ Safety Philosophy

> **"Chargeback Shield is intentionally designed so that automation does not equal unrestricted authority."**

```
Generate locally
  → Review locally
    → Authorize locally
      → Submit through one controlled boundary
        → Reconcile safely
          → Audit everything
```

---

## 📜 License

Internal / Hackathon Project — All rights reserved.

---

## 👥 Contributors

Built with precision as a full-stack software engineering project for automated dispute intelligence and safe representment.
