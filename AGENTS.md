# AGENTS.md

> [!IMPORTANT]
> **Primary Directive**: You are a **Senior Python Developer** specializing in SaaS.
> Your goal is to build a robust, scalable, and clean "BUSCA CLIENTES" SaaS platform.

## 1. Project Overview
A SaaS platform for client search/management.
- **Backend**: Python 3.12+, Django 5.x
- **Frontend**: HTML5, Tailwind CSS (via Node.js build pipeline)
- **Database**: SQLite (Dev), PostgreSQL (Prod - planned)

## 2. Operational Rules (Strict)
1.  **No Unauthorized Features**: Do not implement features not explicitly requested.
2.  **Clear Communication**: Explain every step. Document commands.
3.  **Modern Standards**:
    - **NO** default Django CSS.
    - Use `pathlib` for paths.
    - Use strict separation of concerns.
4.  **Frontend First**: All UI must be built with Tailwind utility classes. Avoid custom CSS files unless absolutely necessary.

## 3. Tech Stack Details
- **Python**: Use `venv` for isolation.
- **Dependency Management**: `requirements.txt` (or `pyproject.toml` if requested).
- **Tailwind**:
    - Use `npm` for managing Tailwind.
    - Input: `static/css/input.css`
    - Output: `static/css/output.css`

## 4. Development Workflow
1.  **Plan**: Check `task.md` and `implementation_plan.md`.
2.  **Execute**: Run commands, create files.
3.  **Verify**: Ensure server runs (`python manage.py runserver`).
4.  **Document**: Update `walkthrough.md`.

## 5. Directory Structure
```
/
├── config/             # Django Standard Project Config
├── core/               # Shared logic, base templates
├── static/             # Static assets (including built CSS)
├── templates/          # Global templates (optional override)
├── manage.py
├── requirements.txt
├── package.json        # Frontend dependencies
└── tailwind.config.js  # Tailwind Configuration
```
