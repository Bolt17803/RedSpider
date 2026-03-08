# Project Todo List


- [x] **Backend Development (FastAPI Services):**
    - [x] Implement `Ingestion Service`:
        - [x] FastAPI app for PDF upload.
        - [x] Store PDF in object storage (mocked locally, or use local filesystem for now).
        - [x] Create document record in PostgreSQL (mocked locally).
        - [x] Publish "document_received" event to a queue (mocked locally, or use a simple in-memory queue for now).
    - [x] Implement `Processing Orchestrator`:
        - [x] Consume "document_received" events.
        - [x] Coordinate calls to PDF Text Extractor, Image Extractor, OCR Service, and Text Merging.
        - [x] Update document status in PostgreSQL.
    - [x] Implement `Results Storage Service`:
        - [x] Store final extracted text (JSON) in object storage (mocked locally).
        - [x] Update document status to "COMPLETED" in PostgreSQL.
        - [x] Publish "document_processed" event.
    - [x] Define API endpoints for upload, status, and result retrieval.
    - [x] Set up PostgreSQL database and SQLAlchemy ORM.
    - [x] Implement basic error handling and logging.

- [x] **ML Engineering (Text Extraction & OCR Pipeline):**
    - [x] Implement `PDF Text Extractor`:
        - [x] Use `PyMuPDF` to extract text blocks with bounding boxes.
    - [x] Implement `Image Extractor`:
        - [x] Use `PyMuPDF` to extract embedded images.
        - [x] Save images temporarily.
    - [x] Implement `OCR Service`:
        - [x] Integrate with Google Cloud Vision API (or a local Tesseract for initial testing).
        - [x] Handle image pre-processing (deskew, binarize - optional for initial MVP).
        - [x] Return text, confidence, and bounding boxes.
    - [x] Implement `Text Merging & Reconstruction`:
        - [x] Combine text from PDF layer and OCR.
        - [x] Implement spatial sorting and overlap resolution heuristics.
        - [x] Reconstruct logical reading order.
        - [x] Output structured JSON.
    - [x] Implement `Evaluation Service`:
        - [x] Consume "document_processed" events.
        - [x] Calculate WER/CER against ground truth (mocked ground truth for now).
        - [x] Store evaluation results.

- [ ] **DevOps (Containerization & Local Setup):**
    - [ ] Create `Dockerfile` for each service (Ingestion, Orchestrator, OCR, Merger, Evaluation).
    - [ ] Create `docker-compose.yml` to orchestrate:
        - [ ] All FastAPI services.
        - [ ] PostgreSQL.
        - [ ] A message queue (e.g., RabbitMQ or Redis Streams for simplicity).
        - [ ] (Optional) MinIO for local object storage.
    - [ ] Define environment variables for configuration.

- [ ] **Project Summary:**
    - [ ] Create `PROJECT_SUMMARY.md` with:
        - [ ] Overview of implemented features.
        - [ ] File structure.
        - [ ] Setup instructions (dependencies, environment variables).
        - [ ] Execution instructions.
        - [ ] Environment variable placeholders.
