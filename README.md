# SharePoint List Semantic Search MCP Server

A powerful, self-contained Model Context Protocol (MCP) server that brings **semantic search** and **vector-based retrieval** to your SharePoint Lists.

Connect your AI agents (Claude, Copilot, etc.) directly to your SharePoint data without complex infrastructure.

## 🚀 Capabilities

This server acts as a bridge between SharePoint and your AI, providing:

*   **🔍 Semantic Search:** Find items by meaning, not just keywords (e.g., search "network issues" to find "VPN connectivity failing").
*   **🧠 Auto-Discovery:** Point it at a SharePoint list, and it automatically detects the schema, classifying columns as embeddable text, filters, or metadata.
*   **📚 Smart Chunking:** Handles long text fields (like descriptions or notes) by splitting them into semantic chunks while preserving context.
*   **⚡ High Performance:** Uses **Zvec** (an in-process, high-speed vector database) for millisecond-latency searches. No external vector DB required.
*   **🔄 Background Sync:** Automatically keeps the search index up-to-date with a configurable background scheduler.
*   **🛡️ Secure Access:** Supports standard Azure AD App-Only authentication with granular `Sites.Selected` permissions.
*   **🌐 Flexible Deployment:** Runs anywhere Python runs (local, Docker, Azure Container Apps).

## 🛠️ Prerequisites

*   **Python 3.12+**
*   **uv** (recommended for dependency management) or pip
*   **Docker** (optional, for containerized deployment)
*   **Azure Subscription** (for App Registration and Azure OpenAI embeddings)
*   **SharePoint Online** site with lists to index

---

## 🔐 Setup Guide: Authentication & Authorization

This server uses **Azure AD App-Only Authentication**. This means it runs as a service principal, not a signed-in user. You must register an app in Azure AD and grant it permissions to read your SharePoint sites.

### 🚀 Automation Script

Run the included setup script to automate App Registration, Client Secret creation, and Permission assignment:

```bash
./setup_azure_auth.sh
```

Follow the prompts.

### Step 1: Create an App Registration (Manual)

1.  Go to the [Azure Portal](https://portal.azure.com).
2.  Navigate to **Microsoft Entra ID** > **App registrations** > **New registration**.
3.  **Name:** `SharePoint-List-MCP-Search` (or similar).
4.  **Supported account types:** "Accounts in this organizational directory only (Single tenant)".
5.  Click **Register**.

### Step 2: Get Credentials (Manual)

After registration, copy the following values to a temporary notepad:
*   **Application (client) ID**
*   **Directory (tenant) ID**

Then, generate a secret:
1.  Go to **Certificates & secrets** > **New client secret**.
2.  **Description:** "MCP Server Secret".
3.  **Expires:** 12 months (or as desired).
4.  Click **Add**.
5.  **COPY THE VALUE IMMEDIATELY.** You won't see it again. This is your `CLIENT_SECRET`.

### Step 3: Grant API Permissions (Manual)

1.  Go to **API permissions** > **Add a permission** > **Microsoft Graph**.
2.  Select **Application permissions**.
3.  Search for and select one of the following (choose based on your security needs):

    *   **Option A (Easiest): `Sites.Read.All`**
        *   Gives the bot read access to **ALL** SharePoint sites in your tenant.
        *   *Use only for testing or if the bot is intended to search everything.*

    *   **Option B (Recommended): `Sites.Selected`**
        *   Gives the bot **NO** access by default. You must explicitly grant read access to specific sites.
        *   *Best for production security.*

4.  Click **Add permissions**.
5.  **IMPORTANT:** Click **Grant admin consent for [Your Org]** to activate the permissions.

### Step 4: Authorizing Specific Sites (If using `Sites.Selected`)

If you chose `Sites.Selected`, follow these steps to grant access to your target site:

1.  Get the **Site ID** for your SharePoint site. You can find this via Graph Explorer (`https://graph.microsoft.com/v1.0/sites/{hostname}:/{relative-path}`).
2.  Use PowerShell (PnP) or a simple HTTP request to grant the permission.

**Using HTTP (Graph Explorer or Postman):**
*   **POST** `https://graph.microsoft.com/v1.0/sites/{site-id}/permissions`
*   **Body:**
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

---

## 💻 Installation & Usage

### 1. Clone and Install

```bash
git clone https://github.com/your-repo/sharepoint-list-mcp.git
cd sharepoint-list-mcp
uv sync
```

### 2. Configure Environment

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` and fill in your details:
```ini
# Azure AD Auth (from Step 2)
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

# Azure OpenAI (for embeddings)
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=text-embedding-3-small
```

### 3. Run the Server

**Local Development:**
```bash
uv run python -m src.server
```

**Docker (Recommended for Production):**
```bash
docker-compose up --build -d
```

### 4. Connect to Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sharepoint-search": {
      "command": "docker",
      "args": [
        "run", 
        "-i", 
        "--rm", 
        "-v", "/path/to/your/data:/app/data", 
        "--env-file", "/path/to/your/.env", 
        "sharepoint-list-mcp"
      ]
    }
  }
}
```

---

## 🤖 Available Tools

Once connected, your AI agent can use these tools:

| Tool | Description |
|---|---|
| `discover_list(site_url, list_name)` | Analyzes a list schema and suggests column classifications. |
| `ingest_list(site_url, list_name)` | Pulls all items, generates embeddings, and builds the index. |
| `search(query, source)` | Semantic search within a specific list. |
| `search_all(query)` | Search across all indexed lists, ranked by relevance. |
| `list_sources()` | View all configured lists and their sync status. |
| `refresh(source)` | Manually trigger a sync for a specific source. |
| `remove_source(source)` | Delete a list's index and configuration. |

---

## 🏗️ Architecture

*   **FastMCP:** Handles the MCP protocol communication.
*   **Zvec:** Provides embedded vector storage and search.
*   **APScheduler:** Manages background synchronization jobs.
*   **MSGraph SDK:** Connects to SharePoint.
*   **Tiktoken:** Ensures precise token counting for chunking.

---

## ⚠️ Limitations & Notes

*   **Permissions:** The bot sees all data granted to the App Registration. It does **not** impersonate the user. Be careful not to index sensitive HR or Legal lists unless the bot's users are authorized to see them.
*   **Rate Limits:** The Graph API has throttling limits. The background syncer is designed to be gentle, but indexing massive lists (100k+ items) initially may take time.