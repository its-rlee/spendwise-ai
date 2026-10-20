# SpendWise AI

**AI-Powered Financial Document Intelligence Platform**

SpendWise AI is a full-stack application that transforms receipts and bank statements into structured, reviewable financial records.

## Features

- Supabase email/password authentication
- FastAPI REST backend with authenticated endpoints
- Receipt OCR using Tesseract
- PDF text extraction using pypdf
- Structured financial extraction using Ollama
- Individual receipt-item extraction and categorization
- Human review, correction, approval and rejection
- PostgreSQL transaction and item storage
- SQL-grounded AI Financial Assistant
- Dockerized FastAPI backend
- Automated Python, Flutter and Docker checks through GitHub Actions

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Flutter / Dart |
| Backend | Python / FastAPI |
| Database | PostgreSQL / Supabase |
| Authentication | Supabase Auth |
| Object Storage | Amazon S3 |
| OCR | Tesseract |
| Local LLM | Ollama / Qwen2.5 |
| ORM | SQLAlchemy |
| Containerization | Docker / Docker Compose |
| CI | GitHub Actions |

## How It Works

1. Users authenticate with Supabase.
2. Users upload receipts or text-based bank statements.
3. FastAPI validates and stores documents.
4. OCR and the local LLM extract structured financial information.
5. Users correct extracted transactions and receipt items.
6. Approved records are stored in PostgreSQL.
7. Users can ask financial questions answered using validated database queries.

## Local Development

### Requirements

- Python 3.15
- Docker Desktop
- Flutter SDK
- Ollama with `qwen2.5:3b`
- Supabase development project
- Private S3 development bucket

### Backend

Configure `backend/.env` using the project's documented environment-variable requirements.

From the repository root:

`docker compose up --build -d`

Backend health endpoint:

`http://127.0.0.1:8000/health`

### Flutter

From the `mobile` directory:

`flutter pub get`

`flutter run -d chrome --web-port=5173 --dart-define-from-file=config/dev.json`

The local configuration file must be created separately and must not contain privileged credentials.

## Automated Testing

Backend:

`python -m pytest -v`

Flutter:

`flutter analyze`

`flutter test`

GitHub Actions automatically runs backend tests, Flutter validation, tracked-secret-file checks and a Docker build smoke test.

## Security Design

- Supabase access tokens authenticate API requests.
- Backend endpoints enforce resource ownership.
- Uploaded documents are stored in a private S3 bucket.
- Financial extraction requires human approval before persistence.
- Application credentials are excluded from the repository.
- SQL-grounded analytics use predefined database queries rather than model-generated SQL.

## Current Limitations

- Local Ollama is not yet deployed as a cloud inference service.
- Scanned PDFs require additional OCR support.
- Automatic item categorization and ML evaluation are planned.
- The deployment configuration is experimental and is not a production financial service.

## Roadmap

- Automatic ML-based transaction categorization
- Spending anomaly detection
- MLflow experiment tracking
- Amazon SageMaker training and inference
- Improved financial analytics
- Production monitoring and deployment

## Disclaimer

SpendWise AI is an educational portfolio project. Development and demonstrations use synthetic financial information.