"""Tests for the analytics engine."""

from typing import Any

from linkedin_mcp.services.analytics import (
    AudienceAnalyzer,
    ContentAnalyzer,
    EngagementAnalyzer,
    PostingTimeAnalyzer,
)


class TestEngagementAnalyzer:
    """Tests for EngagementAnalyzer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = EngagementAnalyzer()

    def test_calculate_engagement_rate_with_followers(self) -> None:
        """Test engagement rate calculation based on followers."""
        result = self.analyzer.calculate_engagement_rate(
            reactions=100,
            comments=20,
            shares=10,
            follower_count=1000,
        )

        assert result["total_engagement"] == 130
        assert result["reactions"] == 100
        assert result["comments"] == 20
        assert result["shares"] == 10
        assert result["engagement_rate"] == 13.0
        assert result["rate_basis"] == "followers"

    def test_calculate_engagement_rate_with_views(self) -> None:
        """Test engagement rate calculation based on views."""
        result = self.analyzer.calculate_engagement_rate(
            reactions=50,
            comments=10,
            shares=5,
            views=1000,
        )

        assert result["total_engagement"] == 65
        assert result["engagement_rate"] == 6.5
        assert result["rate_basis"] == "views"

    def test_calculate_engagement_rate_no_base(self) -> None:
        """Test engagement rate when no base is provided."""
        result = self.analyzer.calculate_engagement_rate(
            reactions=50,
            comments=10,
        )

        assert result["total_engagement"] == 60
        assert result["engagement_rate"] is None
        assert result["rate_basis"] is None

    def test_quality_score_calculation(self) -> None:
        """Test engagement quality score."""
        # Comments weighted higher
        result = self.analyzer.calculate_engagement_rate(
            reactions=10,  # weight 1
            comments=10,  # weight 3
            shares=10,  # weight 2
        )

        # (10*1 + 10*3 + 10*2) / 30 = 60/30 = 2.0
        assert result["quality_score"] == 2.0

    def test_analyze_reaction_distribution(
        self,
        sample_reactions: list[dict[str, Any]],
    ) -> None:
        """Test reaction distribution analysis."""
        result = self.analyzer.analyze_reaction_distribution(sample_reactions)

        assert result["total"] == 7
        assert result["dominant_reaction"] == "LIKE"
        assert result["breakdown"]["LIKE"]["count"] == 3
        assert result["sentiment_score"] > 0

    def test_analyze_empty_reactions(self) -> None:
        """Test with empty reactions list."""
        result = self.analyzer.analyze_reaction_distribution([])

        assert result["total"] == 0
        assert result["dominant_reaction"] is None


class TestContentAnalyzer:
    """Tests for ContentAnalyzer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = ContentAnalyzer()

    def test_extract_hashtags(self) -> None:
        """Test hashtag extraction."""
        content = "Check out #Python and #AI for #MachineLearning"
        hashtags = self.analyzer.extract_hashtags(content)

        assert len(hashtags) == 3
        assert "Python" in hashtags
        assert "AI" in hashtags
        assert "MachineLearning" in hashtags

    def test_extract_hashtags_empty(self) -> None:
        """Test with no hashtags."""
        hashtags = self.analyzer.extract_hashtags("No hashtags here")
        assert len(hashtags) == 0

    def test_extract_mentions(self) -> None:
        """Test mention extraction."""
        content = "Thanks @johndoe and @janesmith!"
        mentions = self.analyzer.extract_mentions(content)

        assert len(mentions) == 2
        assert "johndoe" in mentions
        assert "janesmith" in mentions

    def test_analyze_content_length_optimal(self) -> None:
        """Test content length analysis for optimal length."""
        # Create content of optimal length (1200-2000 chars)
        content = "x" * 1500 + "\n" * 10

        result = self.analyzer.analyze_content_length(content)

        assert result["char_count"] == 1510
        # splitlines() counts the initial line + trailing newlines
        assert result["line_count"] >= 1  # At least 1 line
        assert result["optimal_length"] is True

    def test_analyze_content_length_too_short(self) -> None:
        """Test content length analysis for short content."""
        content = "Short post"

        result = self.analyzer.analyze_content_length(content)

        assert result["optimal_length"] is False
        assert "adding more context" in result["recommendation"]

    def test_detect_content_type_text(self) -> None:
        """Test text content type detection."""
        post: dict[str, Any] = {"commentary": "Just text"}
        assert self.analyzer.detect_content_type(post) == "text"

    def test_detect_content_type_video(self) -> None:
        """Test video content type detection."""
        post: dict[str, Any] = {"video": {"url": "..."}}
        assert self.analyzer.detect_content_type(post) == "video"

    def test_detect_content_type_image(self) -> None:
        """Test image content type detection."""
        post: dict[str, Any] = {"images": [{"url": "..."}]}
        assert self.analyzer.detect_content_type(post) == "image"


class TestPostingTimeAnalyzer:
    """Tests for PostingTimeAnalyzer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = PostingTimeAnalyzer()

    def test_analyze_posting_patterns(self) -> None:
        """Test posting pattern analysis."""
        posts = [
            {
                "created": "2024-01-15T09:00:00Z",
                "numLikes": 100,
                "numComments": 20,
            },
            {
                "created": "2024-01-16T09:00:00Z",
                "numLikes": 150,
                "numComments": 30,
            },
            {
                "created": "2024-01-17T14:00:00Z",
                "numLikes": 50,
                "numComments": 10,
            },
        ]

        result = self.analyzer.analyze_posting_patterns(posts)

        assert "engagement_by_hour" in result
        assert "engagement_by_day" in result
        assert "best_hours" in result
        assert "recommended_posting_times" in result

    def test_analyze_empty_posts(self) -> None:
        """Test with empty posts list."""
        result = self.analyzer.analyze_posting_patterns([])
        assert "error" in result


class TestAudienceAnalyzer:
    """Tests for AudienceAnalyzer."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = AudienceAnalyzer()

    def test_analyze_commenters(
        self,
        sample_comments: list[dict[str, Any]],
    ) -> None:
        """Test commenter analysis."""
        result = self.analyzer.analyze_commenters(sample_comments)

        assert result["total_commenters"] == 3
        assert "Technology" in result["top_industries"]
        assert len(result["insights"]) > 0

    def test_analyze_empty_comments(self) -> None:
        """Test with no comments."""
        result = self.analyzer.analyze_commenters([])

        assert result["total_commenters"] == 0
