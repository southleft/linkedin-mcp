# LinkedIn MCP Server

> **AI-powered LinkedIn content creation, research, and analytics.**
>
> Create posts, manage drafts, schedule content, research professionals and companies, and analyze engagement—all through natural conversation with Claude.

A Model Context Protocol (MCP) server that connects Claude to LinkedIn, enabling seamless content workflows through official and enhanced data APIs.

---

## Architecture

### Intelligent API Fallback

The server uses a multi-source architecture that automatically falls back through APIs **ordered by reliability**:

| Priority | Source | Type | Reliability |
|----------|--------|------|-------------|
| 1 | Professional Network Data API | RapidAPI (paid) | Highest - 55 endpoints |
| 2 | Fresh LinkedIn Data API | RapidAPI (paid) | High - profiles & search |
| 3 | Enhanced HTTP Client | curl_cffi | Medium - anti-detection |
| 4 | Headless Browser | Playwright | Medium - slowest but reliable |
| 5 | Unofficial API | Cookie-based | Lowest - prone to blocking |

**Why this order?** The unofficial LinkedIn API (tomquirk/linkedin-api) relies on session cookies that expire and is prone to bot detection. By placing it **last**, the server prioritizes stable, paid APIs and only falls back to the brittle cookie-based method when all else fails.

This architecture ensures:
- **High availability** - Multiple fallback options
- **Automatic recovery** - Failures cascade gracefully
- **Best-effort data** - Always tries the most reliable source first

---

## Who Is This For?

### Content Creators & Marketers
- Create and schedule LinkedIn posts with AI-powered optimization
- Manage drafts, analyze content performance, and find optimal posting times
- Build a consistent content calendar without leaving your AI assistant

### Sales & Business Development
- Research prospects and companies before outreach
- Find similar profiles to identify new leads
- Look up companies by domain to qualify opportunities

### Recruiters & HR Professionals
- Research candidate profiles and backgrounds
- Discover professional interests and expertise areas
- Find similar professionals based on target profiles

### Analysts & Researchers
- Gather company and professional data at scale
- Analyze engagement patterns and content performance
- Generate comprehensive reports on LinkedIn presence

---

## Features

### Content Creation
| Feature | Description |
|---------|-------------|
| **Text Posts** | Create and publish professional posts with AI assistance |
| **Image Posts** | Share images with captions and hashtags |
| **Polls** | Create interactive polls to engage your audience |
| **Comments** | Comment on posts with optional image attachments |
| **Rich Formatting** | AI-optimized content with hooks, CTAs, and hashtags |

### Content Planning
| Feature | Description |
|---------|-------------|
| **Draft Management** | Save, edit, and organize drafts with tags |
| **Post Scheduling** | Schedule posts for optimal engagement times |
| **Content Calendar** | View and manage your scheduled content |
| **Content Analysis** | Get AI suggestions to improve engagement |

### Profile Research
| Feature | Description |
|---------|-------------|
| **Profile Viewing** | View detailed LinkedIn profiles |
| **Profile Enrichment** | Get comprehensive profile data with multi-source fallback |
| **Profile Interests** | Discover who/what a person follows (influencers, companies, topics) |
| **Similar Profiles** | Find profiles similar to a given person |
| **Profile Articles** | Get articles written by any profile |
| **Skills & Endorsements** | View skills and endorsement data |

### Company Research
| Feature | Description |
|---------|-------------|
| **Company Search** | Search for companies by keywords |
| **Company Details** | Get company info, employee counts, and descriptions |
| **Company by Domain** | Look up companies by website domain |
| **Organization Insights** | Follower counts and engagement data |

### Analytics & Engagement
| Feature | Description |
|---------|-------------|
| **Post Analytics** | Reactions, comments, and engagement metrics |
| **Content Performance** | Analyze what content works best |
| **Optimal Posting Times** | Find when your audience is most active |
| **Hashtag Analysis** | Measure hashtag effectiveness |
| **Engagement Reports** | Comprehensive performance reports |

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

# Install browser automation (optional, for enhanced features)
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

# Enhanced Data API (Recommended for reliable profile/company lookups)
# Powers the top 2 fallback sources: Professional Network Data API + Fresh LinkedIn Data API
THIRDPARTY_RAPIDAPI_KEY=your_api_key
```

> **Note**: The RapidAPI key enables the most reliable data sources in the fallback chain. Without it, the server falls back to cookie-based methods which are prone to LinkedIn's bot detection.

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
        "THIRDPARTY_RAPIDAPI_KEY": "your_api_key",
        "PYTHONPATH": "/path/to/linkedin-mcp/src",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

> **Critical**: Claude Desktop does not read `.env` files—all environment variables must be explicitly passed in the config.

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
        "THIRDPARTY_RAPIDAPI_KEY": "your_api_key",
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

### Profile Research

```
You: "Look up the CEO of Microsoft on LinkedIn"

Claude: Found Satya Nadella's profile:
- Chairman and CEO at Microsoft
- Focus on cloud computing and AI transformation
- Author and thought leader in technology

Would you like me to find similar profiles or see their recent articles?
```

### Company Research

```
You: "Look up information about anthropic.com"

Claude: Found Anthropic:
- AI safety company
- Headquarters in San Francisco
- Focus on AI research and safety

Would you like more details or to search for employees?
```

---

## Available Tools

### Content Creation
| Tool | Description |
|------|-------------|
| `create_post(text, visibility)` | Publish a text post |
| `create_image_post(text, image_path, alt_text)` | Post with an image |
| `create_poll(question, options, duration_days)` | Create an interactive poll |
| `create_comment(post_urn, text)` | Comment on a post |
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

### Profile Research
| Tool | Description |
|------|-------------|
| `get_my_profile()` | Get your LinkedIn profile |
| `get_profile(profile_id)` | View any LinkedIn profile |
| `get_profile_contact_info(profile_id)` | Get contact details |
| `get_profile_skills(profile_id)` | Get skills and endorsements |
| `get_profile_interests(profile_id)` | Get interests (influencers, companies, topics) |
| `get_similar_profiles(profile_id, limit)` | Find similar profiles |
| `get_profile_articles(profile_id, limit)` | Get articles written by profile |
| `get_auth_status()` | Check authentication status |
| `get_rate_limit_status()` | Monitor API usage |

### Company Research
| Tool | Description |
|------|-------------|
| `search_people(keywords, limit, keyword_title)` | Find professionals |
| `search_companies(keywords, limit)` | Search for companies |
| `get_company(public_id)` | Get company details |
| `get_company_by_domain(domain)` | Look up company by website domain |
| `get_article(article_url)` | Get full article content |
| `get_organization_followers(organization_id)` | Get follower count |

### Analytics
| Tool | Description |
|------|-------------|
| `get_feed(limit)` | Get your LinkedIn feed |
| `get_profile_posts(profile_id, limit)` | Get posts from a profile |
| `get_post_reactions(post_urn)` | Get reactions on a post |
| `get_post_comments(post_urn)` | Get comments on a post |
| `analyze_engagement(post_urn)` | Deep engagement analysis |
| `analyze_content_performance(profile_id)` | Content patterns |
| `analyze_optimal_posting_times(profile_id)` | Best times to post |
| `analyze_hashtag_performance(profile_id)` | Hashtag effectiveness |
| `generate_engagement_report(profile_id)` | Full engagement report |

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
| `THIRDPARTY_RAPIDAPI_KEY` | - | API key for enhanced profile data |
| `MCP_TRANSPORT` | `stdio` | Transport: stdio, streamable-http |
| `MCP_HOST` | `127.0.0.1` | HTTP server host |
| `MCP_PORT` | `8000` | HTTP server port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Limitations

| Feature | Status | Notes |
|---------|--------|-------|
| Text/Image/Poll Posts | Supported | Via Official LinkedIn API |
| Article Link Shares | Supported | External URLs with metadata |
| Comments | Supported | Requires Community Management API approval |
| Native LinkedIn Articles | Not Available | LinkedIn API limitation |
| Newsletters | Not Available | No API access |
| Direct Messages | Not Available | LinkedIn restricts access |
| Connection Requests | Not Available | LinkedIn restricts access |

---

## Troubleshooting

**"Profile lookup returns error"**

Ensure `THIRDPARTY_RAPIDAPI_KEY` is set in your Claude Desktop config:
```json
"env": {
  "THIRDPARTY_RAPIDAPI_KEY": "your_api_key",
  ...
}
```

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

**Posts not appearing**
- Verify OAuth: `linkedin-mcp-auth status`
- Ensure "Share on LinkedIn" product is enabled in Developer Portal

**Comments failing with permission error**
- Comments require the "Community Management API" product
- Apply for access in your LinkedIn Developer Portal

**Search returns empty results**
- Search relies on session cookies which expire after ~24 hours
- Refresh cookies: `linkedin-mcp-auth extract-cookies --browser chrome`
- Note: Profile and company lookups use the RapidAPI fallback and are unaffected

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
- [Playwright](https://playwright.dev/) - Browser automation

---

**Built for AI-powered professionals**
