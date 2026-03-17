# LinkedIn MCP - Development Guide

## Messaging / DM System

LinkedIn messaging uses a **headless Playwright browser** as the HTTP transport layer. This is required because LinkedIn's bot detection blocks all Python HTTP clients from accessing the Voyager API.

### How it works
- `HeadlessLinkedInScraper.api_fetch()` makes `fetch()` calls from within a real headless Chromium
- Persistent session stored at `~/.linkedin-mcp/browser-session/`
- First use opens a visible browser for LinkedIn login (~30 seconds). After that, fully headless and automatic
- Session lasts months. If expired, `ensure_authenticated()` auto-opens browser for re-login

### Key files
- `src/linkedin_mcp/services/linkedin/headless_scraper.py` — Browser transport with `api_fetch()` and `ensure_authenticated()`
- `src/linkedin_mcp/services/linkedin/client.py` — `LinkedInClient` with GraphQL messaging methods
- `src/linkedin_mcp/server.py` — MCP tool definitions

### DO NOT
- Use `requests`, `httpx`, or `curl_cffi` for Voyager API calls — LinkedIn blocks them all
- Use the `linkedin-api` library's messaging methods — they use deprecated endpoints
- Try to extract `li_at` cookies from Chrome — unreliable, not needed
- Ask the user to manually manage cookies or tokens

### LinkedIn GraphQL Messaging Endpoints
- Conversations: `voyagerMessagingGraphQL/graphql?queryId=messengerConversations.0d5e6781bbee71c3e51c8843c6519f48`
- Messages: `voyagerMessagingGraphQL/graphql?queryId=messengerMessages.5846eeb71c981f11e0134cb6626cc314`
- Paginated messages: `queryId=messengerMessages.d8ea76885a52fd5dc5c317078ab7c977` (with `deliveredAt` cursor)
- Variable format: `(key:url_encoded_value)` — NOT JSON

### Prerequisites
```bash
pip install playwright && playwright install chromium
```

## Official API (OAuth)
- Used for: posting, profile reading, analytics
- Scopes: openid, profile, email, w_member_social
- Does NOT support reading DMs — that's why the headless browser is needed

## Unofficial API (linkedin-api library)
- Used for: profiles, companies, connections, job search
- Cookie-based auth via `linkedin-mcp-auth extract-cookies`
- NOT used for messaging (broken endpoints)
