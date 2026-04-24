# Docker Integration Guide

This document explains how Docker is integrated into LaTeXGenius and how the multi-container architecture works.

## 1. Architecture Overview

The application uses **Docker Compose** to orchestrate two primary services. This ensures that the Django application and its LaTeX compilation backend run in a consistent, isolated environment.

### Services
*   **`web`**: The Django application.
    *   **Image**: Built from the local `Dockerfile` (Python 3.11-slim).
    *   **Role**: Handles user authentication, project management, and proxies compilation requests.
    *   **Port**: `8000`
*   **`latex-online`**: The LaTeX compilation microservice.
    *   **Image**: `aslushnikov/latex-online`
    *   **Role**: Standalone service that compiles LaTeX source into PDF.
    *   **Port**: `2700` (Internal)

## 2. Integration Mechanics

The integration relies on Docker's internal networking and environment-based configuration.

### Internal Networking
Docker Compose creates a shared network. The `web` service communicates with the compiler using its service name: `http://latex-online:2700`.

### Environment Configuration
The connection is configured via the `LATEX_COMPILER_URL` environment variable:
1.  **Compose Level**: Defined in `docker-compose.yml`.
2.  **Django Level**: Read in `latexgenius/settings.py` via `os.environ.get('LATEX_COMPILER_URL')`.
3.  **App Level**: Used in `myapp/views.py` within the `compile_project` function to proxy requests to the compiler.

## 3. Workflow: Compiling a Document

1.  **User Action**: The user clicks "Compile" in the editor.
2.  **Request**: The frontend sends an AJAX request to the Django backend (`/project/<id>/compile/`).
3.  **Proxying**: The Django `web` container sends a `POST` request containing the LaTeX source to `http://latex-online:2700/compile`.
4.  **Compilation**: The `latex-online` container processes the source using its internal LaTeX distribution (TeX Live).
5.  **Response**: The PDF binary is sent back to the `web` container, which then serves it to the user.

## 4. Getting Started

### Prerequisites
- Docker and Docker Compose installed.

### Setup Instructions

1.  **Prepare Environment**:
    ```bash
    cp .env.example .env
    ```
    *Note: Ensure `DEBUG=True` is set in your `.env` file for local development to see detailed error messages. You must also set a `SECRET_KEY`.*

2.  **Build and Launch**:
    ```bash
    docker compose up --build
    ```

3.  **Initialize Database**:
    In a new terminal, run migrations inside the container:
    ```bash
    docker compose exec web python manage.py migrate
    ```

4.  **Access the Application**:
    Navigate to `http://localhost:8000`.

## 5. Development Tips

- **Hot Reloading**: The `web` service uses a volume mapping (`.:/app`), so changes to your Python code or templates will trigger a Django server restart automatically inside the container.
- **Logs**: View logs for all services using `docker compose logs -f`.
- **Shell Access**: To run commands inside the web container:
    ```bash
    docker compose exec web bash
    ```
