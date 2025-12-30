"""
Profile management service for LinkedIn MCP Server.

Provides profile update capabilities with API and browser automation fallback.
"""

from typing import Any

from linkedin_mcp.core.logging import get_logger
from linkedin_mcp.services.browser import get_browser_automation

logger = get_logger(__name__)


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
