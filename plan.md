# Implementation Plan: SharePoint List Semantic Search MCP Server

This plan outlines the steps to build a self-contained MCP server that provides semantic search capabilities for SharePoint lists using Microsoft Graph API and a local vector database.

## Problem Statement
SharePoint lists lack native semantic search capabilities (Graph API offers only keyword search). Existing solutions often require heavy infrastructure (Azure AI Search). This project aims to build a lightweight, portable MCP server that ingests SharePoint list data, generates embeddings, and enables semantic search via standard MCP tools.

## Proposed Architecture
- **Language:** Python 3.12 (standard for AI/MCP work).
- **Framework:** `fastmcp` for the MCP server.
- **Vector Database:** **Zvec** (as specified). It runs in-process, persists to disk, and requires zero external infrastructure.
- **SharePoint Client:** `msgraph-sdk` for robust Graph API interaction.
- **Embeddings:** Azure OpenAI (`text-embedding-3-small`) or Local (`sentence-transformers`).
- **Scheduler:** `apscheduler` for robust background sync jobs (replacing manual thread loops).
- **Deployment:** Docker container with persistent volume for data.

## Project Structure
Following `CLAUDE.md` guidelines for complex projects (Docker deployment):
```
sharepoint-list-mcp/
├── src/
│   ├── __init__.py
│   ├── server.py              # Entry point (FastMCP)
│   ├── config.py              # Environment configuration
│   ├── models.py              # Pydantic models for API/DB
│   ├── graph_client.py        # MS Graph API wrapper
│   ├── vector_store.py        # Zvec interface
│   ├── ingest_pipeline.py     # Schema discovery, chunking, embedding
│   ├── scheduler.py           # Background sync manager
│   └── tools/                 # Individual MCP tool implementations
│       ├── discover.py
│       ├── ingest.py
│       ├── search.py
│       └── manage.py
├── tests/
│   ├── test_ingest.py
│   ├── test_search.py
│   └── conftest.py
├── .env.example
├── .gitignore
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Implementation Steps

### Phase 1: Foundation & Setup
- [ ] Initialize project with `uv` and create directory structure (`todo:init-project`)
- [ ] Create `Dockerfile` and `docker-compose.yml` (`todo:docker-setup`)
- [ ] Implement configuration loading (`src/config.py`) using `pydantic-settings` (`todo:config`)

### Phase 2: SharePoint Integration
- [ ] Implement MS Graph Client (`src/graph_client.py`) with `msgraph-sdk` (`todo:graph-client`)
- [ ] Implement Schema Discovery (`src/tools/discover.py`) to fetch list columns and propose classification (`todo:schema-discovery`)
- [ ] Implement List Item Fetching with pagination support (`todo:fetch-items`)

### Phase 3: Vector Store & Ingestion
- [ ] Implement Vector Store interface (`src/vector_store.py`) using **Zvec** (`todo:vector-store`)
- [ ] Implement Text Chunking & Template Builder (`src/ingest_pipeline.py`) (`todo:chunking`)
- [ ] Implement Embedding Service wrapper (Azure OpenAI/Local) (`todo:embedding-service`)
- [ ] Build the `ingest_list` tool logic: fetch -> process -> embed -> store (`todo:ingest-logic`)

### Phase 4: Search & MCP Tools
- [ ] Implement `search` and `search_all` logic (embedding query -> vector search -> result formatting) (`todo:search-logic`)
- [ ] Expose all capabilities as MCP tools in `src/server.py` (`todo:mcp-server`)
- [ ] Implement `get_record` and `refresh` tools (`todo:management-tools`)
- [ ] Setup `apscheduler` for background sync (`todo:scheduler`)

### Phase 5: Testing & Refinement
- [ ] Write unit tests for chunking and template generation (`todo:unit-tests`)
- [ ] Perform end-to-end test with a real SharePoint list (dev environment) (`todo:e2e-test`)
- [ ] Optimize Docker build size and startup time (`todo:optimize-docker`)

## Open Questions & Discussion Points
1.  **Authentication Options:**
    *   **Option A (Current Spec):** `Sites.Read.All` (App-only). Simple, but gives access to *all* SharePoint sites.
    *   **Option B (Recommended):** `Sites.Selected` (App-only). Requires admin to explicitly grant access to specific sites. Much more secure as it limits the "blast radius" to only the relevant lists.
    *   **Option C (Advanced):** ACL Indexing. Index item-level permissions and filter at query time. Complex and likely out of scope for MVP.
    *   *Decision:* I will implement support for **Option B** (which is just configuration on the Azure side) and document the setup process.

2.  **Scheduler:** I'm proposing `apscheduler` for more robustness than raw threads.

## Improvements from Spec
-   **Auth:** Recommend `Sites.Selected` for better security scope.
-   **APScheduler:** Better job management for syncs.
-   **Pydantic Settings:** Cleaner configuration management.
-   **Testing:** Added explicit testing phase.
