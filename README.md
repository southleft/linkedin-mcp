# LinkedIn Intelligence MCP Server

> **Connect Claude Desktop to LinkedIn for feed monitoring, people search, and messaging.**

The LinkedIn MCP Server connects Claude Desktop to LinkedIn, enabling natural language conversations to browse your feed, search for people and companies, and manage messages—all without leaving your AI assistant.

---

## What Works Today

| Feature | Status | Example |
|---------|--------|---------|
| **Browse your feed** | ✅ Working | *"Show me posts from my network about AI"* |
| **Get your profile** | ✅ Working | *"What does my LinkedIn profile say?"* |
| **Search for people** | ✅ Working | *"Find software engineers with 'VP' in their title"* |
| **Search for companies** | ✅ Working | *"Search for fintech companies"* |
| **View conversations** | ✅ Working | *"Show my recent LinkedIn messages"* |
| **Send messages** | ✅ Working | *"Send a message to [connection]"* |
| **Create posts** | ✅ Working | *"Post this to LinkedIn"* |
| **Send connection requests** | ✅ Working | *"Send a connection request to [person]"* |

### Known Limitations

> **Important**: This uses LinkedIn's unofficial API which has significant limitations:

| Feature | Status | Notes |
|---------|--------|-------|
| Get other profiles | ⚠️ Unreliable | Often fails with API errors |
| Get anyone's posts | ❌ Broken | LinkedIn API returns errors |
| Analyze post engagement | ❌ Broken | Depends on profile posts |
| Region/location filters | ❌ Not working | Returns empty results |
| Connection list | ❌ Broken | API endpoint issues |
| Pending invitations | ❌ Broken | Redirect loop errors |
| Contact info | ❌ Broken | Redirect loop errors |

The underlying [linkedin-api](https://github.com/tomquirk/linkedin-api) library has known issues with many endpoints. This MCP exposes what's available, but LinkedIn frequently changes their internal APIs.

---

## Realistic Use Cases

<details>
<summary><h3>🔍 Feed Monitoring & Content Discovery</h3></summary>

**What actually works:**

- Browse your LinkedIn feed with natural language
- Filter posts by topic or keyword
- See what your network is talking about

**Example prompts that work:**
- *"Show me the latest 10 posts from my feed"*
- *"What are people in my network posting about AI?"*
- *"Find posts mentioning 'product launch' in my feed"*

**Tools used:**
- `get_feed()` - Retrieve your home feed
- `get_my_profile()` - Get your own profile data

</details>

<details>
<summary><h3>🎯 People & Company Search</h3></summary>

**What actually works:**

- Search for people by keywords and job title
- Search for companies by name or industry
- Basic filtering by title keywords

**Example prompts that work:**
- *"Search for people with 'Product Manager' in their title"*
- *"Find engineers who work in fintech"*
- *"Search for companies in the AI space"*

**What doesn't work:**
- Location/region filtering (returns empty)
- Getting detailed profiles of search results
- Viewing posts from people you find

**Tools used:**
- `search_people(keywords, keyword_title)` - Find people
- `search_companies(keywords)` - Find companies

</details>

<details>
<summary><h3>💬 Messaging</h3></summary>

**What actually works:**

- View your conversation threads
- Send messages to connections
- Read message history

**Example prompts that work:**
- *"Show me my recent LinkedIn conversations"*
- *"Send a message to [connection name] saying..."*
- *"What was my last conversation with [person]?"*

**Tools used:**
- `get_conversations()` - List message threads
- `send_message(profile_id, text)` - Send a message

</details>

<details>
<summary><h3>✍️ Content Creation</h3></summary>

**What actually works:**

- Create and publish LinkedIn posts
- Draft content for review

**Example prompts that work:**
- *"Post this to LinkedIn: [your content]"*
- *"Create a LinkedIn post about [topic]"*

**What doesn't work:**
- Scheduling posts (scheduler exists but untested)
- Analyzing your past post performance
- Seeing engagement on your posts

**Tools used:**
- `create_post(text, visibility)` - Publish a post

</details>

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Claude Desktop
- LinkedIn account

### Installation

```bash
# Clone the repository
git clone https://github.com/southleft/linkedin-mcp.git
cd linkedin-mcp

# Set up environment
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Create data directory
mkdir -p data
```

### Authentication

Export your LinkedIn cookies from an active browser session:

1. Log into LinkedIn in Chrome/Firefox
2. Open DevTools → **Application** (Chrome) or **Storage** (Firefox)
3. Find Cookies → `https://www.linkedin.com`
4. Copy `li_at` and `JSESSIONID` values

Create `data/session_cookies.json`:

```json
{
  "li_at": "YOUR_LI_AT_COOKIE_VALUE",
  "JSESSIONID": "\"ajax:1234567890123456789\""
}
```

> **Note**: The `JSESSIONID` typically includes escaped quotes. Copy exactly as shown in your browser.

### Claude Desktop Configuration

Add to your Claude Desktop config file:

| Platform | Config Location |
|----------|----------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["run", "linkedin-mcp"],
      "cwd": "/absolute/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_API_ENABLED": "true",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

> **Important**: The `cwd` must be an **absolute path** to the project directory.

**Restart Claude Desktop** and verify with: *"Use debug_context to check LinkedIn MCP status"*

---

## Working Tools Reference

### Verified Working ✅

| Tool | Description |
|------|-------------|
| `debug_context()` | Check server status |
| `get_my_profile()` | Get your own profile |
| `get_feed(limit)` | Browse your feed |
| `search_people(keywords, keyword_title)` | Search for people |
| `search_companies(keywords)` | Search for companies |
| `get_conversations()` | List message threads |
| `send_message(profile_id, text)` | Send a message |
| `create_post(text, visibility)` | Create a post |
| `send_connection_request(profile_id, message)` | Send connection invite |

### Unreliable/Broken ⚠️

These tools exist but may not work reliably due to LinkedIn API limitations:

| Tool | Issue |
|------|-------|
| `get_profile(profile_id)` | Often returns API errors |
| `get_profile_posts(profile_id)` | LinkedIn API blocks this |
| `get_connections()` | Missing parameter bug |
| `get_pending_invitations()` | Redirect loop |
| `get_profile_contact_info()` | Redirect loop |
| `analyze_*` functions | Depend on broken endpoints |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_API_ENABLED` | `false` | Enable the LinkedIn API client |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/linkedin_mcp.db` | Database connection URL |

---

## Troubleshooting

<details>
<summary><strong>"LinkedIn client not initialized"</strong></summary>

1. Ensure `LINKEDIN_API_ENABLED` is set to `"true"` (as a string) in Claude Desktop config
2. Verify `data/session_cookies.json` exists with valid cookies
3. Check that cookies haven't expired (re-export from browser if needed)
4. Verify the `cwd` path is **absolute**, not relative

</details>

<details>
<summary><strong>Cookies expire frequently</strong></summary>

LinkedIn session cookies typically last 1-2 weeks. If you're getting authentication errors:

1. Log into LinkedIn in your browser
2. Re-export the `li_at` and `JSESSIONID` cookies
3. Update `data/session_cookies.json`
4. Restart Claude Desktop

</details>

<details>
<summary><strong>View server logs</strong></summary>

```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp-server-linkedin.log

# Windows (PowerShell)
Get-Content -Path "$env:APPDATA\Claude\logs\mcp-server-linkedin.log" -Wait

# Linux
tail -f ~/.config/Claude/logs/mcp-server-linkedin.log
```

</details>

---

## Security & Responsible Use

> **Important**: This server uses the unofficial LinkedIn API which accesses LinkedIn's internal Voyager API.

- **Use a secondary LinkedIn account for testing**
- Respect rate limits (~900 requests/hour)
- Don't spam or automate engagement excessively
- Your account may be restricted if LinkedIn detects automation
- **Never commit your `data/` directory or cookie files**

---

## Development

```bash
# Run tests
pytest tests/ -v --cov=linkedin_mcp

# Linting
ruff check src/ && ruff format src/

# Type checking
mypy src/linkedin_mcp

# Run locally
uv run linkedin-mcp
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - Unofficial LinkedIn API
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol
