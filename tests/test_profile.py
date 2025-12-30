"""Tests for the profile management service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from linkedin_mcp.services.profile import (
    ProfileManager,
    get_profile_manager,
    set_profile_manager,
)


class TestProfileManager:
    """Tests for ProfileManager."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mock_client = MagicMock()
        self.mock_client.get_own_profile = AsyncMock(return_value={
            "firstName": "John",
            "lastName": "Doe",
            "headline": "Software Engineer",
            "summary": "Passionate developer",
            "locationName": "San Francisco",
            "industryName": "Technology",
            "displayPictureUrl": "https://example.com/photo.jpg",
            "experience": [
                {"companyName": "Tech Corp", "title": "Engineer"},
            ],
            "education": [
                {"schoolName": "Stanford University"},
            ],
            "skills": [
                {"name": "Python"},
                {"name": "JavaScript"},
                {"name": "React"},
                {"name": "Node.js"},
                {"name": "AWS"},
            ],
            "languages": [{"name": "English"}],
        })
        self.manager = ProfileManager(linkedin_client=self.mock_client)

    @pytest.mark.asyncio
    async def test_get_profile_sections(self) -> None:
        """Test getting profile sections."""
        result = await self.manager.get_profile_sections()

        assert result["success"] is True
        assert "sections" in result

        sections = result["sections"]
        assert sections["basic_info"]["first_name"] == "John"
        assert sections["basic_info"]["last_name"] == "Doe"
        assert sections["basic_info"]["headline"] == "Software Engineer"
        assert sections["about"]["summary"] == "Passionate developer"
        assert sections["experience"]["positions"] == 1
        assert sections["education"]["schools"] == 1
        assert sections["skills"]["count"] == 5

    @pytest.mark.asyncio
    async def test_get_profile_sections_no_client(self) -> None:
        """Test getting profile sections without client."""
        manager = ProfileManager()
        result = await manager.get_profile_sections()

        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_profile_completeness_full(self) -> None:
        """Test profile completeness with complete profile."""
        result = await self.manager.get_profile_completeness()

        assert result["success"] is True
        assert result["completeness"]["score"] == 100
        assert len(result["suggestions"]) == 0

    @pytest.mark.asyncio
    async def test_get_profile_completeness_partial(self) -> None:
        """Test profile completeness with partial profile."""
        self.mock_client.get_own_profile = AsyncMock(return_value={
            "firstName": "John",
            "lastName": "Doe",
            "headline": "Software Engineer",
            # Missing: summary, photo, experience, education, skills, location, industry
        })

        result = await self.manager.get_profile_completeness()

        assert result["success"] is True
        assert result["completeness"]["score"] < 100
        assert len(result["suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_get_profile_completeness_no_client(self) -> None:
        """Test profile completeness without client."""
        manager = ProfileManager()
        result = await manager.get_profile_completeness()

        assert "error" in result

    @pytest.mark.asyncio
    async def test_update_headline_too_long(self) -> None:
        """Test updating headline with too long text."""
        long_headline = "x" * 221

        result = await self.manager.update_headline(long_headline)

        assert "error" in result
        assert "220 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_update_summary_too_long(self) -> None:
        """Test updating summary with too long text."""
        long_summary = "x" * 2601

        result = await self.manager.update_summary(long_summary)

        assert "error" in result
        assert "2600 characters" in result["error"]

    @pytest.mark.asyncio
    async def test_add_skill_empty(self) -> None:
        """Test adding an empty skill."""
        result = await self.manager.add_skill("   ")

        assert "error" in result
        assert "empty" in result["error"]

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_update_headline_no_browser(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test updating headline without browser automation."""
        mock_get_browser.return_value = None

        result = await self.manager.update_headline("New headline")

        assert "error" in result
        assert "Browser automation not available" in result["error"]

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_update_headline_success(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test successful headline update."""
        mock_automation = MagicMock()
        mock_automation.is_available = True
        mock_automation.update_profile_headline = AsyncMock(
            return_value={"success": True}
        )
        mock_get_browser.return_value = mock_automation

        result = await self.manager.update_headline("New headline")

        assert result["success"] is True
        mock_automation.update_profile_headline.assert_called_once_with("New headline")

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_update_summary_success(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test successful summary update."""
        mock_automation = MagicMock()
        mock_automation.is_available = True
        mock_automation.update_profile_summary = AsyncMock(
            return_value={"success": True}
        )
        mock_get_browser.return_value = mock_automation

        result = await self.manager.update_summary("New summary")

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_upload_profile_photo_success(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test successful profile photo upload."""
        mock_automation = MagicMock()
        mock_automation.is_available = True
        mock_automation.upload_profile_photo = AsyncMock(
            return_value={"success": True}
        )
        mock_get_browser.return_value = mock_automation

        result = await self.manager.upload_profile_photo("/path/to/photo.jpg")

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_upload_background_photo_success(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test successful background photo upload."""
        mock_automation = MagicMock()
        mock_automation.is_available = True
        mock_automation.upload_background_photo = AsyncMock(
            return_value={"success": True}
        )
        mock_get_browser.return_value = mock_automation

        result = await self.manager.upload_background_photo("/path/to/bg.jpg")

        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("linkedin_mcp.services.profile.get_browser_automation")
    async def test_add_skill_success(
        self,
        mock_get_browser: MagicMock,
    ) -> None:
        """Test successful skill addition."""
        mock_automation = MagicMock()
        mock_automation.is_available = True
        mock_automation.add_skill = AsyncMock(return_value={"success": True})
        mock_get_browser.return_value = mock_automation

        result = await self.manager.add_skill("Python")

        assert result["success"] is True

    def test_has_browser_fallback_false(self) -> None:
        """Test browser fallback availability check when not available."""
        with patch("linkedin_mcp.services.profile.get_browser_automation") as mock:
            mock.return_value = None
            assert self.manager.has_browser_fallback is False

    def test_has_browser_fallback_true(self) -> None:
        """Test browser fallback availability check when available."""
        with patch("linkedin_mcp.services.profile.get_browser_automation") as mock:
            mock_automation = MagicMock()
            mock_automation.is_available = True
            mock.return_value = mock_automation
            assert self.manager.has_browser_fallback is True


class TestGlobalInstance:
    """Tests for global profile manager instance."""

    def test_get_profile_manager(self) -> None:
        """Test getting the global profile manager."""
        manager = get_profile_manager()
        assert isinstance(manager, ProfileManager)

    def test_set_profile_manager(self) -> None:
        """Test setting the global profile manager."""
        custom_manager = ProfileManager()
        set_profile_manager(custom_manager)

        retrieved = get_profile_manager()
        assert retrieved is custom_manager
