"""
LinkedIn Analytics API Client.

Provides post analytics and content performance insights using the official
LinkedIn API with the r_member_postAnalytics scope (Community Management API).

Supports:
- Post analytics (impressions, engagement, reactions)
- Content performance analysis
- Posting recommendations
- Content calendar generation
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import requests
import structlog

logger = structlog.get_logger(__name__)


class AnalyticsMetric(str, Enum):
    """Available analytics metrics for post analysis."""

    IMPRESSION = "IMPRESSION"  # Number of times post was shown
    MEMBERS_REACHED = "MEMBERS_REACHED"  # Unique members who saw the post
    RESHARE = "RESHARE"  # Number of reshares/reposts
    REACTION = "REACTION"  # Total reactions (likes, celebrates, etc.)
    COMMENT = "COMMENT"  # Number of comments


class TimePeriod(str, Enum):
    """Time period presets for analytics queries."""

    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_YEAR = "365d"
    ALL_TIME = "all"


class LinkedInAnalyticsClient:
    """
    LinkedIn Analytics API client for content performance insights.

    Requires the r_member_postAnalytics scope from Community Management API.
    """

    API_BASE = "https://api.linkedin.com"
    API_VERSION = "202506"  # Required version for memberCreatorPostAnalytics

    def __init__(self, access_token: str, member_urn: str | None = None):
        """
        Initialize the Analytics API client.

        Args:
            access_token: OAuth access token with r_member_postAnalytics scope
            member_urn: LinkedIn member URN (e.g., "urn:li:person:ABC123")
                       If not provided, will be fetched from userinfo
        """
        self.access_token = access_token
        self._member_urn = member_urn
        self._session = requests.Session()

    def _get_headers(self, content_type: str = "application/json") -> dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": content_type,
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": self.API_VERSION,
        }

    @property
    def member_urn(self) -> str:
        """Get the authenticated member's URN."""
        if not self._member_urn:
            self._member_urn = self._fetch_member_urn()
        return self._member_urn

    def _fetch_member_urn(self) -> str:
        """Fetch member URN from userinfo endpoint."""
        try:
            response = self._session.get(
                f"{self.API_BASE}/v2/userinfo",
                headers=self._get_headers(),
            )
            if response.ok:
                data = response.json()
                member_id = data.get("sub")
                return f"urn:li:person:{member_id}"
            else:
                logger.error("Failed to fetch member URN", status=response.status_code)
                raise ValueError("Could not fetch member URN")
        except Exception as e:
            logger.error("Error fetching member URN", error=str(e))
            raise

    def get_my_posts(
        self,
        count: int = 50,
        start: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Get the authenticated user's posts.

        Args:
            count: Number of posts to retrieve (max 100)
            start: Pagination offset

        Returns:
            List of post objects with URN, content, and metadata
        """
        count = min(count, 100)  # API limit

        try:
            # Use the posts finder to get posts by author
            response = self._session.get(
                f"{self.API_BASE}/rest/posts",
                headers=self._get_headers(),
                params={
                    "author": self.member_urn,
                    "q": "author",
                    "count": count,
                    "start": start,
                    "sortBy": "LAST_MODIFIED",
                },
            )

            if response.ok:
                data = response.json()
                posts = data.get("elements", [])
                logger.info(
                    "Retrieved posts",
                    count=len(posts),
                    total=data.get("paging", {}).get("total", len(posts)),
                )
                return posts
            else:
                logger.error(
                    "Failed to get posts",
                    status=response.status_code,
                    response=response.text[:500],
                )
                return []

        except Exception as e:
            logger.error("Error getting posts", error=str(e))
            return []

    def get_post_analytics(
        self,
        post_urns: list[str],
        metrics: list[AnalyticsMetric] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Get analytics for specific posts.

        Args:
            post_urns: List of post URNs to get analytics for
            metrics: List of metrics to retrieve (default: all)

        Returns:
            Dict mapping post URN to analytics data
        """
        if not post_urns:
            return {}

        if metrics is None:
            metrics = list(AnalyticsMetric)

        try:
            # Build the query params for batch analytics
            # The API uses comma-separated URN list
            posts_param = ",".join(post_urns)

            response = self._session.get(
                f"{self.API_BASE}/rest/memberCreatorPostAnalytics",
                headers=self._get_headers(),
                params={
                    "q": "analytics",
                    "posts": posts_param,
                    "aggregation": "ALL_TIME",
                },
            )

            if response.ok:
                data = response.json()
                elements = data.get("elements", [])

                # Map results by post URN
                analytics_by_post = {}
                for element in elements:
                    post_urn = element.get("post")
                    if post_urn:
                        analytics_by_post[post_urn] = {
                            "impressions": element.get("totalImpressionCount", 0),
                            "unique_impressions": element.get("uniqueImpressionsCount", 0),
                            "reactions": element.get("reactionCount", 0),
                            "comments": element.get("commentCount", 0),
                            "shares": element.get("shareCount", 0),
                            "engagement_rate": self._calculate_engagement_rate(element),
                            "click_count": element.get("clickCount", 0),
                            "raw_data": element,
                        }

                logger.info(
                    "Retrieved post analytics",
                    posts_requested=len(post_urns),
                    posts_with_data=len(analytics_by_post),
                )
                return analytics_by_post

            else:
                logger.error(
                    "Failed to get post analytics",
                    status=response.status_code,
                    response=response.text[:500],
                )
                return {}

        except Exception as e:
            logger.error("Error getting post analytics", error=str(e))
            return {}

    def _calculate_engagement_rate(self, analytics: dict) -> float:
        """
        Calculate engagement rate from analytics data.

        Engagement rate = (reactions + comments + shares) / impressions * 100
        """
        impressions = analytics.get("totalImpressionCount", 0)
        if impressions == 0:
            return 0.0

        reactions = analytics.get("reactionCount", 0)
        comments = analytics.get("commentCount", 0)
        shares = analytics.get("shareCount", 0)

        total_engagement = reactions + comments + shares
        return round((total_engagement / impressions) * 100, 2)

    def analyze_content_performance(
        self,
        time_period: TimePeriod = TimePeriod.LAST_30_DAYS,
        min_posts: int = 5,
    ) -> dict[str, Any]:
        """
        Analyze content performance over a time period.

        Args:
            time_period: Time period to analyze
            min_posts: Minimum number of posts required for analysis

        Returns:
            Performance analysis including averages, trends, and recommendations
        """
        # Get posts
        posts = self.get_my_posts(count=100)

        if len(posts) < min_posts:
            return {
                "error": f"Not enough posts for analysis. Found {len(posts)}, need at least {min_posts}.",
                "posts_found": len(posts),
                "min_posts_required": min_posts,
            }

        # Filter posts by time period
        filtered_posts = self._filter_posts_by_time(posts, time_period)

        if len(filtered_posts) < min_posts:
            return {
                "error": f"Not enough posts in the specified time period. Found {len(filtered_posts)}.",
                "posts_in_period": len(filtered_posts),
                "time_period": time_period.value,
            }

        # Get analytics for filtered posts
        post_urns = [p.get("id") for p in filtered_posts if p.get("id")]
        analytics = self.get_post_analytics(post_urns)

        # Analyze performance
        analysis = self._compute_performance_metrics(filtered_posts, analytics)

        return analysis

    def _filter_posts_by_time(
        self,
        posts: list[dict],
        time_period: TimePeriod,
    ) -> list[dict]:
        """Filter posts by time period."""
        if time_period == TimePeriod.ALL_TIME:
            return posts

        days_map = {
            TimePeriod.LAST_7_DAYS: 7,
            TimePeriod.LAST_30_DAYS: 30,
            TimePeriod.LAST_90_DAYS: 90,
            TimePeriod.LAST_YEAR: 365,
        }

        days = days_map.get(time_period, 30)
        cutoff = datetime.now() - timedelta(days=days)

        filtered = []
        for post in posts:
            created_at = post.get("createdAt", 0)
            if created_at:
                # LinkedIn returns timestamp in milliseconds
                post_date = datetime.fromtimestamp(created_at / 1000)
                if post_date >= cutoff:
                    filtered.append(post)

        return filtered

    def _compute_performance_metrics(
        self,
        posts: list[dict],
        analytics: dict[str, dict],
    ) -> dict[str, Any]:
        """Compute performance metrics from posts and analytics."""
        # Aggregate metrics
        total_impressions = 0
        total_reactions = 0
        total_comments = 0
        total_shares = 0
        engagement_rates = []

        # Track by content type
        by_media_type = {
            "text_only": {"count": 0, "impressions": 0, "engagement": 0},
            "image": {"count": 0, "impressions": 0, "engagement": 0},
            "video": {"count": 0, "impressions": 0, "engagement": 0},
            "document": {"count": 0, "impressions": 0, "engagement": 0},
            "article": {"count": 0, "impressions": 0, "engagement": 0},
        }

        # Track by day of week
        by_day_of_week = {i: {"count": 0, "impressions": 0, "engagement": 0} for i in range(7)}

        # Track by hour
        by_hour = {i: {"count": 0, "impressions": 0, "engagement": 0} for i in range(24)}

        # Best performing posts
        best_posts = []

        for post in posts:
            post_urn = post.get("id")
            post_analytics = analytics.get(post_urn, {})

            impressions = post_analytics.get("impressions", 0)
            reactions = post_analytics.get("reactions", 0)
            comments = post_analytics.get("comments", 0)
            shares = post_analytics.get("shares", 0)
            engagement_rate = post_analytics.get("engagement_rate", 0)

            total_impressions += impressions
            total_reactions += reactions
            total_comments += comments
            total_shares += shares
            if engagement_rate > 0:
                engagement_rates.append(engagement_rate)

            # Determine media type
            media_type = self._get_post_media_type(post)
            if media_type in by_media_type:
                by_media_type[media_type]["count"] += 1
                by_media_type[media_type]["impressions"] += impressions
                by_media_type[media_type]["engagement"] += engagement_rate

            # Track timing
            created_at = post.get("createdAt", 0)
            if created_at:
                post_date = datetime.fromtimestamp(created_at / 1000)
                day = post_date.weekday()
                hour = post_date.hour

                by_day_of_week[day]["count"] += 1
                by_day_of_week[day]["impressions"] += impressions
                by_day_of_week[day]["engagement"] += engagement_rate

                by_hour[hour]["count"] += 1
                by_hour[hour]["impressions"] += impressions
                by_hour[hour]["engagement"] += engagement_rate

            # Track best posts
            best_posts.append({
                "urn": post_urn,
                "text_preview": (post.get("commentary", "") or "")[:100],
                "media_type": media_type,
                "impressions": impressions,
                "engagement_rate": engagement_rate,
                "reactions": reactions,
                "comments": comments,
                "shares": shares,
                "created_at": created_at,
            })

        # Sort best posts by engagement rate
        best_posts.sort(key=lambda x: x.get("engagement_rate", 0), reverse=True)

        # Calculate averages
        post_count = len(posts)
        avg_impressions = round(total_impressions / post_count, 1) if post_count > 0 else 0
        avg_reactions = round(total_reactions / post_count, 1) if post_count > 0 else 0
        avg_comments = round(total_comments / post_count, 1) if post_count > 0 else 0
        avg_shares = round(total_shares / post_count, 1) if post_count > 0 else 0
        avg_engagement = round(sum(engagement_rates) / len(engagement_rates), 2) if engagement_rates else 0

        # Calculate averages by media type
        for _media_type, data in by_media_type.items():
            if data["count"] > 0:
                data["avg_impressions"] = round(data["impressions"] / data["count"], 1)
                data["avg_engagement"] = round(data["engagement"] / data["count"], 2)

        # Find best posting times
        best_days = sorted(
            [(k, v) for k, v in by_day_of_week.items() if v["count"] > 0],
            key=lambda x: x[1]["engagement"] / x[1]["count"] if x[1]["count"] > 0 else 0,
            reverse=True,
        )

        best_hours = sorted(
            [(k, v) for k, v in by_hour.items() if v["count"] > 0],
            key=lambda x: x[1]["engagement"] / x[1]["count"] if x[1]["count"] > 0 else 0,
            reverse=True,
        )

        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        return {
            "summary": {
                "posts_analyzed": post_count,
                "total_impressions": total_impressions,
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "total_engagement": total_reactions + total_comments + total_shares,
            },
            "averages": {
                "impressions_per_post": avg_impressions,
                "reactions_per_post": avg_reactions,
                "comments_per_post": avg_comments,
                "shares_per_post": avg_shares,
                "engagement_rate": avg_engagement,
            },
            "by_media_type": by_media_type,
            "best_posting_times": {
                "best_days": [
                    {
                        "day": day_names[d[0]],
                        "avg_engagement": round(d[1]["engagement"] / d[1]["count"], 2) if d[1]["count"] > 0 else 0,
                        "post_count": d[1]["count"],
                    }
                    for d in best_days[:3]
                ],
                "best_hours": [
                    {
                        "hour": f"{h[0]:02d}:00",
                        "avg_engagement": round(h[1]["engagement"] / h[1]["count"], 2) if h[1]["count"] > 0 else 0,
                        "post_count": h[1]["count"],
                    }
                    for h in best_hours[:5]
                ],
            },
            "top_performing_posts": best_posts[:5],
            "analysis_timestamp": datetime.now().isoformat(),
        }

    def _get_post_media_type(self, post: dict) -> str:
        """Determine the media type of a post."""
        content = post.get("content", {})

        if content.get("article"):
            return "article"
        elif content.get("media"):
            media = content["media"]
            if isinstance(media, list) and len(media) > 0:
                media = media[0]
            media_type = media.get("mediaType", "").upper()
            if "VIDEO" in media_type:
                return "video"
            elif "IMAGE" in media_type:
                return "image"
            elif "DOCUMENT" in media_type:
                return "document"
        elif content.get("multiImage"):
            return "image"
        elif content.get("poll"):
            return "poll"

        return "text_only"

    def get_posting_recommendations(
        self,
        analysis: dict | None = None,
    ) -> dict[str, Any]:
        """
        Generate posting recommendations based on content performance.

        Args:
            analysis: Pre-computed analysis (will be generated if not provided)

        Returns:
            Recommendations for improving content strategy
        """
        if analysis is None:
            analysis = self.analyze_content_performance()

        if "error" in analysis:
            return {"error": analysis["error"]}

        recommendations = []
        insights = []

        # Media type recommendations
        by_media = analysis.get("by_media_type", {})
        best_media = None
        best_media_engagement = 0

        for media_type, data in by_media.items():
            if data.get("count", 0) >= 3 and data.get("avg_engagement", 0) > best_media_engagement:
                best_media = media_type
                best_media_engagement = data["avg_engagement"]

        if best_media:
            recommendations.append({
                "type": "media_type",
                "priority": "high",
                "recommendation": f"Focus on {best_media.replace('_', ' ')} posts",
                "reason": f"Your {best_media.replace('_', ' ')} posts have the highest average engagement rate ({best_media_engagement}%)",
            })

        # Timing recommendations
        best_times = analysis.get("best_posting_times", {})
        best_days = best_times.get("best_days", [])
        best_hours = best_times.get("best_hours", [])

        if best_days:
            top_day = best_days[0]
            recommendations.append({
                "type": "timing",
                "priority": "high",
                "recommendation": f"Post on {top_day['day']}s",
                "reason": f"Your posts on {top_day['day']} have {top_day['avg_engagement']}% average engagement",
            })

        if best_hours:
            top_hours = [h["hour"] for h in best_hours[:3]]
            recommendations.append({
                "type": "timing",
                "priority": "medium",
                "recommendation": f"Best posting times: {', '.join(top_hours)}",
                "reason": "These hours show the highest engagement based on your posting history",
            })

        # Engagement insights
        averages = analysis.get("averages", {})
        engagement_rate = averages.get("engagement_rate", 0)

        if engagement_rate < 2:
            insights.append({
                "type": "engagement",
                "observation": f"Your average engagement rate is {engagement_rate}%",
                "suggestion": "Try adding more questions or calls-to-action in your posts to encourage interaction",
            })
        elif engagement_rate >= 5:
            insights.append({
                "type": "engagement",
                "observation": f"Excellent engagement rate of {engagement_rate}%!",
                "suggestion": "Keep doing what you're doing - analyze your top posts to understand what resonates",
            })

        # Top posts insights
        top_posts = analysis.get("top_performing_posts", [])
        if top_posts:
            top_post = top_posts[0]
            insights.append({
                "type": "top_content",
                "observation": f"Your best performing post had {top_post['impressions']} impressions and {top_post['engagement_rate']}% engagement",
                "suggestion": "Review this post's content, format, and timing to replicate its success",
            })

        # Consistency insights
        summary = analysis.get("summary", {})
        posts_analyzed = summary.get("posts_analyzed", 0)

        if posts_analyzed < 10:
            recommendations.append({
                "type": "consistency",
                "priority": "medium",
                "recommendation": "Post more frequently",
                "reason": f"Only {posts_analyzed} posts analyzed - more data will improve recommendations",
            })

        return {
            "recommendations": recommendations,
            "insights": insights,
            "based_on": {
                "posts_analyzed": summary.get("posts_analyzed", 0),
                "avg_engagement_rate": averages.get("engagement_rate", 0),
                "total_impressions": summary.get("total_impressions", 0),
            },
            "generated_at": datetime.now().isoformat(),
        }

    def generate_content_calendar(
        self,
        weeks: int = 4,
        posts_per_week: int = 3,
        analysis: dict | None = None,
    ) -> dict[str, Any]:
        """
        Generate a content calendar based on performance data.

        Args:
            weeks: Number of weeks to plan
            posts_per_week: Target posts per week
            analysis: Pre-computed analysis (will be generated if not provided)

        Returns:
            Content calendar with suggested posting schedule
        """
        if analysis is None:
            analysis = self.analyze_content_performance()

        if "error" in analysis:
            return {"error": analysis["error"]}

        # Get recommendations
        recommendations = self.get_posting_recommendations(analysis)

        # Extract best times
        best_times = analysis.get("best_posting_times", {})
        best_days = best_times.get("best_days", [])
        best_hours = best_times.get("best_hours", [])

        # Extract best media types
        by_media = analysis.get("by_media_type", {})
        media_types_ranked = sorted(
            [(k, v) for k, v in by_media.items() if v.get("count", 0) > 0],
            key=lambda x: x[1].get("avg_engagement", 0),
            reverse=True,
        )

        # Generate calendar
        calendar = []
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Get preferred days (default to weekdays if no data)
        preferred_days = [d["day"] for d in best_days] if best_days else ["Tuesday", "Wednesday", "Thursday"]

        # Get preferred hours (default to business hours if no data)
        preferred_hours = [h["hour"] for h in best_hours] if best_hours else ["09:00", "12:00", "17:00"]

        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())  # Monday

        for week in range(weeks):
            week_start = start_of_week + timedelta(weeks=week)
            week_posts = []

            # Distribute posts across preferred days
            posts_scheduled = 0
            for day_name in preferred_days:
                if posts_scheduled >= posts_per_week:
                    break

                day_index = day_names.index(day_name)
                post_date = week_start + timedelta(days=day_index)

                # Skip if in the past
                if post_date < today:
                    continue

                # Select media type (rotate through best performers)
                media_index = posts_scheduled % len(media_types_ranked) if media_types_ranked else 0
                suggested_media = media_types_ranked[media_index][0] if media_types_ranked else "text_only"

                # Select time
                time_index = posts_scheduled % len(preferred_hours)
                suggested_time = preferred_hours[time_index]

                week_posts.append({
                    "date": post_date.strftime("%Y-%m-%d"),
                    "day": day_name,
                    "time": suggested_time,
                    "suggested_media_type": suggested_media.replace("_", " ").title(),
                    "content_prompt": self._generate_content_prompt(suggested_media, analysis),
                })

                posts_scheduled += 1

            if week_posts:
                calendar.append({
                    "week": week + 1,
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "posts": week_posts,
                })

        return {
            "calendar": calendar,
            "strategy": {
                "posts_per_week": posts_per_week,
                "preferred_days": preferred_days[:posts_per_week],
                "preferred_times": preferred_hours[:3],
                "best_media_types": [m[0].replace("_", " ").title() for m in media_types_ranked[:3]],
            },
            "based_on_analysis": {
                "posts_analyzed": analysis.get("summary", {}).get("posts_analyzed", 0),
                "avg_engagement": analysis.get("averages", {}).get("engagement_rate", 0),
            },
            "recommendations": recommendations.get("recommendations", []),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_content_prompt(self, media_type: str, _analysis: dict) -> str:
        """Generate a content prompt based on media type and past performance."""
        prompts = {
            "text_only": "Share a thought-provoking insight or ask your network a question",
            "image": "Share a visual that tells a story - infographic, behind-the-scenes, or achievement",
            "video": "Create a short video sharing expertise, tips, or industry insights",
            "document": "Share a carousel or PDF with valuable takeaways on a topic",
            "article": "Write a long-form piece diving deep into a subject you're expert in",
            "poll": "Create a poll to gather opinions and boost engagement",
        }

        return prompts.get(media_type, "Share valuable content with your network")
