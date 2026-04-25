# models/project_context.py  — NEW FILE

"""
ProjectContext: the single source of truth shared across ALL subagents.

Written to disk as CLAUDE.md (human-readable) and project_context.json
(machine-readable) immediately after the planner is approved.

Every subagent reads CLAUDE.md as its FIRST action before writing any code.
This eliminates the config-agent version mismatch bug, the frontend/backend
API contract drift bug, and the missing providers.tsx class of bug.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import json
import os


@dataclass
class ProjectContext:
    # Identity
    project_name: str
    description: str

    # Tech stack — exact choices from planner, locked here
    backend_framework: str          # e.g. "FastAPI"
    frontend_framework: str         # e.g. "Next.js 15 App Router"
    database: str                   # e.g. "SQLite" | "PostgreSQL"
    css_framework: str              # e.g. "Tailwind CSS v3"

    # Pinned versions — config agent MUST use these, not infer from imports
    pinned_versions: Dict[str, str] = field(default_factory=dict)
    # e.g. {"fastapi": ">=0.111.0", "next": "15.0.0", "react": "^18.3.0"}

    # Directory layout — exact paths every agent must use
    backend_root: str = "/backend"
    frontend_root: str = "/frontend"

    # API contract — filled in by orchestrator after backend agent completes
    # Each entry: {"method": "POST", "path": "/api/auth/login",
    #              "auth": false, "request": {...}, "response": {...}}
    api_routes: List[Dict] = field(default_factory=list)

    # Environment variables — all agents contribute, config agent finalises
    env_vars: List[str] = field(default_factory=list)
    # e.g. ["DATABASE_URL", "SECRET_KEY", "NEXT_PUBLIC_API_URL"]

    # Workspace root on REAL disk (not virtual path) — validator uses this
    workspace_root: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_claude_md(self) -> str:
        """
        Render as CLAUDE.md — the file every subagent reads first.
        Structured so an LLM can extract any section quickly.
        """
        routes_text = ""
        for r in self.api_routes:
            auth_tag = "[auth required]" if r.get("auth") else "[public]"
            routes_text += f"  {r['method']} {r['path']} {auth_tag}\n"
            if r.get("request"):
                routes_text += f"    request: {json.dumps(r['request'])}\n"
            if r.get("response"):
                routes_text += f"    response: {json.dumps(r['response'])}\n"

        versions_text = "\n".join(
            f"  {pkg}: {ver}" for pkg, ver in self.pinned_versions.items()
        )

        env_text = "\n".join(f"  {v}" for v in self.env_vars)

        return f"""# CLAUDE.md — Project Ground Truth
## READ THIS FIRST before writing any code or any file.

## Project
Name: {self.project_name}
Description: {self.description}

## Tech Stack (DO NOT DEVIATE)
Backend: {self.backend_framework}
Frontend: {self.frontend_framework}
Database: {self.database}
CSS: {self.css_framework}

## Directory Layout (EXACT PATHS — use verbatim)
Backend root:  {self.backend_root}
Frontend root: {self.frontend_root}

## Pinned Package Versions (USE EXACTLY THESE — do not infer from imports)
{versions_text}

## API Contract (Frontend must use these exact URLs)
{routes_text if routes_text else "  [will be filled after backend agent completes]"}

## Environment Variables
{env_text if env_text else "  [will be filled during implementation]"}

## Real Workspace Path (for execute_command working_dir)
{self.workspace_root}
Backend dir:  {self.workspace_root}{self.backend_root}
Frontend dir: {self.workspace_root}{self.frontend_root}

## Rules
1. NEVER use a package version not listed above.
2. NEVER create files outside the directory layout above.
3. NEVER use virtual paths like /backend in execute_command — use the real paths above.
4. The API contract above is the ONLY source of truth for route URLs.
"""

    # ── Disk I/O ──────────────────────────────────────────────────────────────

    def save(self, workspace_path: str):
        """Write CLAUDE.md and project_context.json to workspace root."""
        claude_md_path = os.path.join(workspace_path, "CLAUDE.md")
        json_path = os.path.join(workspace_path, "project_context.json")

        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(self.to_claude_md())

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, workspace_path: str) -> Optional["ProjectContext"]:
        """Load from project_context.json. Returns None if not found."""
        json_path = os.path.join(workspace_path, "project_context.json")
        if not os.path.exists(json_path):
            return None
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


def build_project_context_from_planner(
    planner_response: str,
    workspace_path: str,
    project_name: str,
) -> ProjectContext:
    """
    Parse the planner response to extract tech stack and pinned versions.
    This is a best-effort extraction — the planner prompt must output
    a structured JSON block (see prompts/planner.py change below).
    """
    import re

    # Try to find a JSON block the planner was instructed to emit
    json_match = re.search(
        r"```json\s*(\{.*?\"pinned_versions\".*?\})\s*```",
        planner_response,
        re.DOTALL,
    )

    if json_match:
        try:
            data = json.loads(json_match.group(1))
            ctx = ProjectContext(
                project_name=project_name,
                description=data.get("description", ""),
                backend_framework=data.get("backend_framework", "FastAPI"),
                frontend_framework=data.get("frontend_framework", "Next.js 15"),
                database=data.get("database", "SQLite"),
                css_framework=data.get("css_framework", "Tailwind CSS v3"),
                pinned_versions=data.get("pinned_versions", {}),
                env_vars=data.get("env_vars", []),
                workspace_root=workspace_path,
            )
            ctx.save(workspace_path)
            return ctx
        except (json.JSONDecodeError, TypeError):
            pass

    # Fallback: build a minimal context with sensible defaults
    ctx = ProjectContext(
        project_name=project_name,
        description="",
        backend_framework="FastAPI",
        frontend_framework="Next.js 15 App Router",
        database="SQLite",
        css_framework="Tailwind CSS v3",
        pinned_versions={
            "fastapi": ">=0.111.0",
            "uvicorn[standard]": ">=0.30.0",
            "sqlalchemy": ">=2.0.30",
            "pydantic": ">=2.7.0",
            "python-jose[cryptography]": ">=3.3.0",
            "passlib[bcrypt]": ">=1.7.4",
            "python-multipart": ">=0.0.9",
            "python-dotenv": ">=1.0.0",
            "next": "15.0.0",
            "react": "^18.3.0",
            "react-dom": "^18.3.0",
            "typescript": "^5.4.0",
            "tailwindcss": "^3.4.0",
            "@tanstack/react-query": "^5.40.0",
            "axios": "^1.7.0",
        },
        env_vars=["DATABASE_URL", "SECRET_KEY", "NEXT_PUBLIC_API_URL"],
        workspace_root=workspace_path,
    )
    ctx.save(workspace_path)
    return ctx