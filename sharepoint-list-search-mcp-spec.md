# SharePoint List Semantic Search MCP Server

## Specification Document

**Version:** 0.1 (Draft)
**Date:** 2026-03-12
**Author:** Roel Schenk

---

## 1. Overview

### 1.1 What Is This

A self-contained MCP (Model Context Protocol) server that provides semantic search over one or more SharePoint lists. It connects to SharePoint via the Microsoft Graph API, auto-discovers list schemas, embeds list item content into vectors, stores them in an in-process vector database (Zvec), and exposes search and management capabilities as MCP tools.

### 1.2 Why Build It

- Azure AI Search's native SharePoint indexer does not support SharePoint Lists (only document libraries)
- Microsoft Graph Search API (`/search/query`) is KQL based (keyword matching), not semantic
- Existing SharePoint MCP servers (PnP CLI, community projects) execute CLI commands or Graph API calls at query time; none provide vector-based semantic search
- Azure AI Search costs ~$75/month per index; this approach costs ~$3/month for embeddings and runs on any Docker host

### 1.3 What It Does

- Points at any SharePoint list and auto-discovers its schema
- Classifies columns as embeddable, filterable, chunk-able, or skippable
- Constructs natural language text from each list item and generates vector embeddings
- Chunks long text fields while preserving structured metadata context
- Stores embeddings and metadata in Zvec collections (one per list)
- Supports semantic search within a single list or across multiple lists
- Syncs on a configurable schedule to keep the index current
- Exposes everything as MCP tools callable from Copilot Studio, Claude, VS Code, or any MCP client

### 1.4 Design Principles

- **Generic:** Works with any SharePoint list without code changes. Point, discover, ingest, search.
- **Self-contained:** Single Docker container. No external database, no Azure AI Search, no infrastructure beyond the container itself.
- **Multi-list:** Supports multiple lists from multiple sites in a single deployment. Each list gets its own Zvec collection with its own schema.
- **Portable:** Runs on Azure App Service, Azure Container Apps, a home server, a laptop, anywhere Docker runs.
- **MCP native:** All capabilities are exposed as MCP tools. The server does not have its own UI; it's designed to be consumed by AI agents and MCP clients.

---

## 2. Architecture

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  Docker Container                                            │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  MCP Server (FastMCP, Python)                          │  │
│  │  Transport: stdio (local) or SSE (remote/Copilot)      │  │
│  │                                                        │  │
│  │  Tools:                                                │  │
│  │  ├── discover_list      (inspect a SharePoint list)    │  │
│  │  ├── ingest_list        (embed + store a list)         │  │
│  │  ├── search             (semantic search, single list) │  │
│  │  ├── search_all         (semantic search, cross-list)  │  │
│  │  ├── get_record         (fetch by item ID)             │  │
│  │  ├── refresh            (re-sync one or all lists)     │  │
│  │  ├── list_sources       (show registered lists)        │  │
│  │  └── remove_source      (drop a list's index + config) │  │
│  └──────────┬─────────────────────────────────────────────┘  │
│             │                                                │
│  ┌──────────▼──────────┐  ┌─────────────────────────────┐   │
│  │  SharePoint Client   │  │  Embedding Service          │   │
│  │                      │  │                             │   │
│  │  • Graph API auth    │  │  Provider (swappable):      │   │
│  │  • Schema discovery  │  │  • Azure OpenAI             │   │
│  │  • Item pagination   │  │  • OpenAI                   │   │
│  │  • Delta queries     │  │  • Local (sentence-xformers)│   │
│  └──────────────────────┘  └──────────────┬──────────────┘   │
│                                           │                  │
│  ┌────────────────────────────────────────▼──────────────┐   │
│  │  Zvec (in-process vector database)                    │   │
│  │                                                       │   │
│  │  Collection: "src_IT_Requests"                        │   │
│  │  Collection: "src_Asset_Inventory"                    │   │
│  │  Collection: "src_Knowledge_Base"                     │   │
│  │  ...                                                  │   │
│  │                                                       │   │
│  │  Persisted to: /data/zvec/                            │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Config + State Store                                 │   │
│  │                                                       │   │
│  │  /data/config/sources.json    (registered lists)      │   │
│  │  /data/config/schemas/        (per-list schema cache) │   │
│  │  /data/state/sync_state.json  (last sync timestamps)  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │  Sync Scheduler (background thread)                   │   │
│  │                                                       │   │
│  │  Runs on configurable interval per source.            │   │
│  │  Calls the same ingest logic as the ingest_list tool. │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
         ▲
         │ MCP Protocol
         │ (stdio for local, SSE for remote)
         │
    ┌────┴─────────────────────────────────┐
    │  MCP Client                          │
    │  • Copilot Studio (via Agent 365)    │
    │  • Claude Desktop / Claude Code      │
    │  • VS Code / Cursor (GitHub Copilot) │
    │  • Custom agent                      │
    └──────────────────────────────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Language | Python 3.11+ | Zvec Python SDK, FastMCP, Graph API SDKs |
| MCP Framework | FastMCP | Pythonic MCP server, supports stdio + SSE transports |
| Vector Database | Zvec | In-process, persistent, hybrid search (vector + filters), zero infrastructure |
| Graph API Client | `msgraph-sdk` or `httpx` + MSAL | SharePoint list access, schema discovery, item pagination |
| Embedding (cloud) | Azure OpenAI `text-embedding-3-small` | 1536 dimensions, good quality, cheap, Microsoft stack |
| Embedding (local) | `sentence-transformers` + `all-MiniLM-L6-v2` | 384 dimensions, no external dependency, ~500MB model |
| Tokenizer | `tiktoken` | Token counting for chunk sizing |
| Packaging | Docker | Single container, portable, volume-mounted persistence |
| Config | JSON files on disk | Simple, human readable, mounted volume |

### 2.3 Data Flow

```
INGEST FLOW:
  Graph API (list columns) ──→ Schema Discovery
  Graph API (list items)   ──→ Column Classifier
                                    │
                               ┌────▼────┐
                               │ Template │ (auto-generated from classified columns)
                               │ Builder  │
                               └────┬────┘
                                    │
                           ┌────────▼────────┐
                           │ Text Constructor │ (applies template per record)
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │    Chunker      │ (splits long text fields,
                           │                 │  prepends metadata prefix)
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │    Embedder     │ (Azure OpenAI or local model)
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │  Zvec Collection│ (insert documents with
                           │                 │  vectors + scalar fields)
                           └─────────────────┘

SEARCH FLOW:
  User query ──→ Embedder ──→ Zvec query (vector + filters)
                                    │
                           ┌────────▼────────┐
                           │  Deduplicator   │ (group chunks by record_id,
                           │                 │  keep best chunk per record)
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │  Result Builder │ (format for MCP response,
                           │                 │  include source attribution)
                           └─────────────────┘
```

---

## 3. Schema Discovery and Column Classification

### 3.1 Discovery Process

When `discover_list` is called for a new SharePoint list:

1. Call `GET /sites/{siteId}/lists/{listId}/columns` via Graph API
2. Filter out hidden and read-only system columns
3. Call `GET /sites/{siteId}/lists/{listId}/items?$top=20&$expand=fields` to get sample data
4. For each column, measure token count across sample records (using `tiktoken`)
5. Classify each column based on type and content analysis
6. Return the proposed classification for review/override

### 3.2 Classification Rules

| SharePoint Column Type | Default Classification | Index Behavior |
|---|---|---|
| Single line of text | `embed` | Included in embedding text |
| Multiple lines of text (avg < 500 tokens) | `embed` | Included in embedding text |
| Multiple lines of text (max > 500 tokens) | `chunk` | Chunked, each chunk gets metadata prefix |
| Choice / Multi-choice | `filter` + `embed` | Zvec scalar field (filterable) + included in embedding text |
| Yes/No | `filter` + `embed` | Zvec scalar field (filterable) + included in embedding text |
| Number / Currency | `filter` + `embed` | Zvec scalar field (filterable) + included with label in embedding text |
| Date and Time | `filter` + `embed` | Zvec scalar field (filterable) + included formatted in embedding text |
| Person or Group | `filter` + `embed` | Zvec scalar field (filterable, display name) + included in embedding text |
| Lookup | `filter` + `embed` | Zvec scalar field (filterable, display value) + included in embedding text |
| Hyperlink / Picture | `retrieve` | Stored in Zvec for retrieval, not embedded or filtered |
| Calculated | Classify by output type | Apply rules based on whether output is text, number, date, etc. |
| Title | `embed` (always) | Always included in embedding text, primary identifier |
| ID | `retrieve` | Stored as `record_id`, not embedded |
| System columns (Created, Modified, etc.) | `skip` or `retrieve` | Not embedded, optionally stored |

### 3.3 Overrides

The auto-classification can be overridden per column in the source config:

```json
{
  "column_overrides": {
    "InternalNotes": "skip",
    "LegacyStatusCode": "skip",
    "DetailedDescription": "chunk",
    "ShortCode": "filter"
  }
}
```

Valid override values: `embed`, `filter`, `chunk`, `retrieve`, `skip`.

---

## 4. Embedding Text Construction

### 4.1 Template Generation

The classifier output produces an ordered list of fields to include in the embedding text. A template is auto-generated:

```python
# Example generated template for an IT Requests list:
template = [
    ("Title",        "embed",  "text",     "Title: {value}"),
    ("Status",       "filter", "choice",   "Status: {value}"),
    ("Priority",     "filter", "choice",   "Priority: {value}"),
    ("AssignedTo",   "filter", "person",   "Assigned to: {value}"),
    ("DueDate",      "filter", "datetime", "Due: {value}"),
    ("Category",     "filter", "choice",   "Category: {value}"),
    ("Description",  "chunk",  "note",     None),  # chunked separately
]
```

### 4.2 Metadata Prefix

All non-chunk fields are concatenated into a metadata prefix:

```
Title: VPN Gateway Migration. Status: In Progress. Priority: High. 
Assigned to: Jan de Vries. Due: 2026-03-15. Category: Network Infrastructure.
```

This prefix is prepended to every chunk of the record, ensuring each chunk carries the record's identity and structured context.

### 4.3 Full Text (Non-Chunked Records)

For records where no field exceeds the chunk threshold:

```
content = metadata_prefix + "\n" + all_embed_fields_concatenated
```

This becomes a single Zvec document.

### 4.4 Chunked Records

For records with one or more long text fields:

```
chunk_text = concatenated long text fields (with field labels)
chunks = split(chunk_text, chunk_size=400, overlap=50, boundary="sentence")

For each chunk:
    content = metadata_prefix + "\n" + chunk
```

Each chunk becomes a separate Zvec document, linked by `record_id`.

---

## 5. Chunking Strategy

### 5.1 Parameters

| Parameter | Default | Description |
|---|---|---|
| `chunk_size_tokens` | 400 | Max tokens of content per chunk (excluding metadata prefix) |
| `chunk_overlap_tokens` | 50 | Overlap between adjacent chunks |
| `chunk_threshold_tokens` | 500 | If a record's total text exceeds this, chunking is triggered |
| `split_boundary` | `sentence` | Split on sentence boundaries first, then paragraph, then token count |

### 5.2 Split Logic (Priority Order)

1. **Paragraph boundaries** (`\n\n`): Try to split on paragraph breaks first. If a paragraph fits within `chunk_size_tokens`, keep it whole.
2. **Sentence boundaries** (`. ` followed by uppercase, `? `, `! `): If a paragraph exceeds `chunk_size_tokens`, split within it at sentence boundaries.
3. **Token count fallback**: If a single sentence exceeds `chunk_size_tokens` (rare, would mean 400+ tokens in one sentence), split on token count.

### 5.3 Overlap

When splitting, the end of chunk N overlaps with the start of chunk N+1 by `chunk_overlap_tokens`. This prevents meaning loss at boundaries. The overlap uses sentence boundaries when possible (include the last 1 to 2 sentences of the previous chunk at the start of the next).

### 5.4 Multiple Long Text Fields

If a record has multiple chunk-able fields (e.g., `Description` and `ResolutionNotes`), concatenate them with labeled separators before chunking:

```
Description: [description text]

Resolution Notes: [resolution notes text]
```

Then chunk the combined text. Each chunk still gets the metadata prefix prepended.

### 5.5 Token Counting

Use `tiktoken` with the `cl100k_base` encoding (used by OpenAI embedding models) for consistent token measurement between chunk sizing and embedding API calls.

---

## 6. Zvec Collection Schema

### 6.1 Document Structure

Each Zvec document (one per record or one per chunk) has:

| Field | Type | Purpose |
|---|---|---|
| `id` | string (primary key) | Composite: `{record_id}_chunk_{chunk_index}` |
| `record_id` | string (scalar, filterable) | SharePoint list item ID |
| `chunk_index` | int (scalar, filterable) | 0 for non-chunked records, 0..N for chunked |
| `record_url` | string (scalar) | Direct URL to the SharePoint list item |
| `content` | string (scalar) | The full text (metadata prefix + chunk content) |
| `content_vector` | vector (dense) | Embedding of `content` field |
| `last_modified` | string (scalar) | SharePoint item's last modified timestamp |
| *Dynamic filter fields* | scalar (filterable) | One per classified filter column (Status, Priority, etc.) |

### 6.2 Collection Naming

Collection names follow the pattern: `src_{sanitized_list_name}_{list_id_short}`

Example: `src_IT_Requests_abc123`

### 6.3 Vector Configuration

| Setting | Value |
|---|---|
| Dimensions | 1536 (Azure OpenAI `text-embedding-3-small`) or 384 (local `all-MiniLM-L6-v2`) |
| Distance metric | Cosine similarity |
| Index type | HNSW (Zvec default) |

### 6.4 Dynamic Schema

Since each list has different columns, the Zvec collection schema is generated dynamically during `ingest_list`. The filter fields are created based on the column classification output. Zvec supports schema evolution, so adding or removing filter fields on re-ingest is possible.

---

## 7. MCP Tool Specifications

### 7.1 `discover_list`

**Purpose:** Inspect a SharePoint list and return its schema with a proposed column classification.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `site_url` | string | yes | SharePoint site URL (e.g., `https://contoso.sharepoint.com/sites/IT`) |
| `list_name` | string | yes | List display name or list ID (GUID) |

**Returns:**

```json
{
  "list_id": "abc123-...",
  "list_name": "IT Requests",
  "item_count": 5247,
  "columns": [
    {
      "internal_name": "Title",
      "display_name": "Title",
      "type": "text",
      "classification": "embed",
      "sample_values": ["VPN Migration", "Printer Setup", "..."],
      "avg_tokens": 5,
      "max_tokens": 12
    },
    {
      "internal_name": "Description",
      "display_name": "Description",
      "type": "note",
      "classification": "chunk",
      "avg_tokens": 320,
      "max_tokens": 4200
    },
    {
      "internal_name": "Status",
      "display_name": "Status",
      "type": "choice",
      "classification": "filter",
      "choices": ["Open", "In Progress", "Closed", "On Hold"]
    }
  ],
  "estimated_chunks": 14200,
  "estimated_ingest_time_seconds": 120
}
```

**Behavior:** Read-only. Does not create any collection or persist any data.

---

### 7.2 `ingest_list`

**Purpose:** Pull all items from a SharePoint list, embed them, and store in a Zvec collection.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `site_url` | string | yes | SharePoint site URL |
| `list_name` | string | yes | List display name or list ID |
| `column_overrides` | object | no | Override auto-classification for specific columns |
| `sync_interval_minutes` | int | no | Schedule automatic refresh (default: 60, 0 = no auto-sync) |

**Returns:**

```json
{
  "source_name": "IT Requests",
  "collection_name": "src_IT_Requests_abc123",
  "records_processed": 5247,
  "chunks_created": 14200,
  "embedding_tokens_used": 6800000,
  "duration_seconds": 95,
  "status": "complete"
}
```

**Behavior:**
1. Calls `discover_list` internally (or uses cached schema if already discovered)
2. Creates or replaces the Zvec collection
3. Paginates through all list items via Graph API (200 items per page)
4. Constructs embedding text per record using the generated template
5. Chunks long text fields as needed
6. Calls embedding API in batches
7. Inserts documents into Zvec collection
8. Persists source config to disk for future refreshes
9. Calls `collection.optimize()` after insertion

---

### 7.3 `search`

**Purpose:** Semantic search within a single list's index.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Natural language search query |
| `source` | string | yes | Source name (as registered during ingest) |
| `filters` | object | no | Metadata filters (e.g., `{"Status": "Open", "Priority": "High"}`) |
| `top_k` | int | no | Number of results to return (default: 5, max: 20) |

**Returns:**

```json
{
  "source": "IT Requests",
  "results": [
    {
      "record_id": "4521",
      "record_url": "https://contoso.sharepoint.com/sites/IT/Lists/Requests/DispForm.aspx?ID=4521",
      "score": 0.92,
      "content": "Title: VPN Gateway Migration. Status: In Progress. Priority: High...",
      "fields": {
        "Title": "VPN Gateway Migration",
        "Status": "In Progress",
        "Priority": "High",
        "AssignedTo": "Jan de Vries"
      }
    }
  ],
  "total_candidates": 14200,
  "query_time_ms": 12
}
```

**Behavior:**
1. Embed the query using the same embedding model as ingestion
2. Execute vector search on the specified Zvec collection with optional filters
3. Deduplicate results (group by `record_id`, keep highest scoring chunk per record)
4. Return top_k unique records with content, fields, and scores

---

### 7.4 `search_all`

**Purpose:** Semantic search across all registered lists (or a subset).

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `query` | string | yes | Natural language search query |
| `sources` | list[string] | no | Limit to specific sources (default: all) |
| `top_k` | int | no | Total results to return across all sources (default: 5) |

**Returns:**

```json
{
  "results": [
    {
      "source": "IT Requests",
      "record_id": "4521",
      "score": 0.92,
      "content": "...",
      "fields": { "Title": "VPN Gateway Migration", "Status": "In Progress" }
    },
    {
      "source": "Knowledge Base",
      "record_id": "187",
      "score": 0.87,
      "content": "...",
      "fields": { "Topic": "VPN Architecture", "Category": "Networking" }
    }
  ],
  "sources_searched": ["IT Requests", "Asset Inventory", "Knowledge Base"],
  "query_time_ms": 28
}
```

**Behavior:**
1. Embed the query once
2. Search each collection in parallel (or sequentially; for <20 collections it doesn't matter)
3. Request `top_k` results per collection
4. Normalize scores across collections (min-max normalization within each collection, then re-rank)
5. Merge, deduplicate (within each source by record_id), sort by normalized score
6. Return top_k total results with source attribution

---

### 7.5 `get_record`

**Purpose:** Retrieve a specific record by its SharePoint item ID.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Source name |
| `record_id` | string | yes | SharePoint list item ID |

**Returns:** Full record content and all stored fields. If the record is chunked, returns all chunks concatenated.

**Behavior:** Fetches from Zvec first (fast). If not found (e.g., just created and not yet synced), falls back to Graph API live lookup.

---

### 7.6 `refresh`

**Purpose:** Trigger a re-sync of one or all registered lists.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `source` | string | no | Specific source to refresh (default: all) |
| `mode` | string | no | `full` (default) or `delta` (if supported) |

**Returns:** Sync result per source (records processed, chunks created, duration).

---

### 7.7 `list_sources`

**Purpose:** Show all registered lists with their stats.

**Parameters:** None.

**Returns:**

```json
{
  "sources": [
    {
      "name": "IT Requests",
      "site_url": "https://contoso.sharepoint.com/sites/IT",
      "list_name": "Requests",
      "record_count": 5247,
      "chunk_count": 14200,
      "last_sync": "2026-03-12T14:00:00Z",
      "sync_interval_minutes": 60,
      "collection_size_mb": 98,
      "schema_summary": "15 columns (6 filterable, 8 embedded, 1 chunked)"
    }
  ]
}
```

---

### 7.8 `remove_source`

**Purpose:** Remove a registered list, dropping its Zvec collection and config.

**Parameters:**

| Name | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Source name to remove |

**Returns:** Confirmation with freed resources.

**Behavior:** Drops the Zvec collection, removes the source config from disk, stops scheduled sync for this source.

---

## 8. Sync Strategy

### 8.1 Full Sync (Default)

Timer-triggered background process, runs per source at its configured interval.

1. Paginate through all list items via Graph API (200 per page, handles 5,000+ item threshold)
2. For each item: construct text, chunk if needed, embed
3. Batch insert into Zvec collection (replace existing collection)
4. Record sync timestamp in state file

### 8.2 Delta Sync (Future Enhancement)

Use Graph API delta queries to get only changed items:

```
GET /sites/{siteId}/lists/{listId}/items/delta?token={deltaToken}
```

1. Fetch changed items since last delta token
2. For changed/new items: re-embed and upsert into Zvec
3. For deleted items: remove from Zvec by record_id
4. Store new delta token

Delta sync reduces embedding costs and sync time but adds complexity (token management, deletion handling, error recovery). Implement after full sync is stable.

### 8.3 Graph API Pagination for Large Lists

The Graph API `GET /lists/{id}/items` endpoint has a 5,000 item threshold on unindexed column filters. For full enumeration (no filters), pagination works normally:

```
GET /sites/{siteId}/lists/{listId}/items?$top=200&$expand=fields
→ Follow @odata.nextLink until exhausted
```

Each page returns up to 200 items. For 5,000 items, that's ~25 API calls per sync. Within Graph API rate limits.

### 8.4 Embedding Batching

Azure OpenAI's embedding API supports batch requests. Group records into batches of up to 16 texts per API call (the API limit for `text-embedding-3-small` is 2048 inputs per request, but smaller batches are more reliable).

Batch size: 50 texts per API call.
Parallelism: 5 concurrent requests (stay within rate limits).

---

## 9. Search Behavior

### 9.1 Hybrid Search

For each query, Zvec executes:

1. **Vector similarity search:** Find the top N documents whose `content_vector` is closest to the query's embedding vector (cosine similarity)
2. **Metadata filtering:** If the query includes filters (explicit or extracted), apply them as pre-filters before vector search

Zvec does not have native BM25 keyword search. Vector search is the primary ranking mechanism. For most queries on structured + free text data, this is sufficient. See section 11.2 for the BM25 gap mitigation strategy.

### 9.2 Score Normalization (Cross-List Search)

When searching across multiple collections, raw similarity scores may not be directly comparable (different collections have different content distributions). Normalize per collection:

```python
def normalize_scores(results_per_collection):
    all_results = []
    for source, results in results_per_collection.items():
        if not results:
            continue
        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)
        range_score = max_score - min_score if max_score > min_score else 1.0
        for r in results:
            r.normalized_score = (r.score - min_score) / range_score
            r.source = source
            all_results.append(r)
    return sorted(all_results, key=lambda r: r.normalized_score, reverse=True)
```

### 9.3 Chunk Deduplication

When a record has multiple chunks, multiple chunks may match the same query. Deduplicate:

1. Group results by `(source, record_id)`
2. For each group, keep the chunk with the highest score
3. Optionally: for the top results, fetch all chunks of that record and concatenate them for richer context

### 9.4 Filter Extraction (Future Enhancement)

Currently, filters must be passed explicitly by the MCP client. A future enhancement could extract filters from natural language queries:

- "open high priority items about VPN" → `filters: {Status: "Open", Priority: "High"}`, `query: "VPN"`
- "items assigned to Jan" → `filters: {AssignedTo: "Jan de Vries"}`, `query: "*"`

This could be done with a small LLM call (GPT-4o-mini) or with rule-based extraction using the known filter values from the collection schema.

---

## 10. Configuration

### 10.1 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TENANT_ID` | yes | Azure AD tenant ID |
| `CLIENT_ID` | yes | Azure AD app registration client ID |
| `CLIENT_SECRET` | yes | Azure AD app registration client secret |
| `EMBEDDING_PROVIDER` | no | `azure_openai` (default), `openai`, or `local` |
| `AZURE_OPENAI_ENDPOINT` | if Azure | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_KEY` | if Azure | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | if Azure | Deployment name (default: `text-embedding-3-small`) |
| `OPENAI_API_KEY` | if OpenAI | OpenAI API key |
| `LOCAL_MODEL_NAME` | if local | HuggingFace model name (default: `all-MiniLM-L6-v2`) |
| `MCP_TRANSPORT` | no | `stdio` (default) or `sse` |
| `MCP_PORT` | if SSE | Port for SSE transport (default: 8080) |
| `DATA_DIR` | no | Persistent data directory (default: `/data`) |
| `LOG_LEVEL` | no | Logging level (default: `INFO`) |

### 10.2 Source Config (Auto-Generated)

Persisted to `{DATA_DIR}/config/sources.json` after `ingest_list` calls. Can also be pre-populated for automated deployments:

```json
{
  "sources": [
    {
      "name": "IT Requests",
      "site_id": "contoso.sharepoint.com,{guid},{guid}",
      "list_id": "{guid}",
      "list_name": "Requests",
      "site_url": "https://contoso.sharepoint.com/sites/IT",
      "collection_name": "src_IT_Requests_abc123",
      "sync_interval_minutes": 60,
      "column_overrides": {},
      "schema_hash": "a1b2c3d4..."
    }
  ]
}
```

### 10.3 Azure AD App Registration

Required Graph API permissions:

| Permission | Type | Scope |
|---|---|---|
| `Sites.Read.All` | Application | Read all site collections and lists |
| OR `Sites.Selected` | Application | Scoped to specific sites (more secure, more setup) |

The app registration needs admin consent for application permissions.

### 10.4 Delegated Auth Configuration

When `AUTH_ENABLED=true`, the server uses FastMCP's `AzureProvider` for OAuth2 authentication with Entra ID.

| Variable | Required | Description |
|---|---|---|
| `AUTH_ENABLED` | no | Enable delegated auth (default: `false`) |
| `MCP_BASE_URL` | if auth | Public URL of the MCP server for OAuth redirects |
| `MCP_IDENTIFIER_URI` | if auth | Application ID URI from Entra app registration |
| `MCP_REQUIRED_SCOPES` | no | Scopes required for consumer tools (default: `mcp-access`) |
| `MCP_GRAPH_SCOPES` | no | Graph scopes for OBO token exchange (default: `https://graph.microsoft.com/Sites.Read.All`) |

**How it works:**
1. User authenticates via OAuth2 flow (authorization code grant)
2. FastMCP validates the access token and extracts scopes
3. Consumer tools (search, discover, list_sources) are available to all authenticated users
4. Admin tools (ingest, refresh, remove, list_sources_admin) require the `mcp-admin` scope
5. For search operations, the server exchanges the user's token for a Graph API token using the On-Behalf-Of (OBO) flow
6. Search results are security-trimmed: the server checks each result's SharePoint list permissions against the user's Graph token, filtering out items the user cannot access

**Security trimming details:**
- Each ingested item stores a `list_path` in its Zvec metadata
- At search time, the server batch-checks user access to the SharePoint lists referenced in results
- Items from lists the user cannot access are removed before returning results
- Collections ingested before the auth feature lack `list_path` metadata — security trimming is skipped with a warning log; re-ingest to enable

**Tool split:**

| Tool | Auth Required | Scope |
|---|---|---|
| `get_site_lists_tool` | Yes (any scope) | Consumer |
| `discover_list_tool` | Yes (any scope) | Consumer |
| `search_tool` | Yes (any scope) | Consumer |
| `search_all_tool` | Yes (any scope) | Consumer |
| `list_sources_tool` | Yes (any scope) | Consumer |
| `ingest_list_tool` | Yes | `mcp-admin` |
| `refresh_tool` | Yes | `mcp-admin` |
| `remove_source_tool` | Yes | `mcp-admin` |
| `list_sources_admin_tool` | Yes | `mcp-admin` |

---

## 11. Deployment

### 11.1 Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY src/ src/

VOLUME /data

# For SSE transport:
EXPOSE 8080

ENTRYPOINT ["python", "-m", "src.server"]
```

```yaml
# docker-compose.yml
services:
  sharepoint-search:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    environment:
      - TENANT_ID=${TENANT_ID}
      - CLIENT_ID=${CLIENT_ID}
      - CLIENT_SECRET=${CLIENT_SECRET}
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      - AZURE_OPENAI_KEY=${AZURE_OPENAI_KEY}
      - EMBEDDING_PROVIDER=azure_openai
      - MCP_TRANSPORT=sse
      - MCP_PORT=8080
```

### 11.2 Deployment Targets

| Target | Transport | Notes |
|---|---|---|
| Local (Claude Desktop, Claude Code) | stdio | Run as a local process, no container needed |
| Nuce150 (Portainer/Coolify) | SSE | Docker container, persistent volume |
| Azure App Service | SSE | B1 tier (1.75 GB RAM), sufficient for 20+ lists |
| Azure Container Apps | SSE | Consumption plan, scales to zero (cold start implications for Zvec) |
| Copilot Studio (Agent 365) | SSE | Register as external MCP server via tooling gateway |

**Note on Azure Container Apps:** Zvec is in-process and loads the index from disk on startup. If the container scales to zero and cold-starts, there will be a delay while Zvec reloads. For production, use a minimum replica count of 1 or use App Service instead.

---

## 12. Resource Estimates

### 12.1 Per List

| Metric | Small List (1,000 items) | Medium List (5,000 items) | Large List (10,000 items) |
|---|---|---|---|
| Records (no chunking) | 1,000 docs | 5,000 docs | 10,000 docs |
| Records (with chunking, 20% long) | ~2,800 docs | ~14,000 docs | ~28,000 docs |
| RAM (Zvec, estimated) | ~10 MB | ~50 MB | ~100 MB |
| Disk (Zvec, estimated) | ~20 MB | ~100 MB | ~200 MB |
| Ingest time (Azure OpenAI) | ~20 sec | ~95 sec | ~190 sec |
| Embedding cost (full sync) | ~$0.01 | ~$0.05 | ~$0.10 |

### 12.2 Multi-List Totals

| Lists | Total Records | Total Chunks (est.) | RAM (est.) | Disk (est.) | Monthly Embedding Cost (hourly sync) |
|---|---|---|---|---|---|
| 1 | 5,000 | 14,000 | ~50 MB | ~100 MB | ~$3 |
| 5 | 25,000 | 70,000 | ~250 MB | ~500 MB | ~$15 |
| 10 | 50,000 | 140,000 | ~500 MB | ~1 GB | ~$30 |
| 20 | 100,000 | 280,000 | ~1 GB | ~2 GB | ~$60 |

All of these fit comfortably on a B1 App Service (1.75 GB RAM) or the Nuce150.

---

## 13. Risks and Mitigations

### 13.1 Zvec Maturity

**Risk:** Zvec is relatively new (open sourced 2025). Less ecosystem support than FAISS, Qdrant, or Chroma.
**Mitigation:** The `store.py` module abstracts Zvec behind an interface. Swapping to FAISS or Qdrant later requires changing one module. Zvec is backed by Alibaba's Proxima engine which has production history at scale.

### 13.2 No BM25 Keyword Search

**Risk:** Pure vector search may miss exact-match queries (e.g., searching for a specific ticket number "INC-4521" or an exact product name).
**Mitigation options:**
- Store the raw `content` field as a searchable scalar in Zvec and do a string-contains pre-check before vector search
- Use Zvec's sparse vector support to store BM25-style term vectors alongside dense embeddings (adds complexity)
- Add a fallback: if vector search returns low-confidence results (score < threshold), fall back to a Graph API KQL search

### 13.3 Container Persistence

**Risk:** If the Docker volume is lost, all indexed data is gone.
**Mitigation:** The index can always be rebuilt by re-running `ingest_list` for each source (the source config is also on the volume, so back up the config separately or store it in environment/config management). Ingest for 5,000 items takes ~2 minutes.

### 13.4 Graph API Rate Limits

**Risk:** Microsoft Graph API has throttling limits. Syncing many large lists simultaneously could hit rate limits.
**Mitigation:** Stagger sync schedules across lists. Implement retry with exponential backoff. Use batch requests where possible. For 10 lists at 5,000 items each, the total API calls per sync cycle is ~250, well within limits.

### 13.5 Embedding Model Dependency

**Risk:** Azure OpenAI outage or API changes could break the embedding pipeline.
**Mitigation:** The embedding service is swappable. Configure `local` as a fallback option. The local model produces different vectors (different dimensions), so switching requires a full re-ingest, but the pipeline handles that automatically.

### 13.6 Schema Changes

**Risk:** If a SharePoint list's schema changes (columns added, removed, renamed), the Zvec collection schema becomes stale.
**Mitigation:** On each sync, re-run schema discovery and compare against the stored schema hash. If changed, log a warning and optionally trigger a full re-ingest with the updated schema. Zvec supports schema evolution for adding new scalar fields.

---

## 14. Future Enhancements

### 14.1 Delta Sync

Replace full sync with Graph API delta queries for incremental updates. Reduces embedding costs and sync time for large, slowly changing lists.

### 14.2 Filter Extraction from Natural Language

Use a small LLM to parse structured filters from user queries automatically, so the MCP client doesn't need to construct filters explicitly.

### 14.3 Sparse Vectors for Keyword Search

Generate BM25 or SPLADE sparse vectors alongside dense embeddings. Use Zvec's native multi-vector query support for true hybrid search (dense + sparse + metadata filters).

### 14.4 Attachment Indexing

Extract text from SharePoint list item attachments (PDF, DOCX, etc.), embed alongside the list item content.

### 14.5 Permission-Aware Search — IMPLEMENTED

Delegated auth with security trimming is now available. When `AUTH_ENABLED=true`, search results are filtered using the user's Graph API token via OBO flow. See section 10.4 for details.

### 14.6 Web UI for Configuration

Simple web interface (served from the same container) for registering lists, reviewing classifications, triggering syncs, and monitoring status. Not a priority if the MCP tools handle everything, but useful for non-technical admins.

### 14.7 Multi-Tenant Support

Support multiple Azure AD tenants in a single deployment, each with their own credentials and lists. Useful for ISV or consulting scenarios.

---

## 15. Project Structure

```
sharepoint-list-search-mcp/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── src/
│   ├── __init__.py
│   ├── server.py               # MCP server entry point (FastMCP)
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── discover.py         # discover_list tool
│   │   ├── ingest.py           # ingest_list tool
│   │   ├── search.py           # search + search_all tools
│   │   ├── manage.py           # get_record, refresh, list_sources, remove_source
│   │   └── types.py            # Shared types and models
│   ├── sharepoint/
│   │   ├── __init__.py
│   │   ├── client.py           # Graph API client (auth, requests)
│   │   ├── schema.py           # Schema discovery and parsing
│   │   └── pagination.py       # List item pagination helper
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── classifier.py       # Column classification rules
│   │   ├── template.py         # Embedding text template generation
│   │   ├── chunker.py          # Text chunking with overlap
│   │   └── embedder.py         # Embedding service (Azure OpenAI / local)
│   ├── store/
│   │   ├── __init__.py
│   │   ├── zvec_store.py       # Zvec collection management
│   │   └── interface.py        # Abstract store interface (for future swap)
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── scheduler.py        # Background sync scheduler
│   │   └── full_sync.py        # Full sync orchestration
│   └── config/
│       ├── __init__.py
│       ├── settings.py         # Environment-based settings
│       └── source_config.py    # Source config persistence
├── tests/
│   ├── test_classifier.py
│   ├── test_chunker.py
│   ├── test_template.py
│   ├── test_search.py
│   └── test_sync.py
└── data/                       # Persistent storage (Docker volume)
    ├── zvec/                   # Zvec collections
    ├── config/                 # Source configs and schema caches
    └── state/                  # Sync state (timestamps, delta tokens)
```
