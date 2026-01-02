# LinkedIn MCP Server

> **AI-powered LinkedIn content creation, scheduling, and analytics.**
>
> Create posts, manage drafts, schedule content, analyze performance, and grow your professional presence—all through natural conversation with Claude.

A Model Context Protocol (MCP) server that connects Claude to LinkedIn, enabling seamless content workflows powered by the Official LinkedIn API and Fresh Data API.

---

## Features

### Content Creation
Create engaging LinkedIn content directly through conversation with Claude.

| Feature | Description |
|---------|-------------|
| **Text Posts** | Create and publish professional posts with AI assistance |
| **Image Posts** | Share images with captions and hashtags |
| **Polls** | Create interactive polls to engage your audience |
| **Rich Formatting** | AI-optimized content with hooks, CTAs, and hashtags |

### Content Planning
Plan and organize your LinkedIn content strategy.

| Feature | Description |
|---------|-------------|
| **Draft Management** | Save, edit, and organize drafts with tags |
| **Post Scheduling** | Schedule posts for optimal engagement times |
| **Content Calendar** | View and manage your scheduled content |
| **Content Analysis** | Get AI suggestions to improve engagement |

### Profile & Analytics
Monitor and optimize your LinkedIn presence.

| Feature | Description |
|---------|-------------|
| **Profile Enrichment** | Multi-source profile data from Fresh Data API |
| **Profile Viewing** | View your profile and others with comprehensive data |
| **Authentication Status** | Monitor API health and connection status |
| **Rate Limits** | Track API usage to avoid throttling |

### Research & Discovery
Find people, companies, and opportunities.

| Feature | Description |
|---------|-------------|
| **People Search** | Find professionals by keywords, title, company |
| **Company Search** | Research companies and organizations |
| **Company Details** | Get company info, employee counts, and more |
| **Organization Insights** | Follower counts via Community Management API |

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- LinkedIn account
- LinkedIn Developer App (free, 5-minute setup)

### Installation

```bash
git clone https://github.com/southleft/linkedin-mcp.git
cd linkedin-mcp

# Install with uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e .

# Install browser automation for profile enrichment
playwright install chromium
```

### LinkedIn Developer Setup

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps)
2. Click **"Create app"**
3. Fill in details:
   - **App name**: e.g., "My LinkedIn MCP"
   - **LinkedIn Page**: Select or create a company page
   - **Privacy policy URL**: Your website or LinkedIn profile
4. Go to **Products** → Request **"Share on LinkedIn"** (instant approval)
5. Go to **Auth** tab:
   - Copy **Client ID** and **Client Secret**
   - Add redirect URL: `http://localhost:8765/callback`

### Configuration

Create a `.env` file in the project root:

```bash
# LinkedIn OAuth (Required for posting)
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_API_ENABLED=true

# Fresh Data API (REQUIRED for reliable profile lookups)
# Without this, profile lookups will fail due to LinkedIn's bot detection
# Subscribe at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2
THIRDPARTY_RAPIDAPI_KEY=your_rapidapi_key
```

> **Important**: The Fresh Data API key is essential for profile lookups. LinkedIn aggressively blocks bot detection, making the unofficial API unreliable. The Fresh Data API provides consistent, reliable access to profile data.

### Authentication

```bash
# Authenticate with LinkedIn (opens browser)
linkedin-mcp-auth oauth

# Optional: Extract cookies for additional features
linkedin-mcp-auth extract-cookies --browser chrome

# Verify setup
linkedin-mcp-auth status
```

### Connect to Claude Desktop

Add the following to your Claude Desktop config file:

| Platform | Config Location |
|----------|-----------------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

**Complete configuration example:**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "/path/to/linkedin-mcp/.venv/bin/python",
      "args": ["-m", "linkedin_mcp.main"],
      "cwd": "/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_API_ENABLED": "true",
        "THIRDPARTY_RAPIDAPI_KEY": "your_rapidapi_key",
        "PYTHONPATH": "/path/to/linkedin-mcp/src",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

> **Critical**: You must include `THIRDPARTY_RAPIDAPI_KEY` in the `env` section. Claude Desktop does not read `.env` files—all environment variables must be explicitly passed in the config.

**After updating the config:**
1. Quit Claude Desktop completely
2. Reopen Claude Desktop
3. The LinkedIn MCP server will connect automatically

### Connect to Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "linkedin-mcp": {
      "type": "stdio",
      "command": "/path/to/linkedin-mcp/.venv/bin/python",
      "args": ["-m", "linkedin_mcp.main"],
      "cwd": "/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_API_ENABLED": "true",
        "THIRDPARTY_RAPIDAPI_KEY": "your_rapidapi_key",
        "PYTHONPATH": "/path/to/linkedin-mcp/src"
      }
    }
  }
}
```

Run `/mcp` in Claude Code to connect.

---

## Usage Examples

### Content Creator Workflow

```
You: "Create a LinkedIn post about the importance of continuous learning in tech"

Claude: Here's a draft optimized for engagement:

"In tech, the moment you stop learning is the moment you start falling behind.

Every new framework, language, or methodology is an opportunity to expand your toolkit and thinking.

The best engineers I know aren't just skilled—they're perpetually curious.

What are you learning this week?

#ContinuousLearning #TechCareers #GrowthMindset"

Should I post this now, schedule it, or save as a draft?
```

### Content Planning

```
You: "Save this as a draft for my product launch and schedule it for Tuesday 9am"

Claude: Done! I've:
1. Saved your draft titled "Product Launch"
2. Scheduled it for Tuesday, 9:00 AM (your timezone)

You can view your drafts anytime or adjust the schedule.
```

### Content Analysis

```
You: "Analyze my draft and suggest improvements"

Claude: Here's my analysis:

Content Score: 65/100

Suggestions:
- Add 3 relevant hashtags to increase discoverability
- Include a call-to-action to encourage comments
- Consider ending with a question to boost engagement
- Expand to 1200-2000 characters for optimal reach

Want me to apply these improvements?
```

### Profile Research

```
You: "Look up the CEO of Anthropic on LinkedIn"

Claude: Found Dario Amodei's profile:
- CEO at Anthropic
- Previously VP of Research at OpenAI
- Background in physics and AI safety research
```

---

## Available Tools

### Content Creation
| Tool | Description |
|------|-------------|
| `create_post(text, visibility)` | Publish a text post |
| `create_image_post(text, image_path, alt_text)` | Post with an image |
| `create_poll(question, options, duration_days)` | Create an interactive poll |
| `delete_post(post_urn)` | Remove a published post |

### Draft Management
| Tool | Description |
|------|-------------|
| `create_draft(content, title, tags)` | Save content for later |
| `list_drafts(tag)` | View all saved drafts |
| `get_draft(draft_id)` | Get a specific draft |
| `update_draft(draft_id, content, title, tags)` | Edit a draft |
| `delete_draft(draft_id)` | Remove a draft |
| `publish_draft(draft_id, visibility)` | Publish a saved draft |
| `analyze_draft_content(content, industry)` | Get AI suggestions |

### Scheduling
| Tool | Description |
|------|-------------|
| `schedule_post(content, scheduled_time, timezone)` | Schedule for future |
| `list_scheduled_posts(status)` | View scheduled posts |
| `get_scheduled_post(job_id)` | Get schedule details |
| `update_scheduled_post(job_id, content, time)` | Modify scheduled post |
| `cancel_scheduled_post(job_id)` | Cancel a scheduled post |

### Profile & Analysis
| Tool | Description |
|------|-------------|
| `get_my_profile()` | Get your LinkedIn profile |
| `get_profile(profile_id)` | View any LinkedIn profile (Fresh Data API) |
| `get_profile_contact_info(profile_id)` | Get contact details |
| `get_profile_skills(profile_id)` | Get skills and endorsements |
| `get_auth_status()` | Check authentication status |
| `get_rate_limit_status()` | Monitor API usage |

### Search & Discovery
| Tool | Description |
|------|-------------|
| `search_people(keywords, limit, keyword_title)` | Find professionals |
| `search_companies(keywords, limit)` | Search for companies |
| `get_company(public_id)` | Get company details |
| `get_organization_followers(organization_id)` | Get follower count |

### Engagement Analytics
| Tool | Description |
|------|-------------|
| `analyze_engagement(post_urn)` | Deep engagement analysis |
| `analyze_content_performance(profile_id)` | Content patterns |
| `analyze_optimal_posting_times(profile_id)` | Best times to post |
| `analyze_hashtag_performance(profile_id)` | Hashtag effectiveness |
| `generate_engagement_report(profile_id)` | Full engagement report |

### Connections & Messaging
| Tool | Description |
|------|-------------|
| `get_connections(limit)` | Get your connections |
| `send_connection_request(profile_id, message)` | Send connection request |
| `get_pending_invitations(sent)` | View pending invitations |
| `get_conversations(limit)` | Get message threads |
| `send_message(profile_id, text)` | Send a message |

---

## CLI Commands

```bash
# Authentication
linkedin-mcp-auth status              # Check auth status
linkedin-mcp-auth oauth               # Authenticate via OAuth
linkedin-mcp-auth oauth --force       # Force re-authentication
linkedin-mcp-auth extract-cookies     # Extract session cookies
linkedin-mcp-auth logout --all        # Clear all credentials

# Server
linkedin-mcp                          # Start MCP server
python -m linkedin_mcp                # Alternative server start
```

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_CLIENT_ID` | - | OAuth Client ID (required for posting) |
| `LINKEDIN_CLIENT_SECRET` | - | OAuth Client Secret (required for posting) |
| `LINKEDIN_API_ENABLED` | `false` | Enable API features |
| `THIRDPARTY_RAPIDAPI_KEY` | - | RapidAPI key for Fresh Data API |
| `MCP_TRANSPORT` | `stdio` | Transport: stdio, streamable-http |
| `MCP_HOST` | `127.0.0.1` | HTTP server host |
| `MCP_PORT` | `8000` | HTTP server port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Architecture

The server uses a **multi-tier data provider** with intelligent fallback:

```
Profile Request → Profile Enrichment Engine
                    ├── Fresh Data API (RapidAPI) - Primary, most reliable
                    ├── Official LinkedIn API - Authenticated user data
                    ├── linkedin-api library - Session-based scraping
                    └── Browser Automation - Headless fallback

Content Request → Official LinkedIn API (OAuth 2.0)
                    └── Share on LinkedIn product
```

### Data Sources

| Source | Use Case | Reliability |
|--------|----------|-------------|
| **Fresh Data API** | Profile viewing, search | High (paid API) |
| **Official API** | Posting, user profile | High (OAuth) |
| **linkedin-api** | Extended features | Medium (session) |
| **Browser** | Fallback scraping | Medium (automation) |

---

## Troubleshooting

**"Profile lookup returns bot detection error"**
This is the most common issue. LinkedIn blocks unofficial API access.

**Solution**: Add `THIRDPARTY_RAPIDAPI_KEY` to your Claude Desktop config:
```json
"env": {
  "THIRDPARTY_RAPIDAPI_KEY": "your_rapidapi_key",
  ...
}
```
Get your API key at: https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2

> **Important**: Claude Desktop does not read `.env` files. You must add the key directly to the config's `env` section.

**"LinkedIn client not initialized"**
```bash
linkedin-mcp-auth status    # Check configuration
linkedin-mcp-auth oauth     # Re-authenticate
```

**"Application context not initialized"**
Reconnect the MCP server:
- Claude Desktop: Quit and reopen the app
- Claude Code: Run `/mcp` to reconnect

**"Session redirect loop"**
```bash
linkedin-mcp-auth extract-cookies --browser chrome
```

**Posts not appearing**
- Verify OAuth: `linkedin-mcp-auth status`
- Ensure "Share on LinkedIn" product is enabled in Developer Portal

**Profile data incomplete or missing**
1. Ensure `THIRDPARTY_RAPIDAPI_KEY` is set in your Claude config
2. Restart Claude Desktop after config changes
3. The Fresh Data API is the primary source for profile data

---

## Security

- **OAuth tokens**: Stored securely in system keychain
- **Session cookies**: Encrypted local storage
- **Credentials**: Environment variables only
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

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol
- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - LinkedIn API library
- [curl_cffi](https://github.com/lexiforest/curl_cffi) - TLS fingerprinting
- [Playwright](https://playwright.dev/) - Browser automation
- [RapidAPI Fresh Data](https://rapidapi.com/freshdata-freshdata-default/api/web-scraping-api2) - LinkedIn profile API

---

**Built for AI-powered content creators**
