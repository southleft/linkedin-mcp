# LinkedIn MCP Server

> **AI-powered LinkedIn content creation, analytics, and engagement.**
> Create posts, analyze performance, manage drafts, and grow your professional presence—all through natural conversation with Claude.

A Model Context Protocol (MCP) server that connects Claude to LinkedIn for content creation, scheduling, and analytics.

---

## ✅ What's Working (Tested & Verified)

### Content Creation (Official API)
| Capability | Example Prompt | Status |
|-----------|----------------|--------|
| **Create Posts** | *"Create a LinkedIn post about AI trends"* | ✅ Working |
| **Image Posts** | *"Post this image with a caption about our launch"* | ✅ Working |
| **Create Polls** | *"Create a poll asking about favorite programming languages"* | ✅ Working |
| **Delete Posts** | *"Delete my last post"* | ✅ Working |
| **Get My Profile** | *"Show me my LinkedIn profile"* | ✅ Working |

### Content Planning (Local Features)
| Capability | Example Prompt | Status |
|-----------|----------------|--------|
| **Draft Content** | *"Save this as a draft for later"* | ✅ Working |
| **List Drafts** | *"Show my saved drafts"* | ✅ Working |
| **Publish Drafts** | *"Publish my 'Product Launch' draft"* | ✅ Working |
| **Schedule Posts** | *"Schedule this post for Tuesday at 9am"* | ✅ Working |
| **Manage Schedule** | *"Show my scheduled posts"* | ✅ Working |
| **Content Analysis** | *"Analyze this draft and suggest improvements"* | ✅ Working |

### Profile Viewing (Browser Automation)
| Capability | Example Prompt | Status |
|-----------|----------------|--------|
| **View Profiles** | *"Look up Bill Gates on LinkedIn"* | ⚠️ Limited (browser fallback) |

---

## ⚠️ Known Limitations

**LinkedIn actively blocks unofficial API access.** The following features are currently unreliable due to LinkedIn's bot detection:

| Feature | Status | Notes |
|---------|--------|-------|
| Search people | ❌ Blocked | LinkedIn redirect loops |
| Search companies | ❌ Blocked | LinkedIn redirect loops |
| Connection list | ❌ Blocked | Use official API for own profile |
| Feed browsing | ❌ Blocked | No current workaround |
| Messaging | ❌ Blocked | LinkedIn security restrictions |
| Network statistics | ❌ Blocked | Limited data available |
| Company details | ❌ Blocked | No current workaround |

**Profile viewing has a fallback:** When the API is blocked, the server automatically falls back to browser automation with anti-detection measures (curl_cffi TLS fingerprinting + Playwright headless browser).

These use the `tomquirk/linkedin-api` library which LinkedIn frequently blocks. **When blocked, errors include helpful suggestions for resolving the issue.**

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- LinkedIn account
- LinkedIn Developer App (free, 5 min setup)

### Step 1: Clone and Install

```bash
git clone https://github.com/southleft/linkedin-mcp.git
cd linkedin-mcp

# Install with uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e .

# Install browser automation (optional, for profile viewing)
playwright install chromium
```

### Step 2: Create LinkedIn Developer App

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps)
2. Click **"Create app"**
3. Fill in the details:
   - **App name**: e.g., "My LinkedIn MCP"
   - **LinkedIn Page**: Select or create a company page
   - **Privacy policy URL**: Your website or LinkedIn profile
   - **App logo**: Any 100x100 image
4. Go to **"Products"** tab → Request **"Share on LinkedIn"** (instant approval)
5. Go to **"Auth"** tab:
   - Copy **Client ID** and **Client Secret**
   - Add redirect URL: `http://localhost:8765/callback`

### Step 3: Configure Environment

Create a `.env` file:

```bash
# LinkedIn OAuth Credentials (Required)
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here

# Enable API features
LINKEDIN_API_ENABLED=true
```

### Step 4: Authenticate

```bash
# OAuth authentication (opens browser, required for posting)
linkedin-mcp-auth oauth

# Extract browser cookies (optional, for additional features)
linkedin-mcp-auth extract-cookies --browser chrome

# Verify status
linkedin-mcp-auth status
```

### Step 5: Connect to Claude

#### Claude Code (Recommended)

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "linkedin-mcp": {
      "type": "stdio",
      "command": "/path/to/python3",
      "args": ["-m", "linkedin_mcp"],
      "cwd": "/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_API_ENABLED": "true",
        "PYTHONPATH": "/path/to/linkedin-mcp/src"
      }
    }
  }
}
```

Then run `/mcp` in Claude Code to connect.

#### Claude Desktop

Add to your config file:

| Platform | Config Location |
|----------|----------------|
| **macOS** | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| **Windows** | `%APPDATA%\Claude\claude_desktop_config.json` |
| **Linux** | `~/.config/Claude/claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "/path/to/linkedin-mcp/.venv/bin/python",
      "args": ["-m", "linkedin_mcp"],
      "cwd": "/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_API_ENABLED": "true"
      }
    }
  }
}
```

Restart Claude Desktop after updating.

---

## Available Tools

### ✅ Reliable Tools (Official API + Local)

#### Profile
| Tool | Description |
|------|-------------|
| `get_my_profile()` | Get your LinkedIn profile |
| `get_auth_status()` | Check authentication status |

#### Content Creation
| Tool | Description |
|------|-------------|
| `create_post(text, visibility)` | Create a text post |
| `create_image_post(text, image_path)` | Create a post with image |
| `create_poll(question, options)` | Create a poll |
| `delete_post(post_urn)` | Delete a post |

#### Drafts & Scheduling
| Tool | Description |
|------|-------------|
| `create_draft(content, title, tags)` | Save content for later |
| `list_drafts()` | List all drafts |
| `get_draft(draft_id)` | Get a specific draft |
| `update_draft(draft_id, ...)` | Update a draft |
| `delete_draft(draft_id)` | Delete a draft |
| `publish_draft(draft_id)` | Publish a draft |
| `schedule_post(content, time)` | Schedule for future |
| `list_scheduled_posts()` | View scheduled posts |
| `cancel_scheduled_post(job_id)` | Cancel scheduled post |
| `update_scheduled_post(job_id, ...)` | Update scheduled post |

#### Content Analysis
| Tool | Description |
|------|-------------|
| `analyze_draft_content(content)` | Get improvement suggestions |

### ⚠️ Limited Tools (May Be Blocked)

These tools use the unofficial API and may fail due to LinkedIn's bot detection:

| Tool | Description | Fallback |
|------|-------------|----------|
| `get_profile(id)` | Get any profile | Browser automation |
| `search_people(keywords)` | Search for people | None |
| `search_companies(keywords)` | Search for companies | None |
| `get_connections(limit)` | List connections | None |
| `get_feed(limit)` | Browse feed | None |
| `get_network_stats()` | Network analysis | None |
| `send_message(id, text)` | Send DM | None |
| `get_company(id)` | Company details | None |

---

## Example Conversations

### Content Creator Workflow (✅ Reliable)

```
You: "I want to post about continuous learning in tech"

Claude: I'll help you create that post. Here's a draft:

"🚀 In tech, the day you stop learning is the day you start falling behind.

Whether it's a new framework or a completely new domain—curiosity is our greatest competitive advantage.

What are you learning this week? 👇

#ContinuousLearning #TechCareers #GrowthMindset"

Should I post this publicly or save it as a draft?
```

### Content Planning (✅ Reliable)

```
You: "Save this as a draft for my product launch next week"

Claude: Done! I've saved your draft titled "Product Launch" with tags: product, launch, announcement.

Would you like me to:
- Schedule it for a specific time?
- Analyze it for engagement potential?
- Show you all your drafts?
```

### Post Scheduling (✅ Reliable)

```
You: "Schedule my launch post for Tuesday at 9am Central"

Claude: ✅ Scheduled! Your post will go live:
- Date: Tuesday, January 7, 2025
- Time: 9:00 AM Central
- Visibility: Public

You can view or cancel scheduled posts anytime.
```

---

## CLI Commands

```bash
# Authentication
linkedin-mcp-auth status              # Check auth status
linkedin-mcp-auth oauth               # OAuth flow (opens browser)
linkedin-mcp-auth oauth --force       # Force re-authentication
linkedin-mcp-auth extract-cookies     # Extract session cookies
linkedin-mcp-auth logout --all        # Clear all credentials

# Run Server
linkedin-mcp                          # Start MCP server
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_CLIENT_ID` | - | OAuth Client ID (required) |
| `LINKEDIN_CLIENT_SECRET` | - | OAuth Client Secret (required) |
| `LINKEDIN_API_ENABLED` | `false` | Enable API features |
| `MCP_TRANSPORT` | `stdio` | Transport: stdio, streamable-http |
| `MCP_HOST` | `127.0.0.1` | HTTP server host |
| `MCP_PORT` | `8000` | HTTP server port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Troubleshooting

### "LinkedIn client not initialized"
```bash
linkedin-mcp-auth status    # Check what's configured
linkedin-mcp-auth oauth     # Re-authenticate
```

### "Exceeded 30 redirects" or "RetryError"
LinkedIn is blocking API access. This is common with the unofficial API. Solutions:
1. Refresh cookies: `linkedin-mcp-auth extract-cookies --browser chrome`
2. Wait and retry later
3. Use official API tools (posting, drafts, scheduling)

### "Application context not initialized"
Reconnect the MCP server: Run `/mcp` in Claude Code.

### Posts not appearing
- Ensure OAuth is authenticated: `linkedin-mcp-auth status`
- Check your Developer App has "Share on LinkedIn" product enabled

---

## Security

- **OAuth tokens**: Stored securely in system keychain
- **Session cookies**: Stored in system keychain (never transmitted)
- **Credentials**: Loaded from environment variables
- **No data collection**: Everything runs locally

---

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Linting
ruff check src/ && ruff format src/

# Type checking
mypy src/linkedin_mcp
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - LinkedIn API library
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol
- [curl_cffi](https://github.com/lexiforest/curl_cffi) - TLS fingerprint spoofing for anti-detection
- [Playwright](https://playwright.dev/) - Browser automation fallback

---

**Built with ❤️ for AI-powered content creators**
