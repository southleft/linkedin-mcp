# LinkedIn Intelligence MCP Server

AI-powered LinkedIn analytics, content creation, and engagement automation through the Model Context Protocol (MCP).

## Features

### Data Collection
- **Profile Management**: Fetch your profile and any public profile
- **Feed Access**: Read your LinkedIn feed and individual posts
- **Post Analytics**: Track engagement metrics (likes, comments, shares)
- **Connection Insights**: Analyze your network and connections

### Content Creation
- **Post Creation**: Create text posts with proper visibility settings
- **Scheduled Posting**: Queue posts for optimal timing
- **Hashtag Optimization**: Analyze and suggest effective hashtags

### Engagement Tools
- **Like & React**: Engage with posts programmatically
- **Comment**: Add comments to posts
- **Messaging**: Send messages to connections
- **Search**: Find people, companies, and content

### Analytics Engine
- **Engagement Tracking**: Monitor post performance over time
- **Competitor Analysis**: Analyze what's working for others
- **Trend Detection**: Identify trending topics and hashtags
- **Optimal Timing**: Discover best times to post

## Installation

### Prerequisites
- Python 3.11 or higher
- uv (recommended) or pip
- A LinkedIn account with active session cookies

### Setup

1. Clone the repository:
```bash
git clone https://github.com/southleft/linkedin-mcp.git
cd linkedin-mcp
```

2. Create virtual environment and install dependencies:
```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# Or using pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

3. Create the data directory:
```bash
mkdir -p data
```

4. Export your LinkedIn cookies (see Authentication section below)

5. (Optional) Install Playwright browsers for automation fallback:
```bash
playwright install chromium
```

## Authentication

This MCP server uses **cookie-based authentication** with LinkedIn's internal Voyager API. You'll need to export cookies from an active LinkedIn session in your browser.

### Exporting Cookies

1. Log into LinkedIn in your browser (Chrome/Firefox)
2. Open Developer Tools (F12 or Cmd+Option+I)
3. Go to the **Application** tab (Chrome) or **Storage** tab (Firefox)
4. Find Cookies > `https://www.linkedin.com`
5. Copy the values for:
   - `li_at` - Your main session token
   - `JSESSIONID` - Your session ID (include the quotes if present)

6. Create `data/session_cookies.json`:
```json
{
  "li_at": "YOUR_LI_AT_COOKIE_VALUE",
  "JSESSIONID": "\"ajax:1234567890123456789\""
}
```

> **Note**: The `JSESSIONID` value typically includes escaped quotes. Copy it exactly as shown in your browser.

### Cookie Helper Script

Alternatively, use the included export script:
```bash
# This script helps format cookies correctly
python scripts/export_cookies.py
```

## Configuration

### Claude Desktop Setup

Add to your Claude Desktop configuration file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

> **Important**: The `cwd` path must be an **absolute path** to the project directory.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_API_ENABLED` | `false` | Enable the LinkedIn API client |
| `LINKEDIN_EMAIL` | - | LinkedIn email (optional, for future use) |
| `LINKEDIN_PASSWORD` | - | LinkedIn password (optional, for future use) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/linkedin_mcp.db` | Database connection URL |
| `FEATURE_BROWSER_FALLBACK` | `true` | Enable Playwright browser automation |
| `FEATURE_ANALYTICS_TRACKING` | `true` | Enable analytics features |
| `FEATURE_POST_SCHEDULING` | `true` | Enable post scheduling |

## Usage

### Verifying Setup

After configuring Claude Desktop, restart the application and try:

1. **Check server status**: Ask Claude to use the `debug_context` tool
2. **Test authentication**: Ask Claude to use `get_my_profile`

If you see "LinkedIn client not initialized", check:
- `LINKEDIN_API_ENABLED` is set to `"true"` (as a string)
- `data/session_cookies.json` exists with valid cookies
- The `cwd` path in Claude Desktop config is absolute

### Available Tools

#### Diagnostic
- `debug_context()` - Check server initialization status and configuration

#### Profile Tools
- `get_my_profile()` - Get your LinkedIn profile
- `get_profile(profile_id)` - Get any profile by public ID
- `get_profile_contact_info(profile_id)` - Get contact information
- `get_profile_skills(profile_id)` - Get skills and endorsements
- `get_profile_sections()` - View editable profile sections
- `get_profile_completeness()` - Calculate profile completeness score
- `get_network_stats()` - Get network size and demographics
- `batch_get_profiles(profile_ids)` - Get multiple profiles efficiently

#### Profile Management (requires browser automation)
- `update_profile_headline(headline)` - Update your headline
- `update_profile_summary(summary)` - Update your about section
- `upload_profile_photo(photo_path)` - Upload profile photo
- `upload_background_photo(photo_path)` - Upload banner photo
- `add_profile_skill(skill_name)` - Add a skill
- `check_browser_automation_status()` - Check browser availability

#### Feed & Posts
- `get_feed(limit)` - Get your feed posts
- `get_profile_posts(profile_id, limit)` - Get posts from a profile
- `create_post(text, visibility)` - Create a new post
- `get_post_reactions(post_urn)` - Get reactions on a post
- `get_post_comments(post_urn)` - Get comments on a post

#### Content Creation & Scheduling
- `analyze_draft_content(content, industry)` - Analyze content with suggestions
- `create_draft(content, title, tags)` - Save a content draft
- `list_drafts(tag)` - List content drafts
- `get_draft(draft_id)` - Get a specific draft
- `update_draft(draft_id, content, title, tags)` - Update a draft
- `delete_draft(draft_id)` - Delete a draft
- `publish_draft(draft_id, visibility)` - Publish a draft as a post
- `schedule_post(content, scheduled_time, visibility, timezone)` - Schedule a post
- `list_scheduled_posts(status)` - View scheduled posts
- `get_scheduled_post(job_id)` - Get scheduled post details
- `update_scheduled_post(job_id, ...)` - Update a scheduled post
- `cancel_scheduled_post(job_id)` - Cancel a scheduled post

#### Engagement
- `like_post(post_urn)` - Like a post
- `react_to_post(post_urn, reaction)` - React with LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, or FUNNY
- `unreact_to_post(post_urn)` - Remove reaction from a post
- `comment_on_post(post_urn, text)` - Comment on a post
- `reply_to_comment(comment_urn, text)` - Reply to a comment

#### Messaging
- `get_conversations(limit)` - Get messaging conversations
- `get_conversation(conversation_id)` - Get full conversation history
- `send_message(profile_id, text)` - Send a direct message
- `send_bulk_messages(profile_ids, text)` - Send to multiple recipients (max 25)

#### Connections
- `get_connections(limit)` - Get your connections
- `send_connection_request(profile_id, message)` - Send connection invite
- `remove_connection(profile_id)` - Remove a connection
- `get_pending_invitations(sent)` - View pending invites
- `accept_invitation(invitation_id, shared_secret)` - Accept connection request
- `reject_invitation(invitation_id, shared_secret)` - Reject connection request

#### Search
- `search_people(keywords, limit, connection_of, current_company)` - Search for people
- `search_companies(keywords, limit)` - Search for companies

#### Analytics
- `get_post_analytics(post_urn)` - Get engagement metrics for a post
- `analyze_engagement(post_urn, follower_count)` - Deep engagement analysis
- `analyze_content_performance(profile_id, post_limit)` - Content type analysis
- `analyze_optimal_posting_times(profile_id, post_limit)` - Best times to post
- `analyze_post_audience(post_urn)` - Audience demographics from commenters
- `analyze_hashtag_performance(profile_id, post_limit)` - Hashtag effectiveness
- `generate_engagement_report(profile_id, post_limit)` - Comprehensive engagement report
- `get_rate_limit_status()` - Check API rate limit status
- `get_cache_stats()` - View cache performance statistics

## Architecture

```
linkedin-mcp/
├── src/linkedin_mcp/
│   ├── config/          # Settings and constants
│   ├── core/            # Context, exceptions, logging, lifespan
│   ├── db/              # SQLAlchemy models and repositories
│   ├── services/
│   │   ├── linkedin/    # LinkedIn API wrapper
│   │   ├── browser/     # Playwright automation
│   │   ├── scheduler/   # APScheduler integration
│   │   └── analytics/   # Analytics processing
│   ├── tools/           # MCP tool definitions
│   ├── resources/       # MCP resource definitions
│   ├── prompts/         # MCP prompt templates
│   ├── server.py        # FastMCP server
│   └── main.py          # Entry point
├── scripts/             # Utility scripts
├── tests/               # Test suite
└── data/                # Runtime data (gitignored)
```

## Development

### Running Tests
```bash
pytest tests/ -v --cov=linkedin_mcp
```

### Linting
```bash
ruff check src/
ruff format src/
```

### Type Checking
```bash
mypy src/linkedin_mcp
```

### Running Locally
```bash
# Start the MCP server directly
uv run linkedin-mcp

# Or with Python
python -m linkedin_mcp.main
```

## Troubleshooting

### "LinkedIn client not initialized"

1. Ensure `LINKEDIN_API_ENABLED=true` in your Claude Desktop config
2. Verify `data/session_cookies.json` exists and contains valid cookies
3. Check that cookies haven't expired (re-export from browser if needed)
4. Verify the `cwd` path is absolute, not relative

### Cookies expire frequently

LinkedIn session cookies typically last 1-2 weeks. If you're getting authentication errors:
1. Log into LinkedIn in your browser
2. Re-export the `li_at` and `JSESSIONID` cookies
3. Update `data/session_cookies.json`
4. Restart Claude Desktop

### MCP server logs

View server logs:

```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp-server-linkedin.log

# Windows (PowerShell)
Get-Content -Path "$env:APPDATA\Claude\logs\mcp-server-linkedin.log" -Wait

# Linux
tail -f ~/.config/Claude/logs/mcp-server-linkedin.log
```

## Security Notice

⚠️ **Important**: This server uses the unofficial LinkedIn API which accesses LinkedIn's internal Voyager API. Use responsibly:

- **Use a secondary LinkedIn account for testing**
- Respect rate limits (~900 requests/hour)
- Don't spam or automate engagement excessively
- Your account may be restricted if LinkedIn detects automation
- **Never commit your `data/` directory or cookie files**

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - Unofficial LinkedIn API
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol
