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

    # Default persistent session directory
    DEFAULT_SESSION_DIR = Path.home() / ".linkedin-mcp" / "browser-session"

    def __init__(
        self,
        session_dir: str | Path | None = None,
        headless: bool = True,
    ):
        """
        Initialize headless scraper.

        Args:
            session_dir: Directory for browser session data (default: ~/.linkedin-mcp/browser-session/)
            headless: Run in headless mode (set False for interactive login)
        """
        self.session_dir = Path(session_dir) if session_dir else self.DEFAULT_SESSION_DIR
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._initialized = False
        self._authenticated = False

    async def initialize(self, headless: bool | None = None) -> None:
        """Initialize the browser with stealth configuration.

        Args:
            headless: Override the instance headless setting (used for interactive login).
        """
        if self._initialized:
            return

        if async_playwright is None:
            raise BrowserAutomationError(
                "No browser automation library available",
                details={"install_cmd": "pip install playwright && playwright install chromium"},
            )

        use_headless = headless if headless is not None else self.headless
        self._playwright = await async_playwright().start()
        storage_state = self.session_dir / "session.json"

        if USING_PATCHRIGHT:
            # Patchright with persistent context (most undetectable)
            args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
            if use_headless:
                args.append("--headless=new")

            self._context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                channel="chrome",
                headless=False,  # Controlled via --headless=new arg
                args=args,
                no_viewport=False,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
            )
            logger.info("Initialized Patchright", headless=use_headless)
        else:
            # Standard Playwright with stealth scripts
            self._browser = await self._playwright.chromium.launch(
                headless=use_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                ],
            )

            self._context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
                storage_state=str(storage_state) if storage_state.exists() else None,
            )

            await self._context.add_init_script(STEALTH_SCRIPTS)
            logger.info("Initialized Playwright", headless=use_headless)

        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()

        self._initialized = True
        logger.info("Headless LinkedIn scraper initialized")

    async def ensure_authenticated(self) -> bool:
        """Ensure the browser session is authenticated with LinkedIn.

        Checks the current session by navigating to LinkedIn. If the session
        is expired or missing, launches a VISIBLE browser window for the user
        to log in interactively. Saves the session to disk after successful login.

        Returns:
            True if authenticated.

        Raises:
            BrowserAutomationError: If authentication cannot be completed.
        """
        if self._authenticated:
            return True

        if not self._initialized:
            await self.initialize()

        # Try navigating to LinkedIn to check if we're logged in
        logger.info("Checking LinkedIn authentication status")
        try:
            await self._page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=20000,
            )
        except Exception as e:
            logger.warning("Navigation failed during auth check", error=str(e))

        current_url = self._page.url
        is_logged_in = (
            "linkedin.com" in current_url
            and "login" not in current_url.lower()
            and "authwall" not in current_url.lower()
            and "uas" not in current_url.lower()
        )

        if is_logged_in:
            logger.info("LinkedIn session is active")
            await self._save_session()
            self._authenticated = True
            return True

        # Session expired — need interactive login
        logger.warning("LinkedIn session expired, interactive login required")

        # Close current browser and relaunch VISIBLE for login
        await self.close()
        self._initialized = False
        self._authenticated = False

        await self.initialize(headless=False)

        await self._page.goto(
            "https://www.linkedin.com/login",
            wait_until="domcontentloaded",
            timeout=20000,
        )

        logger.info(
            "Waiting for LinkedIn login — please log in to the browser window that just opened"
        )

        # Wait for the user to complete login (up to 3 minutes)
        # After successful login, LinkedIn redirects to /feed/
        try:
            await self._page.wait_for_url(
                "**/feed/**",
                timeout=180000,  # 3 minutes
            )
        except Exception:
            # Check if they ended up somewhere else on LinkedIn (still logged in)
            current_url = self._page.url
            if "linkedin.com" in current_url and "login" not in current_url.lower():
                logger.info("Login detected via URL change")
            else:
                raise BrowserAutomationError(
                    "LinkedIn login timed out. Please try again.",
                    details={"current_url": current_url},
                )

        logger.info("LinkedIn login successful")
        await self._save_session()

        # Close visible browser, relaunch headless with saved session
        await self.close()
        self._initialized = False

        await self.initialize(headless=True)
        self._authenticated = True

        # Navigate to feed to confirm session works headlessly
        await self._page.goto(
            "https://www.linkedin.com/feed/",
            wait_until="domcontentloaded",
            timeout=20000,
        )

        current_url = self._page.url
        if "login" in current_url.lower() or "authwall" in current_url.lower():
            raise BrowserAutomationError(
                "Session did not persist after login. Please try again.",
                details={"url": current_url},
            )

        logger.info("Headless session confirmed after login")
        await self._save_session()
        return True

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

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass

        self._context = None
        self._browser = None
        self._page = None
        self._initialized = False
        logger.info("Headless scraper closed")

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # =========================================================================
    # API Fetch - Browser-based API transport
    # =========================================================================

    async def api_fetch(
        self,
        url: str,
        headers: dict | None = None,
        method: str = "GET",
        body: dict | None = None,
    ) -> dict:
        """Make an API call through the browser context.

        Uses page.evaluate() to make fetch() calls from within the authenticated
        browser session. This bypasses all TLS/bot detection since the request
        originates from a real browser with real cookies.

        Args:
            url: Full URL or path (e.g., '/voyager/api/me')
            headers: Additional headers to include
            method: HTTP method (default: GET)
            body: JSON body for POST/PUT requests (will be serialized)

        Returns:
            Parsed JSON response dict

        Raises:
            BrowserAutomationError: On network or auth errors
        """
        # Ensure browser is initialized and authenticated
        await self.ensure_authenticated()

        # Ensure we are on linkedin.com so cookies are sent
        current_url = self._page.url
        if not current_url or "linkedin.com" not in current_url:
            logger.debug("Navigating to LinkedIn feed for cookie context")
            await self._page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._human_delay(1000, 2000)

        # Convert relative paths to full URLs
        if url.startswith("/"):
            url = f"https://www.linkedin.com{url}"

        extra_headers = headers or {}

        js_function = """
            async (config) => {
                try {
                    const csrf = document.cookie.split(';').map(c => c.trim())
                        .find(c => c.startsWith('JSESSIONID='))
                        ?.split('=').slice(1).join('=').replace(/"/g, '') || '';

                    const headers = {
                        'csrf-token': csrf,
                        'X-Restli-Protocol-Version': '2.0.0',
                        'X-Li-Lang': 'en_US',
                        ...config.headers
                    };

                    const fetchOpts = {
                        method: config.method,
                        headers,
                        credentials: 'include'
                    };
                    if (config.body) {
                        fetchOpts.body = JSON.stringify(config.body);
                    }

                    const resp = await fetch(config.url, fetchOpts);

                    let data;
                    const contentType = resp.headers.get('content-type') || '';
                    if (contentType.includes('json') || contentType.includes('graphql')) {
                        data = await resp.json();
                    } else {
                        data = { _raw: await resp.text() };
                    }

                    return {
                        status: resp.status,
                        ok: resp.ok,
                        data: data
                    };
                } catch (err) {
                    return {
                        status: 0,
                        ok: false,
                        data: null,
                        error: err.message || String(err)
                    };
                }
            }
        """

        config = {"url": url, "method": method, "headers": extra_headers}
        if body is not None:
            config["body"] = body

        result = await self._page.evaluate(js_function, config)

        # Handle network-level errors
        if result.get("error"):
            raise BrowserAutomationError(
                f"Browser fetch failed: {result['error']}",
                details={"url": url, "method": method},
            )

        status = result.get("status", 0)

        # Handle auth errors with one retry after re-navigating
        if status in (401, 403):
            logger.warning(
                "Auth error from browser fetch, retrying after navigation",
                status=status,
                url=url,
            )
            await self._page.goto(
                "https://www.linkedin.com/feed/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._human_delay(1500, 3000)

            # Check if we got redirected to login — trigger re-authentication
            if "login" in self._page.url.lower() or "authwall" in self._page.url.lower():
                logger.warning("Session expired during API call, triggering re-authentication")
                self._authenticated = False
                await self.ensure_authenticated()

            # Retry the fetch once
            result = await self._page.evaluate(js_function, config)

            status = result.get("status", 0)
            if not result.get("ok"):
                raise BrowserAutomationError(
                    f"Browser fetch failed after retry with status {status}",
                    details={"url": url, "method": method},
                )

        # Handle other HTTP errors
        if not result.get("ok"):
            raise BrowserAutomationError(
                f"Browser fetch returned status {status}",
                details={"url": url, "method": method, "status": status},
            )

        return result.get("data", {})

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
