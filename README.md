# LinkedIn MCP Server

> **Talk to LinkedIn like you talk to a colleague.** Create posts, analyze engagement, research companies, manage connections, and grow your professional network—all through natural conversation with Claude.

A powerful MCP (Model Context Protocol) server that connects Claude to LinkedIn, enabling AI-powered professional networking, content creation, and lead generation.

---

## What Can You Do?

### Content Creators & Influencers
Create engaging content, analyze what resonates with your audience, and optimize your posting strategy.

| Capability | Example Prompt |
|-----------|----------------|
| **Create Posts** | *"Create a LinkedIn post about the future of AI in healthcare"* |
| **Image Posts** | *"Post this image with a caption about our team's achievement"* |
| **Polls** | *"Create a poll asking my network what programming language they want to learn"* |
| **Schedule Content** | *"Schedule a post for Tuesday at 9am about leadership lessons"* |
| **Analyze Performance** | *"How are my posts performing? What content gets the most engagement?"* |
| **Hashtag Strategy** | *"Which hashtags are driving engagement for my posts?"* |
| **Best Times** | *"When should I post to maximize engagement?"* |

### Sales & Business Development
Identify prospects, research companies, and nurture relationships at scale.

| Capability | Example Prompt |
|-----------|----------------|
| **Find Prospects** | *"Search for VP of Engineering at fintech companies"* |
| **Company Research** | *"Tell me about Microsoft—their size, industry, recent updates"* |
| **Lead Enrichment** | *"Get contact info and skills for this profile"* |
| **Connection Outreach** | *"Send a connection request to johndoe with a personalized message"* |
| **Batch Prospecting** | *"Get profiles for these 10 leads: [list]"* |
| **Track Updates** | *"What has Google been posting recently?"* |

### Recruiters & Talent Acquisition
Streamline candidate sourcing and relationship management.

| Capability | Example Prompt |
|-----------|----------------|
| **Candidate Search** | *"Find senior React developers at startups"* |
| **Skills Analysis** | *"What skills does this candidate have? How many endorsements?"* |
| **Education Check** | *"Get information about Stanford University"* |
| **Outreach** | *"Send a message to this candidate about the role"* |
| **Network Mapping** | *"Show me my connections by industry and location"* |
| **Manage Invitations** | *"Show my pending connection requests"* |

### Marketers & Brand Managers
Build brand presence, track competitors, and engage your audience.

| Capability | Example Prompt |
|-----------|----------------|
| **Brand Monitoring** | *"Show me posts from our company page"* |
| **Competitor Analysis** | *"Analyze the LinkedIn activity of these competitor profiles"* |
| **Engagement** | *"React to and comment on posts in my feed"* |
| **Audience Insights** | *"Who is engaging with my posts? What's their demographic?"* |
| **Content Calendar** | *"List my scheduled posts and their status"* |
| **Performance Reports** | *"Generate an engagement report for my profile"* |

### Executives & Thought Leaders
Establish authority, grow your network strategically, and stay informed.

| Capability | Example Prompt |
|-----------|----------------|
| **Feed Browse** | *"Show me what's trending in my network"* |
| **Profile Optimization** | *"Check my profile completeness—what should I improve?"* |
| **Strategic Networking** | *"Show my network distribution by company and industry"* |
| **Direct Messages** | *"Show my recent conversations and unread messages"* |
| **Engagement Strategy** | *"Help me develop a LinkedIn content strategy"* |

---

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- LinkedIn account
- LinkedIn Developer App (free, takes 5 minutes to set up)

### Step 1: Clone and Install

```bash
git clone https://github.com/southleft/linkedin-mcp.git
cd linkedin-mcp

# Install with uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e .
```

### Step 2: Create LinkedIn Developer App

This gives you official API access for posting and profile features.

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps)
2. Click **"Create app"**
3. Fill in the details:
   - **App name**: Your app name (e.g., "My LinkedIn MCP")
   - **LinkedIn Page**: Select or create a company page
   - **Privacy policy URL**: Can be your website or LinkedIn profile
   - **App logo**: Upload any 100x100 image
4. After creation, go to **"Products"** tab
5. Click **"Request access"** for **"Share on LinkedIn"** (approved instantly)
6. Go to **"Auth"** tab and copy your:
   - **Client ID**
   - **Client Secret** (click to reveal)
7. Under **"OAuth 2.0 settings"**, add redirect URL: `http://localhost:8765/callback`

### Step 3: Configure Environment

Create a `.env` file:

```bash
# LinkedIn OAuth Credentials
LINKEDIN_CLIENT_ID=your_client_id_here
LINKEDIN_CLIENT_SECRET=your_client_secret_here

# Enable full API features
LINKEDIN_API_ENABLED=true
```

### Step 4: Authenticate

```bash
# OAuth authentication (opens browser)
linkedin-mcp-auth oauth

# Extract browser cookies for additional features
linkedin-mcp-auth extract-cookies --browser chrome

# Check status
linkedin-mcp-auth status
```

### Step 5: Connect to Claude

See configuration below for Claude Desktop, Claude Code, or remote access.

---

## Configuration

### Claude Desktop

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
      "args": ["-m", "linkedin_mcp.main"],
      "cwd": "/path/to/linkedin-mcp",
      "env": {
        "LINKEDIN_CLIENT_ID": "your_client_id",
        "LINKEDIN_CLIENT_SECRET": "your_client_secret",
        "LINKEDIN_API_ENABLED": "true",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Restart Claude Desktop** after updating.

### Claude Code

#### Option 1: Add via CLI
```bash
claude mcp add linkedin -- /path/to/linkedin-mcp/.venv/bin/python -m linkedin_mcp.main
```

#### Option 2: Project Configuration
Create `.claude/settings.json` in your project:

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
        "LINKEDIN_API_ENABLED": "true"
      }
    }
  }
}
```

### Remote Access (Claude.ai, Cursor, Mobile)

Run the server in HTTP mode for remote connections:

```bash
# Set transport mode
export MCP_TRANSPORT=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000

# Start server
linkedin-mcp
```

Connect via: `http://your-server:8000/mcp`

For production, use a reverse proxy (nginx/Caddy) with HTTPS.

---

## All Available Tools (60+)

### Profile Tools
| Tool | Description |
|------|-------------|
| `get_my_profile()` | Get your LinkedIn profile |
| `get_profile(id)` | Get any profile by public ID |
| `get_profile_contact_info(id)` | Get contact details (email, phone, websites) |
| `get_profile_skills(id)` | Get skills with endorsement counts |
| `get_network_stats()` | Network distribution by industry/location/company |
| `batch_get_profiles(ids)` | Fetch up to 10 profiles efficiently |

### Content Creation
| Tool | Description |
|------|-------------|
| `create_post(text, visibility)` | Create a text post |
| `create_image_post(text, image_path)` | Create a post with image |
| `create_poll(question, options)` | Create a poll |
| `delete_post(post_urn)` | Delete a post |
| `schedule_post(content, time)` | Schedule for future publishing |

### Drafts & Scheduling
| Tool | Description |
|------|-------------|
| `create_draft(content)` | Save content for later |
| `list_drafts()` | List all drafts |
| `publish_draft(id)` | Publish a draft |
| `list_scheduled_posts()` | View scheduled posts |
| `cancel_scheduled_post(id)` | Cancel a scheduled post |

### Engagement
| Tool | Description |
|------|-------------|
| `react_to_post(urn, type)` | React (LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, FUNNY) |
| `comment_on_post(urn, text)` | Add a comment |
| `reply_to_comment(urn, text)` | Reply to a comment |
| `get_post_reactions(urn)` | See who reacted |
| `get_post_comments(urn)` | Get all comments |

### Search & Discovery
| Tool | Description |
|------|-------------|
| `search_people(keywords)` | Search for people |
| `search_companies(keywords)` | Search for companies |
| `get_connections(limit)` | List your connections |
| `get_feed(limit)` | Browse your feed |

### Company Research
| Tool | Description |
|------|-------------|
| `get_company(id)` | Get company details |
| `get_company_updates(id)` | Get company posts |
| `get_school(id)` | Get school/university info |

### Messaging
| Tool | Description |
|------|-------------|
| `get_conversations(limit)` | List message threads |
| `get_conversation(id)` | Get full conversation |
| `send_message(profile_id, text)` | Send a direct message |
| `send_bulk_messages(ids, text)` | Message multiple connections |

### Connection Management
| Tool | Description |
|------|-------------|
| `send_connection_invitation(id, message)` | Send connection request |
| `withdraw_connection_invitation(id)` | Withdraw pending request |
| `get_invitations()` | View pending requests |
| `accept_invitation(id)` | Accept a request |
| `reject_invitation(id)` | Decline a request |

### Analytics
| Tool | Description |
|------|-------------|
| `get_post_analytics(urn)` | Engagement metrics for a post |
| `analyze_engagement(urn)` | Deep engagement analysis |
| `analyze_content_performance(id)` | Content type performance |
| `analyze_optimal_posting_times(id)` | Best times to post |
| `analyze_hashtag_performance(id)` | Hashtag ROI analysis |
| `generate_engagement_report(id)` | Comprehensive report |

### Profile Management
| Tool | Description |
|------|-------------|
| `get_profile_completeness()` | Completeness score + suggestions |
| `update_profile_headline(text)` | Update headline |
| `update_profile_summary(text)` | Update about section |
| `add_profile_skill(name)` | Add a skill |
| `upload_profile_photo(path)` | Update profile photo |

---

## Example Conversations

### For Content Creators
```
You: "I want to post about the importance of continuous learning in tech"

Claude: I'll create that post for you. Here's a draft:

"🚀 In tech, the day you stop learning is the day you start falling behind.

Whether it's a new framework, a different approach, or a completely new domain—
curiosity is our greatest competitive advantage.

What are you learning this week? Drop it in the comments 👇

#ContinuousLearning #TechCareers #GrowthMindset"

Should I post this publicly or just to your connections?
```

### For Sales Teams
```
You: "Find me VPs of Engineering at AI startups"

Claude: I searched LinkedIn and found 10 matching profiles:

1. **Jane Smith** - VP Engineering @ AIStartup Inc
   Location: San Francisco, CA

2. **John Doe** - VP of Engineering @ ML Solutions
   Location: New York, NY

[...]

Would you like me to:
- Get more details on any of these profiles?
- Show their recent activity?
- Send connection requests?
```

### For Recruiters
```
You: "Get the skills for this candidate: johndoe-developer"

Claude: Here are John Doe's skills with endorsements:

**Top Skills:**
- Python (47 endorsements)
- Machine Learning (38 endorsements)
- React (35 endorsements)
- AWS (28 endorsements)
- Docker (22 endorsements)

**Other Skills:**
- TypeScript, Node.js, PostgreSQL...

Would you like me to get their contact information?
```

---

## CLI Commands

```bash
# Authentication
linkedin-mcp-auth status          # Check auth status
linkedin-mcp-auth oauth           # OAuth flow (opens browser)
linkedin-mcp-auth oauth --force   # Force re-authentication
linkedin-mcp-auth extract-cookies --browser chrome  # Extract session cookies
linkedin-mcp-auth logout --all    # Clear all credentials

# Run Server
linkedin-mcp                      # Start MCP server (stdio mode)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_CLIENT_ID` | - | OAuth Client ID |
| `LINKEDIN_CLIENT_SECRET` | - | OAuth Client Secret |
| `LINKEDIN_API_ENABLED` | `false` | Enable full API features |
| `MCP_TRANSPORT` | `stdio` | Transport: stdio, streamable-http, sse |
| `MCP_HOST` | `127.0.0.1` | HTTP server host |
| `MCP_PORT` | `8000` | HTTP server port |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Authentication Methods

### OAuth 2.0 (Recommended)
- Official LinkedIn API
- Required for posting, polls, image uploads
- Token lasts 60 days, auto-refreshes
- TOS-compliant

### Cookie Extraction (Additional Features)
- Enables search, messaging, company research
- Extracted from your logged-in browser session
- Refresh periodically for best results

Use both for maximum functionality:
```bash
linkedin-mcp-auth oauth
linkedin-mcp-auth extract-cookies --browser chrome
```

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

## Security

- **OAuth tokens** stored securely with encryption
- **Session cookies** stored locally (never transmitted)
- **Credentials** loaded from environment variables
- **No data collection** - everything runs locally
- Never commit `.env` or credential files

---

## Troubleshooting

### "LinkedIn client not initialized"
Run `linkedin-mcp-auth status` to check authentication. Then run either:
- `linkedin-mcp-auth oauth` for OAuth
- `linkedin-mcp-auth extract-cookies` for cookie auth

### "Challenge URL" errors
LinkedIn may require verification. Log into LinkedIn in your browser, then re-extract cookies.

### Rate limiting
The server includes built-in rate limiting. If you hit limits, wait a few minutes before retrying.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Acknowledgments

- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - LinkedIn API library
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol

---

**Built with ❤️ for the AI-powered professional**
