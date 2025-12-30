"""Tests for the scheduling service."""

from datetime import datetime, timedelta

from linkedin_mcp.services.scheduler import (
    ContentDraftManager,
    ContentSuggestionEngine,
    ScheduledPostManager,
    get_draft_manager,
    get_post_manager,
    get_suggestion_engine,
)


class TestScheduledPostManager:
    """Tests for ScheduledPostManager."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.manager = ScheduledPostManager()

    def test_schedule_post(self) -> None:
        """Test scheduling a new post."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        result = self.manager.schedule_post(
            content="Test post content",
            scheduled_time=scheduled_time,
            visibility="PUBLIC",
        )

        assert "job_id" in result
        assert result["content"] == "Test post content"
        assert result["visibility"] == "PUBLIC"
        assert result["status"] == "pending"

    def test_get_scheduled_post(self) -> None:
        """Test retrieving a scheduled post."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        created = self.manager.schedule_post(
            content="Test content",
            scheduled_time=scheduled_time,
        )

        retrieved = self.manager.get_scheduled_post(created["job_id"])
        assert retrieved is not None
        assert retrieved["content"] == "Test content"

    def test_get_nonexistent_post(self) -> None:
        """Test retrieving a nonexistent post."""
        result = self.manager.get_scheduled_post("nonexistent")
        assert result is None

    def test_list_scheduled_posts(self) -> None:
        """Test listing scheduled posts."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        self.manager.schedule_post(
            content="Post 1",
            scheduled_time=scheduled_time,
        )
        self.manager.schedule_post(
            content="Post 2",
            scheduled_time=scheduled_time + timedelta(hours=1),
        )

        posts = self.manager.list_scheduled_posts()
        assert len(posts) == 2

    def test_list_posts_by_status(self) -> None:
        """Test listing posts filtered by status."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        post1 = self.manager.schedule_post(
            content="Post 1",
            scheduled_time=scheduled_time,
        )
        self.manager.schedule_post(
            content="Post 2",
            scheduled_time=scheduled_time,
        )

        # Cancel one post
        self.manager.cancel_scheduled_post(post1["job_id"])

        pending = self.manager.list_scheduled_posts(status="pending")
        assert len(pending) == 1

        cancelled = self.manager.list_scheduled_posts(status="cancelled")
        assert len(cancelled) == 1

    def test_cancel_scheduled_post(self) -> None:
        """Test cancelling a scheduled post."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        post = self.manager.schedule_post(
            content="Test content",
            scheduled_time=scheduled_time,
        )

        result = self.manager.cancel_scheduled_post(post["job_id"])
        assert result is True

        retrieved = self.manager.get_scheduled_post(post["job_id"])
        assert retrieved["status"] == "cancelled"

    def test_cancel_nonexistent_post(self) -> None:
        """Test cancelling a nonexistent post."""
        result = self.manager.cancel_scheduled_post("nonexistent")
        assert result is False

    def test_update_scheduled_post(self) -> None:
        """Test updating a scheduled post."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        post = self.manager.schedule_post(
            content="Original content",
            scheduled_time=scheduled_time,
            visibility="PUBLIC",
        )

        updated = self.manager.update_scheduled_post(
            job_id=post["job_id"],
            content="Updated content",
            visibility="CONNECTIONS",
        )

        assert updated is not None
        assert updated["content"] == "Updated content"
        assert updated["visibility"] == "CONNECTIONS"

    def test_mark_published(self) -> None:
        """Test marking a post as published."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        post = self.manager.schedule_post(
            content="Test content",
            scheduled_time=scheduled_time,
        )

        result = self.manager.mark_published(
            post["job_id"],
            post_urn="urn:li:activity:123",
        )

        assert result is True

        retrieved = self.manager.get_scheduled_post(post["job_id"])
        assert retrieved["status"] == "published"
        assert retrieved["post_urn"] == "urn:li:activity:123"

    def test_mark_failed(self) -> None:
        """Test marking a post as failed."""
        scheduled_time = datetime.now() + timedelta(hours=1)

        post = self.manager.schedule_post(
            content="Test content",
            scheduled_time=scheduled_time,
        )

        result = self.manager.mark_failed(post["job_id"], "API error")

        assert result is True

        retrieved = self.manager.get_scheduled_post(post["job_id"])
        assert retrieved["status"] == "failed"
        assert retrieved["error"] == "API error"

    def test_get_due_posts(self) -> None:
        """Test getting posts due for publishing."""
        # Schedule a post in the past (due now)
        past_time = datetime.now() - timedelta(minutes=5)
        future_time = datetime.now() + timedelta(hours=1)

        self.manager.schedule_post(
            content="Due post",
            scheduled_time=past_time,
        )
        self.manager.schedule_post(
            content="Future post",
            scheduled_time=future_time,
        )

        due_posts = self.manager.get_due_posts()
        assert len(due_posts) == 1
        assert due_posts[0]["content"] == "Due post"


class TestContentDraftManager:
    """Tests for ContentDraftManager."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.manager = ContentDraftManager()

    def test_create_draft(self) -> None:
        """Test creating a draft."""
        result = self.manager.create_draft(
            content="Draft content",
            title="Test Draft",
            tags=["test", "example"],
        )

        assert "draft_id" in result
        assert result["content"] == "Draft content"
        assert result["title"] == "Test Draft"
        assert result["tags"] == ["test", "example"]
        assert result["status"] == "draft"

    def test_get_draft(self) -> None:
        """Test retrieving a draft."""
        created = self.manager.create_draft(
            content="Test content",
            title="Test",
        )

        retrieved = self.manager.get_draft(created["draft_id"])
        assert retrieved is not None
        assert retrieved["content"] == "Test content"

    def test_list_drafts(self) -> None:
        """Test listing drafts."""
        self.manager.create_draft(content="Draft 1")
        self.manager.create_draft(content="Draft 2")

        drafts = self.manager.list_drafts()
        assert len(drafts) == 2

    def test_list_drafts_by_tag(self) -> None:
        """Test listing drafts filtered by tag."""
        self.manager.create_draft(content="Draft 1", tags=["tech"])
        self.manager.create_draft(content="Draft 2", tags=["marketing"])

        tech_drafts = self.manager.list_drafts(tag="tech")
        assert len(tech_drafts) == 1
        assert tech_drafts[0]["content"] == "Draft 1"

    def test_update_draft(self) -> None:
        """Test updating a draft."""
        draft = self.manager.create_draft(
            content="Original",
            title="Original Title",
        )

        updated = self.manager.update_draft(
            draft_id=draft["draft_id"],
            content="Updated content",
            title="Updated Title",
        )

        assert updated is not None
        assert updated["content"] == "Updated content"
        assert updated["title"] == "Updated Title"

    def test_delete_draft(self) -> None:
        """Test deleting a draft."""
        draft = self.manager.create_draft(content="To delete")

        result = self.manager.delete_draft(draft["draft_id"])
        assert result is True

        retrieved = self.manager.get_draft(draft["draft_id"])
        assert retrieved is None

    def test_delete_nonexistent_draft(self) -> None:
        """Test deleting a nonexistent draft."""
        result = self.manager.delete_draft("nonexistent")
        assert result is False


class TestContentSuggestionEngine:
    """Tests for ContentSuggestionEngine."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.engine = ContentSuggestionEngine()

    def test_analyze_short_content(self) -> None:
        """Test analyzing short content."""
        result = self.engine.analyze_content("Short post")

        assert result["metrics"]["char_count"] < 1200
        assert any(s["type"] == "length" for s in result["suggestions"])

    def test_analyze_content_with_hashtags(self) -> None:
        """Test analyzing content with hashtags."""
        content = "Great post about #Technology and #Innovation"
        result = self.engine.analyze_content(content)

        assert result["metrics"]["hashtag_count"] == 2
        assert result["analysis"]["hashtags"] == ["Technology", "Innovation"]

    def test_analyze_content_with_mentions(self) -> None:
        """Test analyzing content with mentions."""
        content = "Thanks @johndoe and @janesmith for the insights!"
        result = self.engine.analyze_content(content)

        assert result["metrics"]["mention_count"] == 2
        assert "johndoe" in result["analysis"]["mentions"]
        assert "janesmith" in result["analysis"]["mentions"]

    def test_analyze_content_with_cta(self) -> None:
        """Test analyzing content with call to action."""
        content = "What do you think about this? Comment below!"
        result = self.engine.analyze_content(content)

        assert result["analysis"]["has_cta"] is True
        assert result["analysis"]["has_question"] is True

    def test_analyze_optimal_content(self) -> None:
        """Test analyzing optimal length content."""
        # Create content of optimal length with good structure
        content = "x" * 1500 + "\n\n" + "What do you think? #Test"

        result = self.engine.analyze_content(content)

        assert result["content_score"] > 50

    def test_suggest_hashtags_basic(self) -> None:
        """Test basic hashtag suggestions."""
        content = "Artificial intelligence is transforming technology"
        hashtags = self.engine.suggest_hashtags(content)

        assert len(hashtags) > 0
        assert len(hashtags) <= 5

    def test_suggest_hashtags_with_industry(self) -> None:
        """Test hashtag suggestions with industry."""
        content = "New product launch announcement"
        hashtags = self.engine.suggest_hashtags(content, industry="marketing")

        # Should include marketing-related hashtags
        assert any(h.lower() in ["marketing", "digitalmarketing", "branding", "growth", "contentmarketing"] for h in hashtags)

    def test_content_score_range(self) -> None:
        """Test that content score is within valid range."""
        result = self.engine.analyze_content("Simple test")

        assert 0 <= result["content_score"] <= 100

    def test_optimal_constants(self) -> None:
        """Test that optimal constants are defined."""
        assert self.engine.OPTIMAL_LENGTH_MIN == 1200
        assert self.engine.OPTIMAL_LENGTH_MAX == 2000
        assert self.engine.OPTIMAL_HASHTAG_COUNT == 3
        assert self.engine.MAX_HASHTAG_COUNT == 5


class TestGlobalInstances:
    """Tests for global instance getters."""

    def test_get_post_manager(self) -> None:
        """Test getting the global post manager."""
        manager = get_post_manager()
        assert isinstance(manager, ScheduledPostManager)

    def test_get_draft_manager(self) -> None:
        """Test getting the global draft manager."""
        manager = get_draft_manager()
        assert isinstance(manager, ContentDraftManager)

    def test_get_suggestion_engine(self) -> None:
        """Test getting the global suggestion engine."""
        engine = get_suggestion_engine()
        assert isinstance(engine, ContentSuggestionEngine)
