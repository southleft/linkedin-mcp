"""
Browser automation service using Playwright.

Provides fallback automation for LinkedIn operations not supported by the API.
"""

import asyncio
from typing import Any

from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)


class BrowserAutomation:
    """
    Playwright-based browser automation for LinkedIn.

    Used as fallback when API operations are not available or fail.
    """

    def __init__(
        self,
        browser: Any | None = None,
        context: Any | None = None,
    ) -> None:
        self._browser = browser
        self._context = context
        self._page: Any | None = None

    async def initialize(self) -> None:
        """Initialize browser page."""
        if not self._context:
            logger.warning("Browser context not available")
            return

        try:
            self._page = await self._context.new_page()
            await self._page.set_viewport_size({"width": 1280, "height": 800})
            logger.info("Browser page initialized")
        except Exception as e:
            logger.error("Failed to initialize browser page", error=str(e))
            raise

    async def close(self) -> None:
        """Close browser page."""
        if self._page:
            await self._page.close()
            self._page = None

    @property
    def is_available(self) -> bool:
        """Check if browser automation is available."""
        return self._page is not None

    async def navigate_to_profile(self, profile_id: str | None = None) -> bool:
        """
        Navigate to a LinkedIn profile.

        Args:
            profile_id: Profile public ID. If None, navigates to own profile.

        Returns:
            True if navigation successful
        """
        if not self._page:
            return False

        try:
            if profile_id:
                url = f"https://www.linkedin.com/in/{profile_id}/"
            else:
                url = "https://www.linkedin.com/in/me/"

            await self._page.goto(url, wait_until="networkidle")
            await asyncio.sleep(1)  # Wait for dynamic content
            return True
        except Exception as e:
            logger.error("Failed to navigate to profile", error=str(e))
            return False

    async def update_profile_headline(self, headline: str) -> dict[str, Any]:
        """
        Update profile headline using browser automation.

        Args:
            headline: New headline text

        Returns:
            Result with success status
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            # Navigate to own profile
            await self.navigate_to_profile()

            # Click edit intro button
            edit_button = await self._page.query_selector(
                'button[aria-label="Edit intro"]'
            )
            if not edit_button:
                return {"success": False, "error": "Edit button not found"}

            await edit_button.click()
            await asyncio.sleep(1)

            # Find and update headline field
            headline_input = await self._page.query_selector(
                'input[id*="headline"], textarea[id*="headline"]'
            )
            if not headline_input:
                return {"success": False, "error": "Headline field not found"}

            await headline_input.fill("")
            await headline_input.fill(headline)

            # Save changes
            save_button = await self._page.query_selector(
                'button[aria-label="Save"], button:has-text("Save")'
            )
            if save_button:
                await save_button.click()
                await asyncio.sleep(2)

            return {"success": True, "headline": headline}

        except Exception as e:
            logger.error("Failed to update headline", error=str(e))
            return {"success": False, "error": str(e)}

    async def update_profile_summary(self, summary: str) -> dict[str, Any]:
        """
        Update profile summary/about section using browser automation.

        Args:
            summary: New summary text

        Returns:
            Result with success status
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            await self.navigate_to_profile()

            # Click edit about section
            about_section = await self._page.query_selector(
                'section:has-text("About")'
            )
            if not about_section:
                return {"success": False, "error": "About section not found"}

            edit_button = await about_section.query_selector(
                'button[aria-label*="Edit"]'
            )
            if not edit_button:
                return {"success": False, "error": "Edit button not found"}

            await edit_button.click()
            await asyncio.sleep(1)

            # Find and update summary field
            summary_input = await self._page.query_selector(
                'textarea[id*="summary"], textarea[id*="about"]'
            )
            if not summary_input:
                return {"success": False, "error": "Summary field not found"}

            await summary_input.fill("")
            await summary_input.fill(summary)

            # Save changes
            save_button = await self._page.query_selector(
                'button[aria-label="Save"], button:has-text("Save")'
            )
            if save_button:
                await save_button.click()
                await asyncio.sleep(2)

            return {"success": True, "summary_length": len(summary)}

        except Exception as e:
            logger.error("Failed to update summary", error=str(e))
            return {"success": False, "error": str(e)}

    async def upload_profile_photo(self, photo_path: str) -> dict[str, Any]:
        """
        Upload a profile photo using browser automation.

        Args:
            photo_path: Path to the photo file

        Returns:
            Result with success status
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            await self.navigate_to_profile()

            # Click on profile photo area
            photo_button = await self._page.query_selector(
                'button[aria-label*="profile photo"], div.profile-photo-edit'
            )
            if not photo_button:
                return {"success": False, "error": "Photo upload button not found"}

            await photo_button.click()
            await asyncio.sleep(1)

            # Handle file upload
            file_input = await self._page.query_selector('input[type="file"]')
            if not file_input:
                return {"success": False, "error": "File input not found"}

            await file_input.set_input_files(photo_path)
            await asyncio.sleep(2)

            # Apply changes
            apply_button = await self._page.query_selector(
                'button:has-text("Apply"), button:has-text("Save")'
            )
            if apply_button:
                await apply_button.click()
                await asyncio.sleep(2)

            return {"success": True, "photo_path": photo_path}

        except Exception as e:
            logger.error("Failed to upload photo", error=str(e))
            return {"success": False, "error": str(e)}

    async def upload_background_photo(self, photo_path: str) -> dict[str, Any]:
        """
        Upload a background/banner photo using browser automation.

        Args:
            photo_path: Path to the photo file

        Returns:
            Result with success status
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            await self.navigate_to_profile()

            # Click on background photo area
            bg_button = await self._page.query_selector(
                'button[aria-label*="background"], div.background-image-edit'
            )
            if not bg_button:
                return {"success": False, "error": "Background upload button not found"}

            await bg_button.click()
            await asyncio.sleep(1)

            # Handle file upload
            file_input = await self._page.query_selector('input[type="file"]')
            if not file_input:
                return {"success": False, "error": "File input not found"}

            await file_input.set_input_files(photo_path)
            await asyncio.sleep(2)

            # Apply changes
            apply_button = await self._page.query_selector(
                'button:has-text("Apply"), button:has-text("Save")'
            )
            if apply_button:
                await apply_button.click()
                await asyncio.sleep(2)

            return {"success": True, "photo_path": photo_path}

        except Exception as e:
            logger.error("Failed to upload background", error=str(e))
            return {"success": False, "error": str(e)}

    async def add_skill(self, skill_name: str) -> dict[str, Any]:
        """
        Add a skill to profile using browser automation.

        Args:
            skill_name: Name of the skill to add

        Returns:
            Result with success status
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            await self.navigate_to_profile()

            # Navigate to skills section
            await self._page.goto(
                "https://www.linkedin.com/in/me/details/skills/",
                wait_until="networkidle",
            )
            await asyncio.sleep(1)

            # Click add skill button
            add_button = await self._page.query_selector(
                'button:has-text("Add skill"), button[aria-label*="Add skill"]'
            )
            if not add_button:
                return {"success": False, "error": "Add skill button not found"}

            await add_button.click()
            await asyncio.sleep(1)

            # Enter skill name
            skill_input = await self._page.query_selector(
                'input[placeholder*="skill"], input[aria-label*="skill"]'
            )
            if not skill_input:
                return {"success": False, "error": "Skill input not found"}

            await skill_input.fill(skill_name)
            await asyncio.sleep(1)

            # Select from dropdown
            option = await self._page.query_selector(
                f'li:has-text("{skill_name}"), div[role="option"]:has-text("{skill_name}")'
            )
            if option:
                await option.click()

            # Save
            save_button = await self._page.query_selector(
                'button:has-text("Save"), button[aria-label="Save"]'
            )
            if save_button:
                await save_button.click()
                await asyncio.sleep(2)

            return {"success": True, "skill": skill_name}

        except Exception as e:
            logger.error("Failed to add skill", error=str(e))
            return {"success": False, "error": str(e)}

    async def take_screenshot(self, path: str | None = None) -> dict[str, Any]:
        """
        Take a screenshot of the current page.

        Args:
            path: Optional path to save screenshot

        Returns:
            Screenshot data or path
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            if path:
                await self._page.screenshot(path=path, full_page=True)
                return {"success": True, "path": path}
            else:
                screenshot = await self._page.screenshot(full_page=True)
                return {"success": True, "data": screenshot}

        except Exception as e:
            logger.error("Failed to take screenshot", error=str(e))
            return {"success": False, "error": str(e)}

    async def scrape_profile(self, profile_id: str) -> dict[str, Any]:
        """
        Scrape comprehensive profile data directly from LinkedIn page.

        NOTE: This requires an active LinkedIn session in Playwright.
        LinkedIn blocks headless browsers with session cookies from other browsers.
        For best results, use Claude in Chrome's tools to scrape the profile
        directly from the user's logged-in browser session.

        Args:
            profile_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data extracted from the page
        """
        if not self._page:
            return {"success": False, "error": "Browser not available"}

        try:
            logger.info("Scraping profile via browser", profile_id=profile_id)

            # Navigate to profile
            url = f"https://www.linkedin.com/in/{profile_id}/"
            await self._page.goto(url, wait_until="networkidle")
            await asyncio.sleep(2)  # Wait for dynamic content

            # Extract profile data using JavaScript
            profile_data = await self._page.evaluate("""
                () => {
                    const profile = { public_id: window.location.pathname.split('/in/')[1]?.replace('/', '') };

                    // Name - multiple selectors for reliability
                    const nameEl = document.querySelector('h1.text-heading-xlarge') ||
                                   document.querySelector('h1.inline.t-24') ||
                                   document.querySelector('.pv-top-card--list li:first-child');
                    if (nameEl) {
                        const fullName = nameEl.textContent.trim();
                        const parts = fullName.split(' ');
                        profile.firstName = parts[0] || '';
                        profile.lastName = parts.slice(1).join(' ') || '';
                        profile.displayName = fullName;
                    }

                    // Headline
                    const headlineEl = document.querySelector('div.text-body-medium.break-words') ||
                                       document.querySelector('.pv-top-card--list-bullet + p') ||
                                       document.querySelector('.ph5.pb5 .text-body-medium');
                    if (headlineEl) profile.headline = headlineEl.textContent.trim();

                    // Location
                    const locationEl = document.querySelector('span.text-body-small.inline.t-black--light.break-words') ||
                                       document.querySelector('.pv-top-card--list-bullet li:first-child');
                    if (locationEl) profile.locationName = locationEl.textContent.trim();

                    // Profile photo
                    const photoEl = document.querySelector('img.pv-top-card-profile-picture__image') ||
                                    document.querySelector('.profile-photo-edit__preview img') ||
                                    document.querySelector('img[alt*="profile photo"]');
                    if (photoEl) profile.profilePicture = photoEl.src;

                    // About/Summary section
                    const aboutSection = document.querySelector('#about ~ .display-flex .inline-show-more-text span[aria-hidden="true"]') ||
                                         document.querySelector('.pv-about-section .pv-about__summary-text');
                    if (aboutSection) profile.summary = aboutSection.textContent.trim();

                    // Connection count
                    const connectionsEl = document.querySelector('a[href*="/connections/"] span') ||
                                          document.querySelector('li.text-body-small span.t-bold');
                    if (connectionsEl) {
                        const text = connectionsEl.textContent.trim();
                        const match = text.match(/([\\d,]+)/);
                        if (match) profile.connections_count = parseInt(match[1].replace(',', ''));
                    }

                    // Follower count
                    const followersEl = document.querySelector('a.link-without-visited-state span') ||
                                        document.querySelector('[href*="followers"] span');
                    if (followersEl) {
                        const text = followersEl.textContent.trim();
                        const match = text.match(/([\\d,]+)/);
                        if (match) profile.followers_count = parseInt(match[1].replace(',', ''));
                    }

                    // Experience - current position
                    const experienceSection = document.querySelector('#experience ~ .pvs-list__outer-container');
                    if (experienceSection) {
                        const currentRole = experienceSection.querySelector('.display-flex.flex-row');
                        if (currentRole) {
                            const roleTitle = currentRole.querySelector('.hoverable-link-text span[aria-hidden="true"]');
                            const company = currentRole.querySelector('.t-normal span[aria-hidden="true"]');
                            if (roleTitle) profile.currentPosition = roleTitle.textContent.trim();
                            if (company) profile.currentCompany = company.textContent.trim();
                        }
                    }

                    // Education
                    const educationSection = document.querySelector('#education ~ .pvs-list__outer-container');
                    if (educationSection) {
                        const schools = [];
                        const items = educationSection.querySelectorAll('.pvs-list__item--line-separated');
                        items.forEach((item, i) => {
                            if (i < 3) {
                                const name = item.querySelector('.hoverable-link-text span[aria-hidden="true"]');
                                const degree = item.querySelector('.t-normal span[aria-hidden="true"]');
                                if (name) schools.push({
                                    name: name.textContent.trim(),
                                    degree: degree ? degree.textContent.trim() : ''
                                });
                            }
                        });
                        if (schools.length > 0) profile.education = schools;
                    }

                    // Skills (if visible on profile)
                    const skillsSection = document.querySelector('#skills ~ .pvs-list__outer-container');
                    if (skillsSection) {
                        const skills = [];
                        const items = skillsSection.querySelectorAll('.pvs-list__item--one-column');
                        items.forEach((item, i) => {
                            if (i < 10) {
                                const name = item.querySelector('.hoverable-link-text span[aria-hidden="true"]');
                                const endorsements = item.querySelector('.t-black--light span[aria-hidden="true"]');
                                if (name) skills.push({
                                    name: name.textContent.trim(),
                                    endorsementCount: endorsements ? parseInt(endorsements.textContent) || 0 : 0
                                });
                            }
                        });
                        if (skills.length > 0) profile.skills = skills;
                    }

                    // Premium badge
                    profile.is_premium = !!document.querySelector('.premium-icon, [data-test-premium-badge]');

                    // Creator badge
                    profile.is_creator = !!document.querySelector('[data-test-creator-badge], .creator-badge');

                    // Open to work badge
                    profile.open_to_work = !!document.querySelector('.pv-open-to-work-badge, #OPEN_TO_WORK');

                    return profile;
                }
            """)

            logger.info(
                "Profile scraped successfully",
                profile_id=profile_id,
                has_name=bool(profile_data.get('displayName')),
                has_headline=bool(profile_data.get('headline')),
            )

            return {
                "success": True,
                "profile": profile_data,
                "source": "browser_scrape",
            }

        except Exception as e:
            logger.error("Failed to scrape profile", error=str(e))
            return {"success": False, "error": str(e)}


# Global instance
_browser_automation: BrowserAutomation | None = None


def get_browser_automation() -> BrowserAutomation | None:
    """Get the browser automation instance."""
    return _browser_automation


def set_browser_automation(automation: BrowserAutomation) -> None:
    """Set the browser automation instance."""
    global _browser_automation
    _browser_automation = automation
