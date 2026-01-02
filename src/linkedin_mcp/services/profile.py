"""
Profile management service for LinkedIn MCP Server.

Provides profile update capabilities with API and browser automation fallback.
Includes ProfileEnrichmentEngine for comprehensive multi-source profile data.
"""

import asyncio
from datetime import datetime
from typing import Any

from linkedin_mcp.core.logging import get_logger
from linkedin_mcp.services.browser import get_browser_automation

logger = get_logger(__name__)


# =============================================================================
# Profile Enrichment Engine
# =============================================================================


class ProfileEnrichmentEngine:
    """
    Multi-source profile enrichment engine.

    Philosophy: "Aggregate, Don't Fallback"

    Runs ALL available profile endpoints in PARALLEL and merges results
    into a comprehensive profile. This is NOT a fallback system - it's
    an enrichment system that always provides the most complete data possible.

    Data Sources:
    - Fresh Data API (RapidAPI) - Most reliable paid source
    - Primary profile endpoint (API)
    - Contact information (API)
    - Skills and endorsements (API)
    - Network information (connections, followers, distance) (API)
    - Member badges (Premium, Creator, etc.) (API)
    - Activity updates (API)
    - Search results (API)
    - Browser scraping (DOM) - Most reliable source when API fails
    - Web search (Public data) - Always available, no auth required
    """

    def __init__(
        self,
        linkedin_client: Any,
        browser_automation: Any = None,
        fresh_data_client: Any = None,
    ) -> None:
        self._client = linkedin_client
        self._browser = browser_automation
        self._fresh_data = fresh_data_client

    async def get_enriched_profile(
        self,
        public_id: str,
        include_activity: bool = True,
        include_network: bool = True,
        include_badges: bool = True,
    ) -> dict[str, Any]:
        """
        Get comprehensive profile data from multiple sources.

        Runs all endpoints in PARALLEL for maximum efficiency, then
        intelligently merges results into a unified profile object.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")
            include_activity: Include recent activity/posts (default: True)
            include_network: Include network stats (default: True)
            include_badges: Include member badges (default: True)

        Returns:
            Comprehensive profile data with source attribution
        """
        logger.info("Starting profile enrichment", public_id=public_id)
        start_time = datetime.now()

        # Build list of tasks to run in parallel
        # ALL sources run simultaneously for maximum data aggregation
        tasks: dict[str, Any] = {
            "profile": self._fetch_primary_profile(public_id),
            "contact_info": self._fetch_contact_info(public_id),
            "skills": self._fetch_skills(public_id),
            "search": self._fetch_from_search(public_id),
            # Web search is ALWAYS available - no auth required
            "web_search": self._fetch_from_web_search(public_id),
        }

        # Fresh Data API (RapidAPI) - Most reliable paid source
        if self._fresh_data:
            tasks["fresh_data"] = self._fetch_from_fresh_data(public_id)

        if include_network:
            tasks["network"] = self._fetch_network_info(public_id)

        if include_badges:
            tasks["badges"] = self._fetch_badges(public_id)

        if include_activity:
            tasks["activity"] = self._fetch_activity(public_id)

        # Browser scraping - most reliable source, runs in parallel with API calls
        if self._browser and self._browser.is_available:
            tasks["browser"] = self._fetch_from_browser(public_id)

        # Execute all tasks in parallel
        task_names = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        # Map results back to their names
        source_results: dict[str, Any] = {}
        for name, result in zip(task_names, results):
            if isinstance(result, Exception):
                logger.debug(f"Enrichment source '{name}' failed", error=str(result))
                source_results[name] = None
            else:
                source_results[name] = result

        # Merge all results into unified profile
        enriched = self._merge_results(public_id, source_results)

        # Add enrichment metadata
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        enriched["_enrichment"] = {
            "sources_attempted": task_names,
            "sources_successful": [
                name for name, result in source_results.items()
                if result is not None
            ],
            "duration_ms": round(duration_ms, 2),
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            "Profile enrichment complete",
            public_id=public_id,
            sources_successful=len(enriched["_enrichment"]["sources_successful"]),
            duration_ms=duration_ms,
        )

        return enriched

    async def _fetch_primary_profile(self, public_id: str) -> dict[str, Any] | None:
        """Fetch primary profile data."""
        try:
            return await self._client.get_profile(public_id)
        except Exception as e:
            logger.debug("Primary profile fetch failed", error=str(e))
            return None

    async def _fetch_from_fresh_data(self, public_id: str) -> dict[str, Any] | None:
        """Fetch profile data from Fresh Data API (RapidAPI)."""
        if not self._fresh_data:
            return None
        try:
            return await self._fresh_data.get_profile(public_id=public_id)
        except Exception as e:
            logger.debug("Fresh Data API profile fetch failed", error=str(e))
            return None

    async def _fetch_contact_info(self, public_id: str) -> dict[str, Any] | None:
        """Fetch contact information."""
        try:
            return await self._client.get_profile_contact_info(public_id)
        except Exception as e:
            logger.debug("Contact info fetch failed", error=str(e))
            return None

    async def _fetch_skills(self, public_id: str) -> list[dict[str, Any]] | None:
        """Fetch skills and endorsements."""
        try:
            return await self._client.get_profile_skills(public_id)
        except Exception as e:
            logger.debug("Skills fetch failed", error=str(e))
            return None

    async def _fetch_network_info(self, public_id: str) -> dict[str, Any] | None:
        """Fetch network information (connections, followers, distance)."""
        try:
            return await self._client.get_profile_network_info(public_id)
        except Exception as e:
            logger.debug("Network info fetch failed", error=str(e))
            return None

    async def _fetch_badges(self, public_id: str) -> dict[str, Any] | None:
        """Fetch member badges (Premium, Creator, etc.)."""
        try:
            return await self._client.get_profile_member_badges(public_id)
        except Exception as e:
            logger.debug("Badges fetch failed", error=str(e))
            return None

    async def _fetch_activity(self, public_id: str) -> list[dict[str, Any]] | None:
        """Fetch recent activity updates."""
        try:
            return await self._client.get_profile_updates(public_id, limit=5)
        except Exception as e:
            logger.debug("Activity fetch failed", error=str(e))
            return None

    async def _fetch_from_search(self, public_id: str) -> dict[str, Any] | None:
        """Search for profile to get basic info (name, headline, photo)."""
        try:
            results = await self._client.search_people(keywords=public_id, limit=10)
            # Find exact match
            for result in results:
                if result.get("public_id") == public_id:
                    return result
            return None
        except Exception as e:
            logger.debug("Search fetch failed", error=str(e))
            return None

    async def _fetch_from_browser(self, public_id: str) -> dict[str, Any] | None:
        """Scrape profile data directly from LinkedIn page via browser."""
        try:
            result = await self._browser.scrape_profile(public_id)
            if result.get("success"):
                return result.get("profile")
            return None
        except Exception as e:
            logger.debug("Browser scrape failed", error=str(e))
            return None

    async def _fetch_from_web_search(self, public_id: str) -> dict[str, Any] | None:
        """
        Search for LinkedIn profile using web search APIs.

        NOTE: This method attempts web-based profile discovery but may fail due to:
        - Bot detection (CAPTCHA challenges)
        - Rate limiting
        - Network restrictions

        This is a best-effort enrichment source that gracefully returns None on failure.

        Args:
            public_id: LinkedIn public ID (e.g., "johndoe")

        Returns:
            Profile data extracted from web search results, or None
        """
        # Web search is currently unreliable due to bot detection
        # Return None to avoid blocking the enrichment pipeline
        # TODO: Integrate with a proper search API when available
        logger.debug(
            "Web search skipped - bot detection makes this unreliable",
            public_id=public_id,
        )
        return None

    def _merge_results(
        self,
        public_id: str,
        sources: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge results from all sources into a unified profile.

        Priority order for conflicts (highest priority first):
        1. Browser scraping (most reliable real data)
        2. Primary profile API
        3. Search results
        4. Other API sources
        """
        profile: dict[str, Any] = {
            "public_id": public_id,
        }

        # Start with primary profile if available
        primary = sources.get("profile")
        if primary and isinstance(primary, dict):
            profile.update(primary)

        # Fresh Data API is HIGH PRIORITY - comprehensive data from RapidAPI
        # Maps Fresh Data API field names to our standard names
        fresh_data = sources.get("fresh_data")
        if fresh_data and isinstance(fresh_data, dict):
            # Fresh Data API uses different field names
            if not profile.get("firstName") and fresh_data.get("first_name"):
                profile["firstName"] = fresh_data.get("first_name")
            if not profile.get("lastName") and fresh_data.get("last_name"):
                profile["lastName"] = fresh_data.get("last_name")
            if not profile.get("headline") and fresh_data.get("headline"):
                profile["headline"] = fresh_data.get("headline")
            if not profile.get("summary") and fresh_data.get("about"):
                profile["summary"] = fresh_data.get("about")
            if not profile.get("locationName") and fresh_data.get("city"):
                profile["locationName"] = fresh_data.get("city")
            if not profile.get("profilePicture") and fresh_data.get("profile_image_url"):
                profile["profilePicture"] = fresh_data.get("profile_image_url")
            if not profile.get("currentCompany") and fresh_data.get("company"):
                profile["currentCompany"] = fresh_data.get("company")
            if not profile.get("industry") and fresh_data.get("company_industry"):
                profile["industry"] = fresh_data.get("company_industry")
            # Store raw fresh_data for reference if it has rich data
            if fresh_data.get("experiences") or fresh_data.get("educations"):
                profile["_fresh_data"] = {
                    "experiences": fresh_data.get("experiences", []),
                    "educations": fresh_data.get("educations", []),
                    "languages": fresh_data.get("languages", []),
                    "certifications": fresh_data.get("certifications", []),
                }

        # Merge search results for missing basic info
        # Search uses different field names: name, jobtitle, location
        search = sources.get("search")
        if search and isinstance(search, dict):
            if not profile.get("firstName"):
                # Search may use "name" (full name) instead of firstName/lastName
                if search.get("firstName"):
                    profile["firstName"] = search.get("firstName", "")
                elif search.get("name"):
                    parts = search.get("name", "").split(" ", 1)
                    profile["firstName"] = parts[0] if parts else ""
                    if len(parts) > 1:
                        profile["lastName"] = parts[1]
            if not profile.get("lastName") and search.get("lastName"):
                profile["lastName"] = search.get("lastName", "")
            if not profile.get("headline"):
                # Search may use "jobtitle" instead of headline
                profile["headline"] = search.get("headline") or search.get("jobtitle", "")
            if not profile.get("locationName") and not profile.get("location"):
                profile["locationName"] = search.get("locationName") or search.get("location", "")
            if not profile.get("displayPictureUrl") and not profile.get("profilePicture"):
                profile["profilePicture"] = search.get("displayPictureUrl", search.get("profilePicture", ""))
            if not profile.get("industry"):
                profile["industry"] = search.get("industry", "")

        # Web search data - ALWAYS available, no auth required
        # Use this to fill in gaps when API fails
        web_search = sources.get("web_search")
        if web_search and isinstance(web_search, dict):
            if not profile.get("firstName") and web_search.get("firstName"):
                profile["firstName"] = web_search.get("firstName")
            if not profile.get("lastName") and web_search.get("lastName"):
                profile["lastName"] = web_search.get("lastName")
            if not profile.get("displayName") and web_search.get("displayName"):
                profile["displayName"] = web_search.get("displayName")
            if not profile.get("headline") and web_search.get("headline"):
                profile["headline"] = web_search.get("headline")
            if not profile.get("locationName") and web_search.get("locationName"):
                profile["locationName"] = web_search.get("locationName")
            if not profile.get("currentCompany") and web_search.get("currentCompany"):
                profile["currentCompany"] = web_search.get("currentCompany")
            # Store discovered profiles for reference
            if web_search.get("discovered_profiles"):
                profile["_web_search_profiles"] = web_search.get("discovered_profiles")

        # Browser data is HIGH PRIORITY - it overrides empty API data
        # This is the most reliable source when API returns empty values
        browser = sources.get("browser")
        if browser and isinstance(browser, dict):
            # These fields from browser scraping should fill in gaps
            if not profile.get("firstName") and browser.get("firstName"):
                profile["firstName"] = browser.get("firstName")
            if not profile.get("lastName") and browser.get("lastName"):
                profile["lastName"] = browser.get("lastName")
            if not profile.get("displayName") and browser.get("displayName"):
                profile["displayName"] = browser.get("displayName")
            if not profile.get("headline") and browser.get("headline"):
                profile["headline"] = browser.get("headline")
            if not profile.get("locationName") and browser.get("locationName"):
                profile["locationName"] = browser.get("locationName")
            if not profile.get("profilePicture") and browser.get("profilePicture"):
                profile["profilePicture"] = browser.get("profilePicture")
            if not profile.get("summary") and browser.get("summary"):
                profile["summary"] = browser.get("summary")
            if not profile.get("currentPosition") and browser.get("currentPosition"):
                profile["currentPosition"] = browser.get("currentPosition")
            if not profile.get("currentCompany") and browser.get("currentCompany"):
                profile["currentCompany"] = browser.get("currentCompany")
            if not profile.get("education") and browser.get("education"):
                profile["education"] = browser.get("education")
            # Browser badge detection
            if browser.get("is_premium"):
                profile["is_premium"] = True
            if browser.get("is_creator"):
                profile["is_creator"] = True
            if browser.get("open_to_work"):
                profile["open_to_work"] = True
            # Browser network counts
            if not profile.get("connections_count") and browser.get("connections_count"):
                profile["connections_count"] = browser.get("connections_count")
            if not profile.get("followers_count") and browser.get("followers_count"):
                profile["followers_count"] = browser.get("followers_count")
            # Browser skills (if not from API)
            if not profile.get("skills") and browser.get("skills"):
                profile["skills"] = browser.get("skills")
                profile["skills_count"] = len(browser.get("skills", []))

        # Add contact information
        contact = sources.get("contact_info")
        if contact and isinstance(contact, dict):
            profile["contact_info"] = contact

        # Add skills
        skills = sources.get("skills")
        if skills and isinstance(skills, list):
            profile["skills"] = skills
            profile["skills_count"] = len(skills)
            # Also extract top skills summary
            top_skills = sorted(
                skills,
                key=lambda x: x.get("endorsementCount", 0) if isinstance(x, dict) else 0,
                reverse=True,
            )[:5]
            profile["top_skills"] = [
                {"name": s.get("name"), "endorsements": s.get("endorsementCount", 0)}
                for s in top_skills if isinstance(s, dict)
            ]

        # Add network information
        network = sources.get("network")
        if network and isinstance(network, dict):
            profile["network"] = {
                "connections_count": network.get("connectionsCount"),
                "followers_count": network.get("followersCount"),
                "following_count": network.get("followingCount"),
                "distance": network.get("distance"),
                "is_connection": network.get("distance") == 1,
            }

        # Add badges
        badges = sources.get("badges")
        if badges and isinstance(badges, dict):
            profile["badges"] = badges
            profile["is_premium"] = badges.get("premium", False)
            profile["is_creator"] = badges.get("creator", False)
            profile["is_influencer"] = badges.get("influencer", False)

        # Add activity summary
        activity = sources.get("activity")
        if activity and isinstance(activity, list):
            profile["recent_activity"] = {
                "count": len(activity),
                "has_activity": len(activity) > 0,
                "last_post_preview": (
                    activity[0].get("commentary", {}).get("text", "")[:200]
                    if activity and isinstance(activity[0], dict)
                    else None
                ),
            }

        # Ensure we have at least a display name
        if not profile.get("firstName") and not profile.get("lastName"):
            # Use public_id as fallback name
            profile["displayName"] = public_id
        else:
            first = profile.get("firstName", "")
            last = profile.get("lastName", "")
            profile["displayName"] = f"{first} {last}".strip()

        return profile


# Global enrichment engine instance
_enrichment_engine: ProfileEnrichmentEngine | None = None


def get_enrichment_engine() -> ProfileEnrichmentEngine | None:
    """Get the profile enrichment engine instance."""
    return _enrichment_engine


def set_enrichment_engine(engine: ProfileEnrichmentEngine) -> None:
    """Set the profile enrichment engine instance."""
    global _enrichment_engine
    _enrichment_engine = engine


class ProfileManager:
    """
    Manages LinkedIn profile updates.

    Uses API when available, falls back to browser automation.
    """

    def __init__(self, linkedin_client: Any | None = None) -> None:
        self._client = linkedin_client

    @property
    def has_browser_fallback(self) -> bool:
        """Check if browser automation is available."""
        automation = get_browser_automation()
        return automation is not None and automation.is_available

    async def get_profile_sections(self) -> dict[str, Any]:
        """
        Get all editable profile sections.

        Returns overview of profile sections with current content.
        """
        if not self._client:
            return {"error": "LinkedIn client not initialized"}

        try:
            profile = await self._client.get_own_profile()

            sections = {
                "basic_info": {
                    "first_name": profile.get("firstName", ""),
                    "last_name": profile.get("lastName", ""),
                    "headline": profile.get("headline", ""),
                    "location": profile.get("locationName", ""),
                    "industry": profile.get("industryName", ""),
                },
                "about": {
                    "summary": profile.get("summary", ""),
                    "summary_length": len(profile.get("summary", "")),
                },
                "experience": {
                    "positions": len(profile.get("experience", [])),
                    "current_company": (
                        profile.get("experience", [{}])[0].get("companyName", "")
                        if profile.get("experience")
                        else ""
                    ),
                },
                "education": {
                    "schools": len(profile.get("education", [])),
                },
                "skills": {
                    "count": len(profile.get("skills", [])),
                    "top_skills": [
                        s.get("name", "")
                        for s in profile.get("skills", [])[:5]
                    ],
                },
                "languages": {
                    "count": len(profile.get("languages", [])),
                },
            }

            return {"success": True, "sections": sections}

        except Exception as e:
            logger.error("Failed to get profile sections", error=str(e))
            return {"error": str(e)}

    async def update_headline(self, headline: str) -> dict[str, Any]:
        """
        Update profile headline.

        Uses browser automation as API doesn't support this directly.

        Args:
            headline: New headline text (max 220 characters)

        Returns:
            Result with success status
        """
        if len(headline) > 220:
            return {"error": "Headline cannot exceed 220 characters"}

        automation = get_browser_automation()
        if not automation or not automation.is_available:
            return {
                "error": "Browser automation not available. This operation requires Playwright.",
                "suggestion": "Enable browser_fallback in settings and ensure Playwright is installed.",
            }

        result = await automation.update_profile_headline(headline)
        if result.get("success"):
            logger.info("Profile headline updated", length=len(headline))

        return result

    async def update_summary(self, summary: str) -> dict[str, Any]:
        """
        Update profile summary/about section.

        Uses browser automation as API doesn't support this directly.

        Args:
            summary: New summary text (max 2600 characters)

        Returns:
            Result with success status
        """
        if len(summary) > 2600:
            return {"error": "Summary cannot exceed 2600 characters"}

        automation = get_browser_automation()
        if not automation or not automation.is_available:
            return {
                "error": "Browser automation not available. This operation requires Playwright.",
                "suggestion": "Enable browser_fallback in settings and ensure Playwright is installed.",
            }

        result = await automation.update_profile_summary(summary)
        if result.get("success"):
            logger.info("Profile summary updated", length=len(summary))

        return result

    async def upload_profile_photo(self, photo_path: str) -> dict[str, Any]:
        """
        Upload a new profile photo.

        Uses browser automation.

        Args:
            photo_path: Path to the photo file

        Returns:
            Result with success status
        """
        automation = get_browser_automation()
        if not automation or not automation.is_available:
            return {
                "error": "Browser automation not available. This operation requires Playwright.",
                "suggestion": "Enable browser_fallback in settings and ensure Playwright is installed.",
            }

        result = await automation.upload_profile_photo(photo_path)
        if result.get("success"):
            logger.info("Profile photo uploaded", path=photo_path)

        return result

    async def upload_background_photo(self, photo_path: str) -> dict[str, Any]:
        """
        Upload a new background/banner photo.

        Uses browser automation.

        Args:
            photo_path: Path to the photo file

        Returns:
            Result with success status
        """
        automation = get_browser_automation()
        if not automation or not automation.is_available:
            return {
                "error": "Browser automation not available. This operation requires Playwright.",
                "suggestion": "Enable browser_fallback in settings and ensure Playwright is installed.",
            }

        result = await automation.upload_background_photo(photo_path)
        if result.get("success"):
            logger.info("Background photo uploaded", path=photo_path)

        return result

    async def add_skill(self, skill_name: str) -> dict[str, Any]:
        """
        Add a skill to profile.

        Uses browser automation.

        Args:
            skill_name: Name of the skill to add

        Returns:
            Result with success status
        """
        if not skill_name.strip():
            return {"error": "Skill name cannot be empty"}

        automation = get_browser_automation()
        if not automation or not automation.is_available:
            return {
                "error": "Browser automation not available. This operation requires Playwright.",
                "suggestion": "Enable browser_fallback in settings and ensure Playwright is installed.",
            }

        result = await automation.add_skill(skill_name)
        if result.get("success"):
            logger.info("Skill added", skill=skill_name)

        return result

    async def get_profile_completeness(self) -> dict[str, Any]:
        """
        Calculate profile completeness score.

        Returns score and suggestions for improvement.
        """
        if not self._client:
            return {"error": "LinkedIn client not initialized"}

        try:
            profile = await self._client.get_own_profile()

            # Calculate completeness
            checks = {
                "has_photo": bool(profile.get("displayPictureUrl")),
                "has_headline": bool(profile.get("headline")),
                "has_summary": bool(profile.get("summary")),
                "has_experience": len(profile.get("experience", [])) > 0,
                "has_education": len(profile.get("education", [])) > 0,
                "has_skills": len(profile.get("skills", [])) >= 5,
                "has_location": bool(profile.get("locationName")),
                "has_industry": bool(profile.get("industryName")),
            }

            completed = sum(1 for v in checks.values() if v)
            total = len(checks)
            score = round((completed / total) * 100)

            # Generate suggestions
            suggestions = []
            if not checks["has_photo"]:
                suggestions.append("Add a professional profile photo")
            if not checks["has_headline"]:
                suggestions.append("Write a compelling headline")
            if not checks["has_summary"]:
                suggestions.append("Add an About section to tell your story")
            if not checks["has_experience"]:
                suggestions.append("Add your work experience")
            if not checks["has_education"]:
                suggestions.append("Add your education background")
            if not checks["has_skills"]:
                suggestions.append("Add at least 5 skills to showcase your expertise")
            if not checks["has_location"]:
                suggestions.append("Add your location")
            if not checks["has_industry"]:
                suggestions.append("Specify your industry")

            return {
                "success": True,
                "completeness": {
                    "score": score,
                    "completed_sections": completed,
                    "total_sections": total,
                    "sections": checks,
                },
                "suggestions": suggestions,
            }

        except Exception as e:
            logger.error("Failed to calculate completeness", error=str(e))
            return {"error": str(e)}


# Global instance
_profile_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """Get the profile manager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager


def set_profile_manager(manager: ProfileManager) -> None:
    """Set the profile manager instance."""
    global _profile_manager
    _profile_manager = manager
