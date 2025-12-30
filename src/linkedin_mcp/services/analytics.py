"""
Analytics engine for LinkedIn MCP Server.

Provides engagement analysis, optimal posting times, content performance metrics,
and audience insights.
"""

import re
from collections import Counter
from datetime import datetime
from typing import Any

from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)


class EngagementAnalyzer:
    """Analyzes engagement metrics for posts and profiles."""

    def calculate_engagement_rate(
        self,
        reactions: int,
        comments: int,
        shares: int = 0,
        views: int | None = None,
        follower_count: int | None = None,
    ) -> dict[str, Any]:
        """
        Calculate engagement rate for a post.

        Args:
            reactions: Total reactions (likes, celebrate, etc.)
            comments: Number of comments
            shares: Number of shares/reposts
            views: Number of views (if available from Partner API)
            follower_count: Author's follower count (for rate calculation)

        Returns:
            Engagement metrics and rate
        """
        total_engagement = reactions + comments + shares

        result: dict[str, Any] = {
            "total_engagement": total_engagement,
            "reactions": reactions,
            "comments": comments,
            "shares": shares,
        }

        # Calculate rate based on views (if available) or followers
        if views and views > 0:
            result["engagement_rate"] = round((total_engagement / views) * 100, 2)
            result["rate_basis"] = "views"
        elif follower_count and follower_count > 0:
            result["engagement_rate"] = round((total_engagement / follower_count) * 100, 2)
            result["rate_basis"] = "followers"
        else:
            result["engagement_rate"] = None
            result["rate_basis"] = None

        # Engagement quality score (comments weighted higher)
        if total_engagement > 0:
            quality_score = (
                (reactions * 1)
                + (comments * 3)  # Comments indicate deeper engagement
                + (shares * 2)  # Shares extend reach
            ) / total_engagement
            result["quality_score"] = round(quality_score, 2)
        else:
            result["quality_score"] = 0

        return result

    def analyze_reaction_distribution(
        self,
        reactions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze the distribution of reaction types.

        Args:
            reactions: List of reaction objects from API

        Returns:
            Reaction breakdown with percentages and insights
        """
        if not reactions:
            return {"total": 0, "breakdown": {}, "dominant_reaction": None}

        reaction_counts: Counter[str] = Counter()
        for reaction in reactions:
            reaction_type = reaction.get("reactionType", "LIKE")
            reaction_counts[reaction_type] += 1

        total = sum(reaction_counts.values())
        breakdown = {}

        for reaction_type, count in reaction_counts.most_common():
            breakdown[reaction_type] = {
                "count": count,
                "percentage": round((count / total) * 100, 1),
            }

        dominant = reaction_counts.most_common(1)[0][0] if reaction_counts else None

        # Sentiment indicator based on reaction mix
        positive_reactions = sum(
            reaction_counts.get(r, 0)
            for r in ["LIKE", "CELEBRATE", "SUPPORT", "LOVE"]
        )
        sentiment_score = round((positive_reactions / total) * 100, 1) if total > 0 else 0

        return {
            "total": total,
            "breakdown": breakdown,
            "dominant_reaction": dominant,
            "sentiment_score": sentiment_score,
        }


class ContentAnalyzer:
    """Analyzes content patterns and performance."""

    def extract_hashtags(self, content: str) -> list[str]:
        """Extract hashtags from post content."""
        if not content:
            return []
        return re.findall(r"#(\w+)", content)

    def extract_mentions(self, content: str) -> list[str]:
        """Extract @mentions from post content."""
        if not content:
            return []
        return re.findall(r"@(\w+)", content)

    def analyze_content_length(self, content: str) -> dict[str, Any]:
        """
        Analyze content length and structure.

        Returns insights on optimal length based on LinkedIn best practices.
        """
        if not content:
            return {
                "char_count": 0,
                "word_count": 0,
                "line_count": 0,
                "optimal_length": False,
            }

        char_count = len(content)
        word_count = len(content.split())
        line_count = len(content.splitlines())

        # LinkedIn optimal lengths (based on industry research)
        optimal_char_range = (1200, 2000)  # Hook in feed + detailed content
        optimal_line_range = (8, 15)

        is_optimal = (
            optimal_char_range[0] <= char_count <= optimal_char_range[1]
            and optimal_line_range[0] <= line_count <= optimal_line_range[1]
        )

        recommendation = ""
        if char_count < optimal_char_range[0]:
            recommendation = "Consider adding more context or storytelling"
        elif char_count > optimal_char_range[1]:
            recommendation = "Consider breaking into multiple posts or adding visual elements"
        else:
            recommendation = "Good length for engagement"

        return {
            "char_count": char_count,
            "word_count": word_count,
            "line_count": line_count,
            "optimal_length": is_optimal,
            "recommendation": recommendation,
        }

    def detect_content_type(self, post: dict[str, Any]) -> str:
        """
        Detect the type of content in a post.

        Returns: text, image, video, article, poll, document
        """
        # Check for various media indicators in post data
        if post.get("document"):
            return "document"
        if post.get("video"):
            return "video"
        if post.get("article"):
            return "article"
        if post.get("images") or post.get("media"):
            return "image"
        if post.get("poll"):
            return "poll"
        return "text"

    def analyze_posts_performance(
        self,
        posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze performance patterns across multiple posts.

        Args:
            posts: List of post objects with engagement data

        Returns:
            Performance analysis with recommendations
        """
        if not posts:
            return {"error": "No posts to analyze"}

        content_types: Counter[str] = Counter()
        hashtag_counter: Counter[str] = Counter()
        engagement_by_type: dict[str, list[int]] = {}
        engagement_by_length: dict[str, list[int]] = {"short": [], "medium": [], "long": []}

        for post in posts:
            content = post.get("commentary", post.get("text", ""))
            content_type = self.detect_content_type(post)
            content_types[content_type] += 1

            # Extract hashtags
            hashtags = self.extract_hashtags(content)
            hashtag_counter.update(hashtags)

            # Calculate engagement
            reactions = post.get("numLikes", 0) or post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numLikes", 0)
            comments = post.get("numComments", 0) or post.get("socialDetail", {}).get("totalSocialActivityCounts", {}).get("numComments", 0)
            total_engagement = reactions + comments

            # Track by content type
            if content_type not in engagement_by_type:
                engagement_by_type[content_type] = []
            engagement_by_type[content_type].append(total_engagement)

            # Track by length
            char_count = len(content)
            if char_count < 500:
                engagement_by_length["short"].append(total_engagement)
            elif char_count < 1500:
                engagement_by_length["medium"].append(total_engagement)
            else:
                engagement_by_length["long"].append(total_engagement)

        # Calculate averages
        avg_by_type = {}
        for ct, engagements in engagement_by_type.items():
            if engagements:
                avg_by_type[ct] = round(sum(engagements) / len(engagements), 1)

        avg_by_length = {}
        for length, engagements in engagement_by_length.items():
            if engagements:
                avg_by_length[length] = round(sum(engagements) / len(engagements), 1)

        # Best performing type
        best_type = max(avg_by_type.items(), key=lambda x: x[1])[0] if avg_by_type else None

        return {
            "total_posts_analyzed": len(posts),
            "content_type_distribution": dict(content_types),
            "average_engagement_by_type": avg_by_type,
            "average_engagement_by_length": avg_by_length,
            "best_performing_type": best_type,
            "top_hashtags": dict(hashtag_counter.most_common(10)),
            "recommendations": self._generate_recommendations(avg_by_type, avg_by_length, best_type),
        }

    def _generate_recommendations(
        self,
        avg_by_type: dict[str, float],
        avg_by_length: dict[str, float],
        best_type: str | None,
    ) -> list[str]:
        """Generate content recommendations based on analysis."""
        recommendations = []

        if best_type:
            recommendations.append(f"Focus on {best_type} content - it's your best performer")

        if avg_by_length:
            best_length = max(avg_by_length.items(), key=lambda x: x[1])[0]
            recommendations.append(f"Optimal post length: {best_length} (gets highest engagement)")

        if "video" in avg_by_type and avg_by_type.get("video", 0) > avg_by_type.get("text", 0):
            recommendations.append("Video content significantly outperforms text - increase video posts")

        if "image" in avg_by_type:
            recommendations.append("Posts with images generally get 2x more engagement")

        return recommendations


class PostingTimeAnalyzer:
    """Analyzes optimal posting times based on engagement patterns."""

    def analyze_posting_patterns(
        self,
        posts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze posting patterns and find optimal times.

        Args:
            posts: List of posts with timestamps and engagement data

        Returns:
            Optimal posting times and patterns
        """
        if not posts:
            return {"error": "No posts to analyze"}

        hour_engagement: dict[int, list[int]] = {h: [] for h in range(24)}
        day_engagement: dict[int, list[int]] = {d: [] for d in range(7)}  # 0=Monday

        for post in posts:
            # Get post timestamp
            timestamp = post.get("created", post.get("postedAt", post.get("created_at")))
            if not timestamp:
                continue

            # Parse timestamp if string
            if isinstance(timestamp, str):
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
            elif isinstance(timestamp, (int, float)):
                # Unix timestamp (milliseconds)
                dt = datetime.fromtimestamp(timestamp / 1000)
            else:
                continue

            # Get engagement
            reactions = post.get("numLikes", 0) or 0
            comments = post.get("numComments", 0) or 0
            total_engagement = reactions + comments

            hour_engagement[dt.hour].append(total_engagement)
            day_engagement[dt.weekday()].append(total_engagement)

        # Calculate averages
        avg_by_hour = {}
        for hour, engagements in hour_engagement.items():
            if engagements:
                avg_by_hour[hour] = round(sum(engagements) / len(engagements), 1)

        avg_by_day = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day, engagements in day_engagement.items():
            if engagements:
                avg_by_day[day_names[day]] = round(sum(engagements) / len(engagements), 1)

        # Find best times
        best_hours = sorted(avg_by_hour.items(), key=lambda x: x[1], reverse=True)[:3]
        best_days = sorted(avg_by_day.items(), key=lambda x: x[1], reverse=True)[:3]

        return {
            "engagement_by_hour": avg_by_hour,
            "engagement_by_day": avg_by_day,
            "best_hours": [{"hour": h, "avg_engagement": e} for h, e in best_hours],
            "best_days": [{"day": d, "avg_engagement": e} for d, e in best_days],
            "recommended_posting_times": self._format_recommendations(best_hours, best_days),
        }

    def _format_recommendations(
        self,
        best_hours: list[tuple[int, float]],
        best_days: list[tuple[str, float]],
    ) -> list[str]:
        """Format posting time recommendations."""
        recommendations = []

        if best_days:
            top_day = best_days[0][0]
            recommendations.append(f"Best day to post: {top_day}")

        if best_hours:
            formatted_hours = []
            for hour, _ in best_hours[:3]:
                if hour < 12:
                    formatted_hours.append(f"{hour}:00 AM" if hour != 0 else "12:00 AM")
                else:
                    h = hour - 12 if hour != 12 else 12
                    formatted_hours.append(f"{h}:00 PM")
            recommendations.append(f"Best times to post: {', '.join(formatted_hours)}")

        return recommendations


class AudienceAnalyzer:
    """Analyzes audience demographics and engagement patterns."""

    def analyze_commenters(
        self,
        comments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze who's commenting on posts.

        Returns audience insights based on commenter profiles.
        """
        if not comments:
            return {"total_commenters": 0, "insights": {}}

        unique_commenters: set[str] = set()
        industries: Counter[str] = Counter()
        titles: Counter[str] = Counter()

        for comment in comments:
            commenter = comment.get("commenter", {})
            commenter_id = commenter.get("publicIdentifier", commenter.get("id", ""))

            if commenter_id:
                unique_commenters.add(commenter_id)

            industry = commenter.get("industry", "")
            if industry:
                industries[industry] += 1

            title = commenter.get("title", commenter.get("headline", ""))
            # Extract key role from title
            if title:
                title_lower = title.lower()
                if any(x in title_lower for x in ["ceo", "founder", "owner"]):
                    titles["Executive"] += 1
                elif any(x in title_lower for x in ["director", "vp", "head of"]):
                    titles["Leadership"] += 1
                elif any(x in title_lower for x in ["manager", "lead"]):
                    titles["Management"] += 1
                elif any(x in title_lower for x in ["engineer", "developer"]):
                    titles["Technical"] += 1
                else:
                    titles["Other"] += 1

        return {
            "total_commenters": len(unique_commenters),
            "top_industries": dict(industries.most_common(5)),
            "audience_segments": dict(titles.most_common()),
            "insights": self._generate_audience_insights(industries, titles),
        }

    def _generate_audience_insights(
        self,
        industries: Counter[str],
        titles: Counter[str],
    ) -> list[str]:
        """Generate audience insights."""
        insights = []

        if industries:
            top_industry = industries.most_common(1)[0][0]
            insights.append(f"Primary audience industry: {top_industry}")

        if titles:
            top_segment = titles.most_common(1)[0][0]
            insights.append(f"Primary audience segment: {top_segment}")

            if titles.get("Executive", 0) > 0:
                exec_pct = round(
                    (titles["Executive"] / sum(titles.values())) * 100, 1
                )
                insights.append(f"{exec_pct}% of engaged audience are executives")

        return insights


# Global analyzers
_engagement_analyzer: EngagementAnalyzer | None = None
_content_analyzer: ContentAnalyzer | None = None
_posting_time_analyzer: PostingTimeAnalyzer | None = None
_audience_analyzer: AudienceAnalyzer | None = None


def get_engagement_analyzer() -> EngagementAnalyzer:
    """Get the engagement analyzer instance."""
    global _engagement_analyzer
    if _engagement_analyzer is None:
        _engagement_analyzer = EngagementAnalyzer()
    return _engagement_analyzer


def get_content_analyzer() -> ContentAnalyzer:
    """Get the content analyzer instance."""
    global _content_analyzer
    if _content_analyzer is None:
        _content_analyzer = ContentAnalyzer()
    return _content_analyzer


def get_posting_time_analyzer() -> PostingTimeAnalyzer:
    """Get the posting time analyzer instance."""
    global _posting_time_analyzer
    if _posting_time_analyzer is None:
        _posting_time_analyzer = PostingTimeAnalyzer()
    return _posting_time_analyzer


def get_audience_analyzer() -> AudienceAnalyzer:
    """Get the audience analyzer instance."""
    global _audience_analyzer
    if _audience_analyzer is None:
        _audience_analyzer = AudienceAnalyzer()
    return _audience_analyzer
