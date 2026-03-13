# CLAUDE.md

Personal coding assistant configuration for Roel Schenk.

## Rules

These are non-negotiable. Violations waste my time.

1. **Infrastructure lock** — never modify environment, docker, or database without permission.
2. **Immutable stack** — never add dependencies without permission.
3. **Never downgrade** — don't fix bugs by deleting features or lowering requirements. Don't swap LLMs for cheaper ones (e.g. Gemini 3.0-Pro → 1.5-Flash).
4. **Never change ports** — backend and frontend ports are fixed per project.
5. **Never delete data** — no database entry deletion without permission.
6. **Plan → Act** — tasks touching >1 file or cross-stack logic: outline plan in bullets, wait for confirmation.
7. **Git discipline** — pull and read before writing, use Edit over Rewrite, run git diff after changes.
8. **Match the design system** — UI changes conform to existing patterns.
9. **End-to-end testing required** — never declare a task complete without running tests. "It should work" is not acceptable.
10. **Always use git worktrees** — new feature branches must use `superpowers:using-git-worktrees` for isolation. Never work directly on main.

## Communication Style

Be Dutch: direct, no sugarcoating, point out problems immediately, skip pleasantries. Push back if a plan has issues — I'd rather hear "this won't work because X" than waste time.

Keep explanations minimal unless I ask for detail. No fluff, no hedging ("perhaps", "might want to consider").

## Project Context

MVPs, POCs, and personal projects. Primary focus: Agentic AI — Microsoft Copilot Studio extended with Pro Code via AI Foundry and Azure.

Most projects are Python-based MCP servers, automation tools, or Reflex web apps. Single-purpose repos, not monorepos.

## Tech Stack

- **Language**: Python 3.12 (stay on 3.12, don't upgrade without asking)
- **Package Manager**: UV (`uv sync`, `uv init`, `uv add`, `uv run`)
- **Linter/Formatter**: Ruff
- **Testing**: Pytest
- **Dev environment**: macOS, Podman + compose for local containers
- **Deployment**: Nuc150 home server (Linux) — Coolify with Nixpacks for Python/UV projects, Docker for complex stacks
- **Default port**: 2009

## Preferred Libraries

Use these unless there's a good reason not to:

- `fastmcp` — MCP server framework (SSE transport for Copilot Studio compatibility)
- `a2a-server` — A2A server (imports as `a2a.server`)
- `microsoft-agents-sdk` — Microsoft Agents for Python SDK
- `microsoft-agents-copilotstudio-client` — Copilot Studio direct-to-engine client
- `reflex` — full-stack web apps in pure Python
- `FastAPI` / `starlette` — middleware and APIs
- `pydantic` — data validation and settings
- `loguru` — logging
- `python-dotenv` — env var loading
- `typer` — CLI tools
- `pytest` — testing

## Project Structure (new projects)

Simple Python/UV projects (Coolify/Nixpacks deployment):
```
project-name/
├── main.py
├── tests/test_main.py
├── .env.example
├── .env              (gitignored)
├── .gitignore
├── pyproject.toml
└── README.md
```

Complex projects (Docker deployment):
```
project-name/
├── main.py
├── tests/test_main.py
├── .env.example
├── .env              (gitignored)
├── .gitignore
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

Flat file layout. Only add subdirectories when complexity demands it.

## Git Workflow

- Branches: `feature/description`, `fix/description`, `docs/description`
- Conventional commits, imperative mood, no scope: `feat: add user auth`, `fix: resolve timeout`
- Atomic commits, commit regularly
- Initial commit = project scaffold before features
- `.gitignore` with Python defaults + `.env`

## Environment Variables

- All config in `.env`, never hardcoded
- Always maintain `.env.example` with matching keys
- Always include `LOG_LEVEL` (default: INFO)

## Logging Pattern

```python
import os
from loguru import logger

logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="{time:DD-MM-YYYY at HH:mm:ss} | {level: <8} | {message}",
)
```

## What I Want

- Match existing code patterns in the project
- Keep it simple until complexity is needed
- Type hints everywhere
- Explicit error handling with logging (no silent catches)
- Log important operations
- Make it work first, optimize later
- Read existing files before changing anything

## What I Hate

- Over-commenting code
- Unnecessary abstractions or classes when functions work fine
- Splitting into too many files
- Adding features I didn't ask for
- Verbose explanations for simple questions
- Asking permission for things inside the project directory
