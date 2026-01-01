"""
Headless LinkedIn scraper using Patchright/Playwright.

Provides background browser automation for LinkedIn data access
when API-based methods are blocked. Works completely in background
without any visible browser window.

Uses Patchright (undetected Playwright fork) when available,
falls back to standard Playwright with stealth configuration.
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Any

from linkedin_mcp.core.exceptions import (
    BrowserAutomationError,
    LinkedInAPIError,
    LinkedInAuthError,
)
from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)

# Try to import Patchright (most undetectable)
try:
    from patchright.async_api import async_playwright
    USING_PATCHRIGHT = True
    logger.info("Patchright available for undetected browser automation")
except ImportError:
    USING_PATCHRIGHT = False
    try:
        from playwright.async_api import async_playwright
        logger.warning(
            "Patchright not available, using Playwright",
            install_cmd="pip install patchright && patchright install chrome",
        )
    except ImportError:
        async_playwright = None
        logger.warning("No browser automation available")

# Stealth JavaScript to inject when using standard Playwright
STEALTH_SCRIPTS = """
// Hide webdriver flag
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
    configurable: true
});

// Mock plugins array
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ];
        plugins.item = (i) => plugins[i];
        plugins.namedItem = (n) => plugins.find(p => p.name === n);
        plugins.refresh = () => {};
        return plugins;
    }
});

// Mock languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Mock permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Chrome runtime mock
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};
"""


class HeadlessLinkedInScraper:
    """
    Headless LinkedIn scraper for background data extraction.

    This scraper works completely in the background without any
    visible browser window. It uses Patchright (if available) or
    Playwright with stealth configuration for anti-detection.

    Features:
    - Completely headless operation (no visible window)
    - Session cookie authentication
    - Human-like interaction patterns
    - Automatic session persistence
    - Profile, feed, and search scraping
    """

    def __init__(
        self,
        session_dir: str | Path = "./data/linkedin_browser_session",
        headless: bool = True,
    ):
        """
        Initialize headless scraper.

        Args:
            session_dir: Directory for browser session data
            headless: Run in headless mode (always True for MCP usage)
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless  # Always headless for background operation

        self._playwright = None
        self._context = None
        self._page = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the browser with stealth configuration."""
        if self._initialized:
            return

        if async_playwright is None:
            raise BrowserAutomationError(
                "No browser automation library available",
                details={"install_cmd": "pip install patchright && patchright install chrome"},
            )

        self._playwright = await async_playwright().start()

        if USING_PATCHRIGHT:
            # Patchright with persistent context (most undetectable)
            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                channel="chrome",  # Use real Chrome, not Chromium
                headless=False,  # Set False but use --headless=new in args
                args=[
                    "--headless=new",  # New headless mode (Chrome 112+)
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
                no_viewport=False,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )
            logger.info("Initialized Patchright with headless=new mode")
        else:
            # Standard Playwright with stealth scripts
            browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                ],
            )

            # Try to load existing session
            storage_state = self.session_dir / "session.json"
            self._context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                storage_state=str(storage_state) if storage_state.exists() else None,
            )

            # Inject stealth scripts
            await self._context.add_init_script(STEALTH_SCRIPTS)
            logger.info("Initialized Playwright with stealth scripts")

        # Get or create page
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()

        self._initialized = True
        logger.info("Headless LinkedIn scraper initialized")

    async def set_cookies(
        self,
        li_at: str,
        jsessionid: str | None = None,
    ) -> None:
        """
        Set LinkedIn session cookies.

        Args:
            li_at: LinkedIn session token (required)
            jsessionid: JSESSIONID token (optional but recommended)
        """
        if not self._initialized:
            await self.initialize()

        cookies = [
            {
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            },
        ]

        if jsessionid:
            # JSESSIONID needs quotes in value
            jsessionid_value = jsessionid if jsessionid.startswith('"') else f'"{jsessionid}"'
            cookies.append({
                "name": "JSESSIONID",
                "value": jsessionid_value,
                "domain": ".linkedin.com",
                "path": "/",
            })

        await self._context.add_cookies(cookies)
        logger.info("LinkedIn cookies configured")

    async def _human_delay(
        self,
        min_ms: int = 500,
        max_ms: int = 2000,
    ) -> None:
        """Add human-like random delay."""
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    async def _scroll_naturally(self, times: int = 3) -> None:
        """Scroll page in human-like manner."""
        for _ in range(times):
            scroll_amount = random.randint(200, 600)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self._human_delay(300, 800)

    async def _save_session(self) -> None:
        """Save browser session state."""
        if self._context:
            try:
                storage_path = self.session_dir / "session.json"
                await self._context.storage_state(path=str(storage_path))
                logger.debug("Browser session saved")
            except Exception as e:
                logger.warning("Failed to save session", error=str(e))

    async def close(self) -> None:
        """Close browser and save session."""
        await self._save_session()

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._initialized = False
        logger.info("Headless scraper closed")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # =========================================================================
    # Profile Methods
    # =========================================================================

    async def get_profile(self, public_id: str) -> dict[str, Any]:
        """
        Get LinkedIn profile data by scraping the profile page.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data dictionary
        """
        if not self._initialized:
            await self.initialize()

        url = f"https://www.linkedin.com/in/{public_id}/"

        logger.info("Scraping profile", public_id=public_id)

        await self._human_delay(1000, 2000)
        await self._page.goto(url, wait_until="networkidle", timeout=30000)
        await self._human_delay(1500, 3000)
        await self._scroll_naturally(2)

        # Check if we got redirected to login
        if "login" in self._page.url.lower() or "authwall" in self._page.url.lower():
            raise LinkedInAuthError(
                "Session expired - redirected to login page",
                details={"suggestion": "Refresh cookies with linkedin-mcp-auth extract-cookies"},
            )

        # Extract profile data from page
        profile = await self._page.evaluate("""
            () => {
                const data = {};

                // Name
                const nameEl = document.querySelector('h1.text-heading-xlarge');
                if (nameEl) data.name = nameEl.textContent.trim();

                // Headline
                const headlineEl = document.querySelector('div.text-body-medium.break-words');
                if (headlineEl) data.headline = headlineEl.textContent.trim();

                // Location
                const locationEl = document.querySelector('span.text-body-small.inline.t-black--light.break-words');
                if (locationEl) data.location = locationEl.textContent.trim();

                // Connections count
                const connectionsEl = document.querySelector('a[href*="/connections/"] span.t-bold');
                if (connectionsEl) {
                    const text = connectionsEl.textContent.trim();
                    const match = text.match(/([\\d,]+)/);
                    if (match) data.connections = parseInt(match[1].replace(/,/g, ''));
                }

                // Profile photo
                const photoEl = document.querySelector('img.pv-top-card-profile-picture__image');
                if (photoEl) data.profile_photo = photoEl.src;

                // About section
                const aboutSection = document.querySelector('#about');
                if (aboutSection) {
                    const aboutText = aboutSection.parentElement.querySelector('.inline-show-more-text span[aria-hidden="true"]');
                    if (aboutText) data.about = aboutText.textContent.trim();
                }

                // Current position
                const experienceSection = document.querySelector('#experience');
                if (experienceSection) {
                    const firstPosition = experienceSection.parentElement.querySelector('.pvs-entity');
                    if (firstPosition) {
                        const titleEl = firstPosition.querySelector('.t-bold span[aria-hidden="true"]');
                        const companyEl = firstPosition.querySelector('.t-14.t-normal span[aria-hidden="true"]');
                        if (titleEl) data.current_position = titleEl.textContent.trim();
                        if (companyEl) data.current_company = companyEl.textContent.trim();
                    }
                }

                data.public_id = location.pathname.split('/in/')[1]?.replace('/', '') || '';
                data.url = location.href;

                return data;
            }
        """)

        await self._save_session()

        return {"success": True, "profile": profile, "source": "headless_scraper"}

    # =========================================================================
    # Search Methods
    # =========================================================================

    async def search_people(
        self,
        keywords: str | None = None,
        limit: int = 10,
        keyword_title: str | None = None,
        keyword_company: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords
            limit: Maximum results to return
            keyword_title: Filter by job title
            keyword_company: Filter by company

        Returns:
            List of search results
        """
        if not self._initialized:
            await self.initialize()

        # Build search URL
        params = ["searchId=", f"origin=GLOBAL_SEARCH_HEADER"]
        if keywords:
            params.append(f"keywords={keywords}")
        if keyword_title:
            params.append(f"titleFreeText={keyword_title}")
        if keyword_company:
            params.append(f"company={keyword_company}")

        search_url = f"https://www.linkedin.com/search/results/people/?{'&'.join(params)}"

        logger.info("Searching people", keywords=keywords, limit=limit)

        await self._human_delay()
        await self._page.goto(search_url, wait_until="networkidle", timeout=30000)
        await self._human_delay(2000, 4000)

        # Check for login redirect
        if "login" in self._page.url.lower():
            raise LinkedInAuthError("Session expired - redirected to login")

        results = []
        pages_scraped = 0
        max_pages = min(limit // 10 + 1, 5)  # Max 5 pages

        while len(results) < limit and pages_scraped < max_pages:
            await self._scroll_naturally(3)
            await self._human_delay(1000, 2000)

            # Extract results from current page
            page_results = await self._page.evaluate("""
                () => {
                    const results = [];
                    const items = document.querySelectorAll('.reusable-search__result-container');

                    items.forEach(item => {
                        const nameEl = item.querySelector('.entity-result__title-text a span[aria-hidden="true"]');
                        const headlineEl = item.querySelector('.entity-result__primary-subtitle');
                        const locationEl = item.querySelector('.entity-result__secondary-subtitle');
                        const linkEl = item.querySelector('.entity-result__title-text a');

                        if (nameEl && nameEl.textContent.trim()) {
                            const link = linkEl ? linkEl.href : '';
                            let publicId = '';
                            if (link.includes('/in/')) {
                                publicId = link.split('/in/')[1].split('/')[0].split('?')[0];
                            }

                            results.push({
                                name: nameEl.textContent.trim(),
                                headline: headlineEl ? headlineEl.textContent.trim() : '',
                                location: locationEl ? locationEl.textContent.trim() : '',
                                profile_url: link,
                                public_id: publicId,
                            });
                        }
                    });

                    return results;
                }
            """)

            # Add unique results
            for result in page_results:
                if result not in results and result.get("name"):
                    results.append(result)

            pages_scraped += 1

            if len(results) >= limit:
                break

            # Try to go to next page
            next_button = await self._page.query_selector('button[aria-label="Next"]')
            if next_button:
                try:
                    await next_button.click()
                    await self._human_delay(2000, 4000)
                except Exception:
                    break
            else:
                break

        await self._save_session()

        return results[:limit]

    # =========================================================================
    # Feed Methods
    # =========================================================================

    async def get_feed(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get LinkedIn feed posts.

        Args:
            limit: Maximum posts to return

        Returns:
            List of feed posts
        """
        if not self._initialized:
            await self.initialize()

        logger.info("Scraping feed", limit=limit)

        await self._human_delay()
        await self._page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="networkidle",
            timeout=30000,
        )
        await self._human_delay(2000, 4000)

        # Check for login redirect
        if "login" in self._page.url.lower():
            raise LinkedInAuthError("Session expired - redirected to login")

        posts = []
        scroll_attempts = 0
        max_scrolls = min(limit // 3 + 2, 15)

        while len(posts) < limit and scroll_attempts < max_scrolls:
            await self._scroll_naturally(2)
            await self._human_delay(1500, 3000)

            # Extract posts
            page_posts = await self._page.evaluate("""
                () => {
                    const posts = [];
                    const items = document.querySelectorAll('.feed-shared-update-v2');

                    items.forEach(item => {
                        try {
                            const authorEl = item.querySelector('.update-components-actor__name span[aria-hidden="true"]');
                            const contentEl = item.querySelector('.feed-shared-update-v2__description');
                            const likesEl = item.querySelector('.social-details-social-counts__reactions-count');
                            const commentsEl = item.querySelector('[data-test-id="social-actions__comments"]');

                            // Get post ID/URN from data attributes if available
                            const urn = item.getAttribute('data-urn') || '';

                            if (authorEl) {
                                posts.push({
                                    author: authorEl.textContent.trim(),
                                    content: contentEl ? contentEl.textContent.trim().substring(0, 1000) : '',
                                    likes: likesEl ? parseInt(likesEl.textContent.replace(/[^0-9]/g, '')) || 0 : 0,
                                    comments: commentsEl ? parseInt(commentsEl.textContent.replace(/[^0-9]/g, '')) || 0 : 0,
                                    urn: urn,
                                });
                            }
                        } catch (e) {
                            // Skip problematic posts
                        }
                    });

                    return posts;
                }
            """)

            # Add unique posts
            existing_urns = {p.get("urn") for p in posts if p.get("urn")}
            for post in page_posts:
                if post.get("author") and post.get("urn") not in existing_urns:
                    posts.append(post)
                    if post.get("urn"):
                        existing_urns.add(post["urn"])

            scroll_attempts += 1

        await self._save_session()

        return posts[:limit]

    # =========================================================================
    # Connections Methods
    # =========================================================================

    async def get_connections(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Get user's LinkedIn connections.

        Args:
            limit: Maximum connections to return

        Returns:
            List of connections
        """
        if not self._initialized:
            await self.initialize()

        logger.info("Scraping connections", limit=limit)

        await self._human_delay()
        await self._page.goto(
            "https://www.linkedin.com/mynetwork/invite-connect/connections/",
            wait_until="networkidle",
            timeout=30000,
        )
        await self._human_delay(2000, 4000)

        # Check for login redirect
        if "login" in self._page.url.lower():
            raise LinkedInAuthError("Session expired - redirected to login")

        connections = []
        scroll_attempts = 0
        max_scrolls = min(limit // 10 + 2, 20)

        while len(connections) < limit and scroll_attempts < max_scrolls:
            await self._scroll_naturally(3)
            await self._human_delay(1000, 2000)

            # Extract connections
            page_connections = await self._page.evaluate("""
                () => {
                    const connections = [];
                    const items = document.querySelectorAll('.mn-connection-card');

                    items.forEach(item => {
                        const nameEl = item.querySelector('.mn-connection-card__name');
                        const headlineEl = item.querySelector('.mn-connection-card__occupation');
                        const linkEl = item.querySelector('a.mn-connection-card__link');

                        if (nameEl) {
                            const link = linkEl ? linkEl.href : '';
                            let publicId = '';
                            if (link.includes('/in/')) {
                                publicId = link.split('/in/')[1].split('/')[0].split('?')[0];
                            }

                            connections.push({
                                name: nameEl.textContent.trim(),
                                headline: headlineEl ? headlineEl.textContent.trim() : '',
                                profile_url: link,
                                public_id: publicId,
                            });
                        }
                    });

                    return connections;
                }
            """)

            # Add unique connections
            existing_ids = {c.get("public_id") for c in connections if c.get("public_id")}
            for conn in page_connections:
                if conn.get("public_id") and conn["public_id"] not in existing_ids:
                    connections.append(conn)
                    existing_ids.add(conn["public_id"])

            scroll_attempts += 1

        await self._save_session()

        return connections[:limit]


# =============================================================================
# Factory function
# =============================================================================

async def create_headless_scraper(
    li_at: str,
    jsessionid: str | None = None,
    session_dir: str | Path = "./data/linkedin_browser_session",
) -> HeadlessLinkedInScraper:
    """
    Factory function to create and initialize a headless LinkedIn scraper.

    This scraper works completely in the background without any visible
    browser window, making it suitable for MCP server usage.

    Args:
        li_at: LinkedIn session cookie (required)
        jsessionid: JSESSIONID cookie (optional but recommended)
        session_dir: Directory for browser session persistence

    Returns:
        Initialized HeadlessLinkedInScraper

    Example:
        scraper = await create_headless_scraper(
            li_at="AQE...",
            jsessionid="ajax:123...",
        )
        profile = await scraper.get_profile("williamhgates")
        await scraper.close()
    """
    scraper = HeadlessLinkedInScraper(
        session_dir=session_dir,
        headless=True,
    )

    await scraper.initialize()
    await scraper.set_cookies(li_at, jsessionid)

    return scraper
