"""
Application constants for LinkedIn MCP Server.
"""

# LinkedIn API Constants
LINKEDIN_BASE_URL = "https://www.linkedin.com"
LINKEDIN_API_BASE = "https://api.linkedin.com"

# Rate Limiting Defaults
DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_RATE_LIMIT_BURST = 10
MAX_REQUESTS_PER_HOUR = 900  # linkedin-api warning threshold

# Cache TTL (in seconds)
PROFILE_CACHE_TTL = 86400  # 24 hours
POST_CACHE_TTL = 3600  # 1 hour
FEED_CACHE_TTL = 300  # 5 minutes

# Retry Configuration
MAX_RETRIES = 3
RETRY_BACKOFF_MULTIPLIER = 1
RETRY_MIN_WAIT = 4
RETRY_MAX_WAIT = 60

# Post Limits
MAX_POST_LENGTH = 3000
MAX_HASHTAGS_PER_POST = 30

# Analytics Constants
ANALYTICS_EVENT_TYPES = [
    "profile_viewed",
    "post_created",
    "post_liked",
    "post_commented",
    "message_sent",
    "connection_sent",
    "connection_accepted",
    "search_performed",
]

# Scheduler Constants
DEFAULT_SCHEDULER_TIMEZONE = "UTC"
MAX_SCHEDULED_POSTS = 100

# Browser Automation
BROWSER_SELECTORS = {
    "login_email": 'input[name="session_key"]',
    "login_password": 'input[name="session_password"]',
    "login_submit": 'button[type="submit"]',
    "start_post_button": 'button[class*="share-box"]',
    "post_editor": 'div[role="textbox"]',
    "post_submit": 'button[class*="share-actions__primary-action"]',
}
