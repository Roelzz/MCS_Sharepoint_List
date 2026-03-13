# SharePoint List MCP Server

**Semantic search over SharePoint Lists for AI agents.**

Turn any SharePoint list into a searchable knowledge base your AI can query by meaning, not keywords. Discover schema, ingest items, generate embeddings, and expose semantic search — all through the [Model Context Protocol](https://modelcontextprotocol.io/).

---

## 🤔 Why This Exists

SharePoint Lists are everywhere in M365 organizations — IT ticket queues, knowledge bases, asset inventories, HR request trackers, project logs. They're the backbone of structured data in most enterprises.

But searching them is painful:

- **SharePoint's native search is keyword-based.** Searching "network issues" won't find a ticket titled "VPN connectivity failing intermittently." It doesn't understand intent.
- **Microsoft Copilot can read lists** but can't perform semantic search across them. It sees rows, not meaning.
- **There's no native way to embed list data** and expose it to external AI agents — Claude, custom Copilot Studio agents, or any other MCP-compatible tool.

This server fills that gap. It's a pro-code solution that ingests SharePoint list data, creates vector embeddings, and serves semantic search over MCP. Any MCP-compatible agent can discover, ingest, and search your lists — by meaning, across lists, with filtering.

---

## 🚀 What It Does

- **Auto-discovers list schema** — point it at a list, it classifies columns (embed, filter, chunk, skip)
- **Ingests list items with smart chunking** — tiktoken-based splitting that respects token limits
- **Generates vector embeddings** — Azure OpenAI, OpenAI, or local models (sentence-transformers)
- **Stores everything in Zvec** — in-process vector DB, no external infrastructure needed
- **Exposes 8 MCP tools** — list site lists, discover schema, ingest, search, cross-search, list sources, refresh, remove
- **Background sync** — APScheduler keeps indexed data fresh on a configurable interval
- **Dual transport** — SSE for Copilot Studio, stdio for Claude Desktop / VS Code

---

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────────────────────────────────────────┐     ┌──────────────┐
│  SharePoint  │     │              MCP Server                         │     │   AI Agent    │
│    Online    │     │                                                  │     │              │
│              │     │  ┌──────────┐  ┌───────┐  ┌───────┐  ┌───────┐ │     │  Claude      │
│  List Items  │────▶│  │ Discover │─▶│ Fetch │─▶│ Chunk │─▶│ Embed │ │     │  Copilot     │
│  via Graph   │     │  └──────────┘  └───────┘  └───────┘  └───┬───┘ │     │  Studio      │
│    API       │     │                                           │     │     │  VS Code     │
│              │     │                                    ┌──────▼───┐ │     │  Any MCP     │
│              │     │                                    │   Zvec   │ │     │  Client      │
│              │     │                                    │ (Vector  │ │     │              │
│              │     │  ┌──────────────────────────┐      │   DB)    │ │     │              │
│              │     │  │      MCP Tools (8)       │◀─────┤          │ │◀───▶│              │
│              │     │  └──────────────────────────┘      └──────────┘ │     │              │
│              │     │  ┌──────────────────────────┐                   │     │              │
│              │     │  │   APScheduler (sync)     │                   │     │              │
│              │     │  └──────────────────────────┘                   │     │              │
└──────────────┘     └──────────────────────────────────────────────────┘     └──────────────┘
```

**Stack:** FastMCP · MSGraph SDK · Zvec · OpenAI / Azure OpenAI · tiktoken · APScheduler · Pydantic Settings · Loguru

---

## 🤖 Available Tools

| Tool | Parameters | Description |
|---|---|---|
| `get_site_lists_tool` | `site_url` | Return all lists available in a SharePoint site with their names, IDs, and metadata. Use this to discover which lists exist before inspecting or ingesting. |
| `discover_list_tool` | `site_url`, `list_name` | Inspect a SharePoint list and return its schema with proposed column classification (embed/filter/chunk/skip). |
| `ingest_list_tool` | `site_url`, `list_name`, `column_overrides?`, `sync_interval_minutes?` (default: `SYNC_INTERVAL_MINUTES` env var, or 60) | Pull all items from a list, generate embeddings, store in Zvec, and schedule background sync. |
| `search_tool` | `query`, `source`, `filters?` (JSON string), `top_k?` (default: 5) | Semantic search within a single list's index. Supports metadata filters like `{"Status": "Open"}`. |
| `search_all_tool` | `query`, `sources?` (list of names), `top_k?` (default: 5) | Semantic search across all indexed lists (or a subset), ranked by relevance. |
| `list_sources_tool` | _(none)_ | Show all registered lists with their stats and sync status. |
| `refresh_tool` | `source?` | Trigger a re-sync of one specific list or all registered lists. |
| `remove_source_tool` | `source` | Remove a list's Zvec collection, config, and scheduled sync. |

---

## ⚙️ How It Works

### Discovery
Point the agent at a SharePoint list (`site_url` + `list_name`). The server fetches the list schema via Graph API and auto-classifies each column:
- **Embed** — text columns whose content should be vectorized (titles, descriptions)
- **Filter** — choice/status columns useful for metadata filtering
- **Chunk** — long text fields that need to be split (notes, descriptions exceeding token limits)
- **Skip** — system columns, IDs, timestamps

### Ingestion
1. Fetch all list items via Microsoft Graph API
2. Concatenate embeddable fields per item into a document
3. Split oversized documents into chunks using tiktoken (respects model token limits)
4. Generate vector embeddings via configured provider
5. Store vectors + metadata in a Zvec collection on disk

### Search
1. Embed the query string using the same model
2. Zvec performs cosine similarity search across stored vectors
3. Results are deduplicated by source record (chunks from the same item are merged)
4. Ranked results returned with metadata and relevance scores

### Background Sync
APScheduler runs on a configurable interval (default: `SYNC_INTERVAL_MINUTES` env var, or 60 minutes). Each sync performs a full re-ingest of the list — fetch, chunk, embed, store — replacing the previous index. Per-source `sync_interval_minutes` overrides the global default.

---

## 📋 Setup Guide

### Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- Azure subscription (for App Registration)
- Azure OpenAI resource (or OpenAI API key, or local model)
- SharePoint Online site with lists to index

### Step 1: Azure AD App Registration

This server uses **App-Only Authentication** — it runs as a service principal, not a signed-in user.

#### Automated Setup

```bash
./setup_azure_auth.sh
```

Follow the prompts. This creates the App Registration, Client Secret, and Permission assignment.

#### Manual Setup

1. Go to [Azure Portal](https://portal.azure.com) → **Microsoft Entra ID** → **App registrations** → **New registration**
2. **Name:** `SharePoint-List-MCP-Search`
3. **Supported account types:** Single tenant
4. Click **Register**

**Get credentials:**
- Copy **Application (client) ID** and **Directory (tenant) ID**
- Go to **Certificates & secrets** → **New client secret** → copy the value immediately

**Grant API permissions:**
1. Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**
2. Choose one:
   - **`Sites.Read.All`** — read access to all SharePoint sites (easiest, use for testing)
   - **`Sites.Selected`** — no access by default, you grant per-site (recommended for production)
3. Click **Grant admin consent for [Your Org]**

### Step 2: Grant Site Access (Sites.Selected only)

If you chose `Sites.Selected`, explicitly grant read access to your target site:

1. Get the **Site ID** via Graph Explorer: `https://graph.microsoft.com/v1.0/sites/{hostname}:/{relative-path}`
2. **POST** `https://graph.microsoft.com/v1.0/sites/{site-id}/permissions`

```json
{
  "roles": ["read"],
  "grantedToIdentities": [{
    "application": {
      "id": "YOUR-CLIENT-ID",
      "displayName": "SharePoint-List-MCP-Search"
    }
  }]
}
```

### Step 3: Install & Configure

```bash
git clone https://github.com/your-repo/sharepoint-list-mcp.git
cd sharepoint-list-mcp
uv sync
cp .env.example .env
```

Edit `.env` with your credentials (see [Configuration Reference](#-configuration-reference) below).

### Step 4: Run the Server

**Local (stdio — Claude Desktop / VS Code):**
```bash
uv run python main.py
```

**Local (SSE — Copilot Studio / HTTP clients):**
```bash
MCP_TRANSPORT=sse uv run python main.py
```

**Docker:**
```bash
docker build -t sharepoint-list-mcp .
docker run --env-file .env -p 8080:8080 sharepoint-list-mcp
```

### Step 5: Connect to Your AI Agent

**Claude Desktop** — add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sharepoint-search": {
      "command": "uv",
      "args": ["run", "python", "main.py"],
      "cwd": "/path/to/sharepoint-list-mcp"
    }
  }
}
```

**Copilot Studio** — point your custom connector at the SSE endpoint:
```
http://your-host:8080/sse
```

---

## 📝 Configuration Reference

| Variable | Description | Default | Required |
|---|---|---|---|
| `TENANT_ID` | Azure AD tenant ID | — | Yes |
| `CLIENT_ID` | App Registration client ID | — | Yes |
| `CLIENT_SECRET` | App Registration client secret | — | Yes |
| `EMBEDDING_PROVIDER` | Embedding provider: `azure_openai`, `openai`, `local` | `azure_openai` | No |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint | — | If provider = `azure_openai` |
| `AZURE_OPENAI_KEY` | Azure OpenAI API key | — | If provider = `azure_openai` |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI deployment name | `text-embedding-3-small` | No |
| `OPENAI_API_VERSION` | Azure OpenAI API version | `2023-05-15` | No |
| `OPENAI_API_KEY` | OpenAI API key | — | If provider = `openai` |
| `LOCAL_MODEL_NAME` | Local sentence-transformer model | `all-MiniLM-L6-v2` | No |
| `MCP_TRANSPORT` | Transport protocol: `stdio`, `sse` | `stdio` | No |
| `MCP_PORT` | Port for SSE transport | `8080` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `DATA_DIR` | Directory for Zvec collections and config | `data` | No |
| `SYNC_INTERVAL_MINUTES` | Default background sync interval in minutes | `60` | No |

---

## 🧪 Test Data

The `test-data/` directory contains a ready-made dataset for evaluating semantic search quality:

- **`vector_search_test_data.csv`** — 5,000 synthetic IT helpdesk tickets with realistic titles, descriptions, categories, priorities, and resolutions. Covers password resets, hardware failures, software installs, network issues, permissions, data loss, VPN, mobile, and more. Designed with varied phrasing so the same problem type is described in many different ways — exactly the scenario where vector search outperforms keyword search.
- **`vector_search_test_plan.md`** — A structured test plan with 30+ queries split into three parts: queries where keyword search works fine, queries where only semantic search succeeds, and tricky queries that expose keyword search weaknesses. Includes expected outcomes and a scoring framework.

**How to use:** Import the CSV into a SharePoint list (or use it as a local test fixture), ingest it with `ingest_list_tool`, then run the queries from the test plan against `search_tool`. Compare results to the expected outcomes to validate search quality.

---

## ⚠️ Limitations & Notes

- **App-only auth** — the server runs as a service principal, not a signed-in user. It sees all data granted to the App Registration. Be careful not to index sensitive lists unless the bot's users are authorized to see them.
- **5,000 item limit** — Graph API returns a maximum of 5,000 items per list query. Lists exceeding this require pagination (not yet implemented).
- **Full re-ingest on sync** — background sync performs a complete re-ingest, not delta updates. This is simple and reliable but not optimal for very large lists.
- **Graph API rate limits** — Microsoft throttles Graph API calls. The background syncer is designed to be gentle, but initial ingestion of large lists may take time.
- **No user-level permissions** — results are not filtered by the querying user's SharePoint permissions. Access control is at the App Registration level.
