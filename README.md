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

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/linkedin-mcp.git
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

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your LinkedIn credentials
```

4. Install Playwright browsers (for automation fallback):
```bash
playwright install chromium
```

## Configuration

Create a `.env` file with your settings:

```bash
# Required: LinkedIn Credentials
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-secure-password

# Optional: Database (defaults to SQLite)
DATABASE_URL=sqlite+aiosqlite:///./data/linkedin_mcp.db

# Optional: Server settings
MCP_TRANSPORT=stdio  # or streamable-http, sse

# Optional: Features
FEATURE_BROWSER_FALLBACK=true
FEATURE_ANALYTICS_TRACKING=true
FEATURE_POST_SCHEDULING=true
```

## Usage

### With Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["run", "linkedin-mcp"],
      "cwd": "/path/to/linkedin-mcp"
    }
  }
}
```

### Standalone

```bash
# Run the server
linkedin-mcp

# Or with Python
python -m linkedin_mcp.main
```

## Available Tools

### Profile Tools
- `get_my_profile()` - Get your LinkedIn profile
- `get_profile(profile_id)` - Get any profile by ID

### Feed & Posts
- `get_feed(limit)` - Get your feed posts
- `get_profile_posts(profile_id, limit)` - Get posts from a profile
- `create_post(text, visibility)` - Create a new post

### Engagement
- `get_post_reactions(post_urn)` - Get reactions on a post
- `like_post(post_urn)` - Like a post
- `comment_on_post(post_urn, text)` - Comment on a post

### Messaging
- `get_conversations(limit)` - Get your conversations
- `send_message(profile_id, text)` - Send a message

### Search
- `search_people(keywords, limit)` - Search for people
- `get_connections(limit)` - Get your connections

### Analytics
- `get_post_analytics(post_urn)` - Get engagement metrics

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
├── tests/               # Test suite
├── docs/                # Documentation
└── data/                # SQLite database and browser state
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

## Security Notice

⚠️ **Important**: This server uses the unofficial LinkedIn API which accesses LinkedIn's internal Voyager API. Use responsibly:

- Use a secondary LinkedIn account for testing
- Respect rate limits (~900 requests/hour)
- Don't spam or automate engagement excessively
- Your account may be restricted if LinkedIn detects automation

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [tomquirk/linkedin-api](https://github.com/tomquirk/linkedin-api) - Unofficial LinkedIn API
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP SDK for Python
- [Model Context Protocol](https://modelcontextprotocol.io/) - AI tool protocol
