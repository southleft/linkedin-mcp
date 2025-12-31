# LinkedIn Intelligence MCP Server

> **Transform LinkedIn from a social network into your AI-powered business intelligence platform.**

The LinkedIn MCP Server connects Claude Desktop directly to LinkedIn's data layer, enabling natural language conversations that extract insights, automate engagement, and supercharge your professional networking—all without leaving your AI assistant.

---

## Why LinkedIn MCP?

| Traditional LinkedIn | With LinkedIn MCP |
|---------------------|-------------------|
| Manually scroll through feeds | Ask Claude: *"Show me posts from my network about AI this week"* |
| Export connections to spreadsheets | Ask Claude: *"Analyze my network by industry and seniority"* |
| Guess at optimal posting times | Ask Claude: *"When do my posts get the most engagement?"* |
| Research prospects one-by-one | Ask Claude: *"Get profiles for these 10 decision-makers"* |
| Copy-paste between tools | Seamless integration with Gmail, Calendar, and other MCPs |

### The MCP Ecosystem Advantage

LinkedIn MCP becomes exponentially more powerful when combined with other Claude Desktop integrations:

- **Gmail MCP** → *"Find LinkedIn profiles for everyone who emailed me this week about partnerships"*
- **Google Calendar MCP** → *"Who am I meeting tomorrow? Pull their LinkedIn profiles and recent posts"*
- **Notion/Obsidian MCP** → *"Add this prospect's LinkedIn summary to my CRM notes"*
- **File System MCP** → *"Export my network analytics to a CSV for my quarterly report"*

This isn't just another LinkedIn tool—it's the bridge that connects your professional network to your entire AI-powered workflow.

---

## Use Cases by Role

<details>
<summary><h3>🎯 Sales Development Representatives (SDRs)</h3></summary>

**Turn LinkedIn into your AI-powered prospecting engine.**

#### Your Daily Workflow, Supercharged

| Before | After (with LinkedIn MCP) |
|--------|---------------------------|
| 2 hours researching prospects | *"Get me profiles and recent activity for these 20 leads"* |
| Generic outreach messages | *"What topics does [prospect] post about? Draft a personalized message"* |
| Missing engagement signals | *"Alert me when target accounts post about [pain point]"* |

#### Key Tools for SDRs

```
🔍 Research & Intelligence
├── search_people() - Find prospects by company, title, keywords
├── get_profile() - Deep-dive into prospect backgrounds
├── get_profile_posts() - See what they care about
└── batch_get_profiles() - Research entire account lists at once

📬 Outreach & Engagement
├── send_connection_request() - Personalized invites at scale
├── send_message() - Direct outreach to connections
├── like_post() / comment_on_post() - Warm up cold prospects
└── react_to_post() - Show genuine engagement

📊 Pipeline Intelligence
├── get_conversations() - Track outreach threads
├── analyze_engagement() - See what messaging resonates
└── get_pending_invitations() - Manage your connection pipeline
```

#### Example Prompts for SDRs

- *"Search for VPs of Engineering at Series B fintech companies in NYC"*
- *"What has [prospect name] posted about in the last month? Summarize the themes"*
- *"Send connection requests to these 10 people with a message about [topic]"*
- *"Show me which of my connection requests from last week were accepted"*
- *"Cross-reference my Gmail contacts with LinkedIn—who should I connect with?"*

</details>

<details>
<summary><h3>🤝 Business Development & Partnerships</h3></summary>

**Map relationships and identify partnership opportunities at scale.**

#### Strategic Intelligence Gathering

| Challenge | LinkedIn MCP Solution |
|-----------|----------------------|
| Finding decision-makers | *"Who are the BD leads at [company]? Get their profiles"* |
| Understanding company priorities | *"What is [company] posting about? Any partnership announcements?"* |
| Tracking competitor partnerships | *"Show me [competitor]'s recent posts mentioning partnerships or integrations"* |
| Warm introductions | *"Which of my connections work at or are connected to [target company]?"* |

#### Key Tools for BD Professionals

```
🏢 Company Intelligence
├── search_companies() - Find potential partners by criteria
├── get_profile_posts() - Track company announcements
└── search_people() - Identify key stakeholders

🔗 Relationship Mapping
├── get_connections() - Your network inventory
├── get_network_stats() - Network composition analysis
└── get_profile_contact_info() - Direct contact details

📈 Opportunity Tracking
├── get_feed() - Monitor partnership signals
├── analyze_content_performance() - Understand what resonates
└── generate_engagement_report() - Track relationship building
```

#### Example Prompts for BD

- *"Find AI/ML companies that have posted about seeking partnerships in the last 30 days"*
- *"Map my path to the CEO of [target company]—who do I know there?"*
- *"What integrations or partnerships has [company] announced this quarter?"*
- *"Get me the profiles of everyone with 'Partnerships' in their title at these 5 companies"*
- *"Summarize the recent posts from decision-makers at my target accounts"*

</details>

<details>
<summary><h3>📈 Personal Brand Builders</h3></summary>

**Data-driven content strategy for thought leadership.**

#### Build Your Presence Strategically

| Guesswork | Data-Driven (with LinkedIn MCP) |
|-----------|--------------------------------|
| Post whenever, hope for engagement | *"When do my posts get the most engagement? Analyze my last 50 posts"* |
| Random hashtags | *"Which hashtags drive the most reach for my content?"* |
| Wonder what resonates | *"What topics get the most comments from my audience?"* |
| Inconsistent posting | Schedule content for optimal times automatically |

#### Key Tools for Brand Builders

```
📝 Content Creation
├── create_post() - Publish directly from Claude
├── create_draft() - Save ideas for later
├── analyze_draft_content() - Get AI feedback before posting
└── schedule_post() - Queue content for peak times

📊 Performance Analytics
├── analyze_optimal_posting_times() - Find your best windows
├── analyze_hashtag_performance() - Optimize discoverability
├── analyze_content_performance() - Track what works
└── generate_engagement_report() - Full performance review

🎯 Audience Intelligence
├── get_post_comments() - Understand audience reactions
├── get_post_reactions() - See who engages
├── analyze_post_audience() - Demographics of engagers
└── analyze_engagement() - Deep engagement metrics
```

#### Example Prompts for Brand Builders

- *"Analyze my last 30 posts—which topics drove the most engagement?"*
- *"What time of day should I post to maximize reach with my audience?"*
- *"Draft a post about [topic] optimized for engagement based on what works for me"*
- *"Schedule this post for my optimal posting time tomorrow"*
- *"Which of my posts this month could be repurposed into a series?"*

</details>

<details>
<summary><h3>🏢 Agency & Competitive Intelligence</h3></summary>

**Multi-account insights and competitor analysis for agency professionals.**

#### Agency-Grade Intelligence

| Manual Process | Automated with LinkedIn MCP |
|----------------|----------------------------|
| Weekly competitor audits | *"Compare posting frequency and engagement across these 5 competitors"* |
| Client reporting | *"Generate an engagement report for [client profile]"* |
| Trend spotting | *"What topics are trending in [industry] this week?"* |
| Benchmarking | *"How does my client's engagement rate compare to competitors?"* |

#### Key Tools for Agencies

```
🔍 Competitive Analysis
├── get_profile_posts() - Track competitor content
├── analyze_content_performance() - Benchmark strategies
├── analyze_engagement() - Compare engagement metrics
└── search_people() - Monitor competitor teams

📋 Client Management
├── generate_engagement_report() - Automated reporting
├── analyze_optimal_posting_times() - Client-specific insights
├── analyze_hashtag_performance() - Strategy optimization
└── get_post_analytics() - Detailed post breakdowns

📈 Market Intelligence
├── get_feed() - Industry trend monitoring
├── search_companies() - Market landscape mapping
└── batch_get_profiles() - Bulk research capabilities
```

#### Example Prompts for Agencies

- *"Compare the posting strategy of [client] vs their top 3 competitors"*
- *"Generate a monthly engagement report for [client profile]"*
- *"What content themes are driving the most engagement in the [industry] space?"*
- *"Track what [competitor] has posted about our client's product category"*
- *"Create a benchmark report: my client vs industry average engagement"*

</details>

<details>
<summary><h3>👥 Recruiters & Talent Acquisition</h3></summary>

**Build talent pipelines with AI-powered sourcing.**

#### Recruiting, Reimagined

| Traditional Sourcing | AI-Powered Sourcing |
|---------------------|---------------------|
| Boolean searches, one at a time | *"Find senior engineers at FAANG who've posted about leaving big tech"* |
| Manual candidate research | *"Summarize this candidate's career trajectory and recent interests"* |
| Cold outreach fatigue | *"What does this candidate care about? Draft a personalized InMail"* |
| Lost in spreadsheets | Integrated pipeline tracking with other MCPs |

#### Key Tools for Recruiters

```
🎯 Candidate Sourcing
├── search_people() - Advanced candidate search
├── get_profile() - Comprehensive candidate profiles
├── get_profile_skills() - Skills and endorsements
├── batch_get_profiles() - Research candidate lists

💬 Candidate Engagement
├── get_profile_posts() - Understand candidate interests
├── send_connection_request() - Personalized outreach
├── send_message() - Direct candidate communication
└── get_conversations() - Track outreach threads

📊 Pipeline Analytics
├── get_pending_invitations() - Monitor connection pipeline
├── get_connections() - Your talent network
└── get_network_stats() - Network composition
```

#### Example Prompts for Recruiters

- *"Find product managers at [company] who've been in role 2+ years"*
- *"What has this candidate posted about? What motivates them?"*
- *"Get profiles for all engineers at [company] with ML in their title"*
- *"Draft a personalized connection message for [candidate] based on their interests"*
- *"Who in my network is connected to this candidate for a warm intro?"*

</details>

<details>
<summary><h3>✍️ Content Creators & Thought Leaders</h3></summary>

**Maximize reach and engagement with data-driven content strategies.**

#### Content Strategy on Autopilot

| Content Struggle | LinkedIn MCP Solution |
|-----------------|----------------------|
| What should I post about? | *"What topics are getting engagement in my niche this week?"* |
| Writer's block | *"Based on my top posts, generate 5 content ideas"* |
| Engagement drops | *"Why did my engagement drop last week? Analyze the data"* |
| Audience mystery | *"Who's engaging with my content? Profile my active followers"* |

#### Key Tools for Creators

```
📝 Content Workflow
├── create_draft() - Save ideas and drafts
├── analyze_draft_content() - AI-powered content review
├── schedule_post() - Automated publishing
└── list_scheduled_posts() - Manage content calendar

📊 Deep Analytics
├── analyze_content_performance() - Content type analysis
├── analyze_hashtag_performance() - Hashtag ROI
├── analyze_optimal_posting_times() - Peak engagement windows
└── generate_engagement_report() - Comprehensive analytics

🎯 Engagement Optimization
├── get_post_comments() - Comment analysis
├── reply_to_comment() - Community management
├── analyze_post_audience() - Audience demographics
└── get_post_reactions() - Reaction breakdown
```

#### Example Prompts for Creators

- *"Analyze my content performance over the last 90 days—what's working?"*
- *"Which of my posts should I turn into a content series?"*
- *"What are the top creators in [niche] posting about this month?"*
- *"Review this draft and suggest improvements for engagement"*
- *"Build me a content calendar for next week based on my best-performing topics"*

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

## Complete Tool Reference

<details>
<summary><h3>View All 60+ Available Tools</h3></summary>

#### Diagnostic
- `debug_context()` - Server initialization status and configuration

#### Profile Tools
- `get_my_profile()` - Your LinkedIn profile
- `get_profile(profile_id)` - Any profile by public ID
- `get_profile_contact_info(profile_id)` - Contact information
- `get_profile_skills(profile_id)` - Skills and endorsements
- `get_profile_sections()` - Editable profile sections
- `get_profile_completeness()` - Profile completeness score
- `get_network_stats()` - Network size and demographics
- `batch_get_profiles(profile_ids)` - Multiple profiles efficiently

#### Profile Management (browser automation)
- `update_profile_headline(headline)` - Update headline
- `update_profile_summary(summary)` - Update about section
- `upload_profile_photo(photo_path)` - Upload profile photo
- `upload_background_photo(photo_path)` - Upload banner photo
- `add_profile_skill(skill_name)` - Add a skill
- `check_browser_automation_status()` - Browser availability

#### Feed & Posts
- `get_feed(limit)` - Your feed posts
- `get_profile_posts(profile_id, limit)` - Posts from a profile
- `create_post(text, visibility)` - Create a new post
- `get_post_reactions(post_urn)` - Reactions on a post
- `get_post_comments(post_urn)` - Comments on a post

#### Content Creation & Scheduling
- `analyze_draft_content(content, industry)` - Content analysis with suggestions
- `create_draft(content, title, tags)` - Save a content draft
- `list_drafts(tag)` - List content drafts
- `get_draft(draft_id)` - Get a specific draft
- `update_draft(draft_id, content, title, tags)` - Update a draft
- `delete_draft(draft_id)` - Delete a draft
- `publish_draft(draft_id, visibility)` - Publish a draft as a post
- `schedule_post(content, scheduled_time, visibility, timezone)` - Schedule a post
- `list_scheduled_posts(status)` - View scheduled posts
- `get_scheduled_post(job_id)` - Scheduled post details
- `update_scheduled_post(job_id, ...)` - Update scheduled post
- `cancel_scheduled_post(job_id)` - Cancel scheduled post

#### Engagement
- `like_post(post_urn)` - Like a post
- `react_to_post(post_urn, reaction)` - React (LIKE, CELEBRATE, SUPPORT, LOVE, INSIGHTFUL, FUNNY)
- `unreact_to_post(post_urn)` - Remove reaction
- `comment_on_post(post_urn, text)` - Comment on a post
- `reply_to_comment(comment_urn, text)` - Reply to a comment

#### Messaging
- `get_conversations(limit)` - Messaging conversations
- `get_conversation(conversation_id)` - Full conversation history
- `send_message(profile_id, text)` - Send a direct message
- `send_bulk_messages(profile_ids, text)` - Send to multiple recipients (max 25)

#### Connections
- `get_connections(limit)` - Your connections
- `send_connection_request(profile_id, message)` - Send connection invite
- `remove_connection(profile_id)` - Remove a connection
- `get_pending_invitations(sent)` - View pending invites
- `accept_invitation(invitation_id, shared_secret)` - Accept connection request
- `reject_invitation(invitation_id, shared_secret)` - Reject connection request

#### Search
- `search_people(keywords, limit, connection_of, current_company)` - Search for people
- `search_companies(keywords, limit)` - Search for companies

#### Analytics
- `get_post_analytics(post_urn)` - Engagement metrics for a post
- `analyze_engagement(post_urn, follower_count)` - Deep engagement analysis
- `analyze_content_performance(profile_id, post_limit)` - Content type analysis
- `analyze_optimal_posting_times(profile_id, post_limit)` - Best times to post
- `analyze_post_audience(post_urn)` - Audience demographics from commenters
- `analyze_hashtag_performance(profile_id, post_limit)` - Hashtag effectiveness
- `generate_engagement_report(profile_id, post_limit)` - Comprehensive engagement report
- `get_rate_limit_status()` - API rate limit status
- `get_cache_stats()` - Cache performance statistics

</details>

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LINKEDIN_API_ENABLED` | `false` | Enable the LinkedIn API client |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/linkedin_mcp.db` | Database connection URL |
| `FEATURE_BROWSER_FALLBACK` | `true` | Enable Playwright browser automation |
| `FEATURE_ANALYTICS_TRACKING` | `true` | Enable analytics features |
| `FEATURE_POST_SCHEDULING` | `true` | Enable post scheduling |

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

---

<p align="center">
  <strong>Built for professionals who move fast.</strong><br>
  <a href="https://github.com/southleft/linkedin-mcp/issues">Report Issues</a> ·
  <a href="https://github.com/southleft/linkedin-mcp/pulls">Contribute</a>
</p>
