# Implementation Plan: SharePoint List Semantic Search MCP Server

This document reflects the actual implementation as built.

## Architecture

- **Language:** Python 3.12
- **Framework:** `fastmcp` for the MCP server (SSE + stdio transports)
- **Vector Database:** Zvec (in-process, persistent to disk)
- **SharePoint Client:** `msgraph-sdk` for Graph API interaction
- **Embeddings:** Azure OpenAI (`text-embedding-3-small`), OpenAI, or local (`sentence-transformers`)
- **Scheduler:** `apscheduler` for background sync jobs
- **Auth:** FastMCP `AzureProvider` with delegated auth + OBO token exchange (optional)
- **Deployment:** Docker container with persistent volume, or local via stdio

## Project Structure

```
sharepoint-list-mcp/
├── main.py                    # Entry point
├── src/
│   ├── server.py              # FastMCP server, tool registration, auth setup
│   ├── config.py              # Pydantic settings (env-based config)
│   ├── graph_client.py        # MS Graph API wrapper (app-only auth)
│   ├── scheduler.py           # APScheduler background sync
│   ├── security_trimming.py   # OBO-based permission filtering
│   ├── pipeline/
│   │   ├── embedder.py        # Embedding service (Azure/OpenAI/local)
│   │   └── chunker.py         # tiktoken-based text chunking
│   ├── store/
│   │   └── zvec_store.py      # Zvec collection management
│   └── tools/
│       ├── discover.py        # get_site_lists, discover_list_schema
│       ├── ingest.py          # ingest_sharepoint_list
│       ├── search.py          # search_list, search_all_lists
│       └── manage.py          # source_manager (add/remove/list sources)
├── tests/
│   └── test_e2e.py            # E2E tests via MCP SSE transport (15 tests)
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── pyproject.toml
```

## Tools (9 total)

### Consumer Tools (no special scope required)
- `get_site_lists_tool` — discover available lists in a site
- `discover_list_tool` — inspect list schema with column classification
- `search_tool` — semantic search within a single list (security-trimmed when auth enabled)
- `search_all_tool` — cross-list semantic search (security-trimmed when auth enabled)
- `list_sources_tool` — show registered searchable list names

### Admin Tools (require `mcp-admin` scope when auth enabled)
- `ingest_list_tool` — ingest a list into Zvec + schedule sync
- `refresh_tool` — re-sync one or all lists
- `remove_source_tool` — drop a list's index and config
- `list_sources_admin_tool` — show full config details for all sources

## Authentication Modes

### App-Only (`AUTH_ENABLED=false`, default)
- Server authenticates as service principal via `CLIENT_ID` / `CLIENT_SECRET`
- All tools available without restrictions
- No security trimming — all indexed data returned to all users

### Delegated Auth (`AUTH_ENABLED=true`)
- Users sign in via OAuth2 (FastMCP AzureProvider)
- Consumer tools use OBO token exchange to get a Graph API token scoped to the user
- Search results are security-trimmed: Graph API checks whether the user can access each item's SharePoint list
- Admin tools gated behind `mcp-admin` scope
- Requires `MCP_BASE_URL`, `MCP_IDENTIFIER_URI`, and Entra app registration with exposed API scopes

## Security Trimming

When auth is enabled and search is performed:
1. Search fetches 4x candidates (extra headroom for filtered-out items)
2. For each result, extract the `list_path` from stored metadata
3. Batch-check user permissions against SharePoint via Graph API using the OBO token
4. Filter out items the user cannot access
5. Deduplicate and return top_k results

Collections ingested before the auth feature lack `list_path` metadata — security trimming is skipped with a warning. Re-ingest to enable.

## Implementation Status

All phases complete:
- [x] Foundation: project structure, config, Docker
- [x] SharePoint integration: Graph client, schema discovery, item fetching
- [x] Vector store: Zvec integration, chunking, embedding
- [x] Search: single-list, cross-list, dedup
- [x] Management: source CRUD, background sync
- [x] Delegated auth: AzureProvider, OBO flow, security trimming
- [x] Admin/consumer tool split
- [x] E2E tests: 15/15 passing
