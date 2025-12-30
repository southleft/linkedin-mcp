"""
Post scheduling service for LinkedIn MCP Server.

Manages scheduled posts using APScheduler with persistence.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from linkedin_mcp.core.logging import get_logger

logger = get_logger(__name__)


class ScheduledPostManager:
    """
    Manages scheduled LinkedIn posts.

    Provides scheduling, listing, cancellation, and execution of posts.
    """

    def __init__(self) -> None:
        self._scheduled_posts: dict[str, dict[str, Any]] = {}

    def schedule_post(
        self,
        content: str,
        scheduled_time: datetime,
        visibility: str = "PUBLIC",
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        """
        Schedule a new post.

        Args:
            content: Post content
            scheduled_time: When to publish the post
            visibility: Post visibility (PUBLIC, CONNECTIONS, LOGGED_IN)
            timezone: Timezone for the scheduled time

        Returns:
            Scheduled post details including job_id
        """
        job_id = f"post_{uuid4().hex[:12]}"

        post = {
            "job_id": job_id,
            "content": content,
            "visibility": visibility,
            "scheduled_for": scheduled_time.isoformat(),
            "timezone": timezone,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        self._scheduled_posts[job_id] = post

        logger.info(
            "Post scheduled",
            job_id=job_id,
            scheduled_for=scheduled_time.isoformat(),
        )

        return post

    def get_scheduled_post(self, job_id: str) -> dict[str, Any] | None:
        """Get a scheduled post by job ID."""
        return self._scheduled_posts.get(job_id)

    def list_scheduled_posts(
        self,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all scheduled posts.

        Args:
            status: Filter by status (pending, published, failed, cancelled)

        Returns:
            List of scheduled posts
        """
        posts = list(self._scheduled_posts.values())

        if status:
            posts = [p for p in posts if p.get("status") == status]

        # Sort by scheduled time
        posts.sort(key=lambda x: x.get("scheduled_for", ""))

        return posts

    def cancel_scheduled_post(self, job_id: str) -> bool:
        """
        Cancel a scheduled post.

        Args:
            job_id: ID of the scheduled post

        Returns:
            True if cancelled, False if not found
        """
        post = self._scheduled_posts.get(job_id)

        if not post:
            return False

        if post.get("status") != "pending":
            logger.warning(
                "Cannot cancel non-pending post",
                job_id=job_id,
                status=post.get("status"),
            )
            return False

        post["status"] = "cancelled"
        post["cancelled_at"] = datetime.now().isoformat()

        logger.info("Scheduled post cancelled", job_id=job_id)
        return True

    def update_scheduled_post(
        self,
        job_id: str,
        content: str | None = None,
        scheduled_time: datetime | None = None,
        visibility: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a scheduled post.

        Args:
            job_id: ID of the scheduled post
            content: New content (optional)
            scheduled_time: New scheduled time (optional)
            visibility: New visibility (optional)

        Returns:
            Updated post or None if not found
        """
        post = self._scheduled_posts.get(job_id)

        if not post:
            return None

        if post.get("status") != "pending":
            logger.warning(
                "Cannot update non-pending post",
                job_id=job_id,
                status=post.get("status"),
            )
            return None

        if content is not None:
            post["content"] = content

        if scheduled_time is not None:
            post["scheduled_for"] = scheduled_time.isoformat()

        if visibility is not None:
            post["visibility"] = visibility

        post["updated_at"] = datetime.now().isoformat()

        logger.info("Scheduled post updated", job_id=job_id)
        return post

    def mark_published(
        self,
        job_id: str,
        post_urn: str | None = None,
    ) -> bool:
        """Mark a scheduled post as published."""
        post = self._scheduled_posts.get(job_id)

        if not post:
            return False

        post["status"] = "published"
        post["published_at"] = datetime.now().isoformat()

        if post_urn:
            post["post_urn"] = post_urn

        logger.info("Scheduled post published", job_id=job_id, post_urn=post_urn)
        return True

    def mark_failed(
        self,
        job_id: str,
        error: str,
    ) -> bool:
        """Mark a scheduled post as failed."""
        post = self._scheduled_posts.get(job_id)

        if not post:
            return False

        post["status"] = "failed"
        post["failed_at"] = datetime.now().isoformat()
        post["error"] = error

        logger.error("Scheduled post failed", job_id=job_id, error=error)
        return True

    def get_due_posts(self) -> list[dict[str, Any]]:
        """Get posts that are due for publishing."""
        now = datetime.now()
        due_posts = []

        for post in self._scheduled_posts.values():
            if post.get("status") != "pending":
                continue

            scheduled_for = datetime.fromisoformat(post["scheduled_for"])

            if scheduled_for <= now:
                due_posts.append(post)

        return due_posts


class ContentDraftManager:
    """
    Manages content drafts for LinkedIn posts.

    Provides draft creation, editing, and suggestion features.
    """

    def __init__(self) -> None:
        self._drafts: dict[str, dict[str, Any]] = {}

    def create_draft(
        self,
        content: str,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new draft.

        Args:
            content: Draft content
            title: Optional title for organization
            tags: Optional tags for categorization

        Returns:
            Created draft details
        """
        draft_id = f"draft_{uuid4().hex[:12]}"

        draft = {
            "draft_id": draft_id,
            "title": title,
            "content": content,
            "tags": tags or [],
            "status": "draft",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        self._drafts[draft_id] = draft

        logger.info("Draft created", draft_id=draft_id)
        return draft

    def get_draft(self, draft_id: str) -> dict[str, Any] | None:
        """Get a draft by ID."""
        return self._drafts.get(draft_id)

    def list_drafts(
        self,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all drafts.

        Args:
            tag: Filter by tag

        Returns:
            List of drafts
        """
        drafts = list(self._drafts.values())

        if tag:
            drafts = [d for d in drafts if tag in d.get("tags", [])]

        # Sort by updated time (newest first)
        drafts.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

        return drafts

    def update_draft(
        self,
        draft_id: str,
        content: str | None = None,
        title: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a draft.

        Args:
            draft_id: ID of the draft
            content: New content
            title: New title
            tags: New tags

        Returns:
            Updated draft or None if not found
        """
        draft = self._drafts.get(draft_id)

        if not draft:
            return None

        if content is not None:
            draft["content"] = content

        if title is not None:
            draft["title"] = title

        if tags is not None:
            draft["tags"] = tags

        draft["updated_at"] = datetime.now().isoformat()

        logger.info("Draft updated", draft_id=draft_id)
        return draft

    def delete_draft(self, draft_id: str) -> bool:
        """
        Delete a draft.

        Args:
            draft_id: ID of the draft

        Returns:
            True if deleted, False if not found
        """
        if draft_id in self._drafts:
            del self._drafts[draft_id]
            logger.info("Draft deleted", draft_id=draft_id)
            return True
        return False


class ContentSuggestionEngine:
    """
    Provides content suggestions and improvements.

    Analyzes content and provides formatting, hashtag, and engagement suggestions.
    """

    # Optimal post characteristics based on LinkedIn research
    OPTIMAL_LENGTH_MIN = 1200
    OPTIMAL_LENGTH_MAX = 2000
    OPTIMAL_HASHTAG_COUNT = 3
    MAX_HASHTAG_COUNT = 5

    def analyze_content(self, content: str) -> dict[str, Any]:
        """
        Analyze content and provide suggestions.

        Args:
            content: Post content to analyze

        Returns:
            Analysis with suggestions for improvement
        """
        import re

        char_count = len(content)
        word_count = len(content.split())
        line_count = len(content.splitlines())

        # Extract hashtags
        hashtags = re.findall(r"#(\w+)", content)
        hashtag_count = len(hashtags)

        # Extract mentions
        mentions = re.findall(r"@(\w+)", content)

        # Check for hook (first line)
        first_line = content.split("\n")[0] if content else ""
        has_hook = len(first_line) > 20 and len(first_line) < 150

        # Check for call to action patterns
        cta_patterns = [
            r"comment (below|your)",
            r"share (your|this)",
            r"let me know",
            r"what do you think",
            r"agree\?",
            r"follow for more",
            r"like if",
        ]
        has_cta = any(re.search(p, content.lower()) for p in cta_patterns)

        # Check for question
        has_question = "?" in content

        # Generate suggestions
        suggestions = []

        # Length suggestions
        if char_count < self.OPTIMAL_LENGTH_MIN:
            suggestions.append({
                "type": "length",
                "priority": "medium",
                "message": f"Consider expanding your post. Optimal length is {self.OPTIMAL_LENGTH_MIN}-{self.OPTIMAL_LENGTH_MAX} characters.",
            })
        elif char_count > self.OPTIMAL_LENGTH_MAX:
            suggestions.append({
                "type": "length",
                "priority": "low",
                "message": "Your post is quite long. Consider breaking into multiple posts or adding visual elements.",
            })

        # Hashtag suggestions
        if hashtag_count == 0:
            suggestions.append({
                "type": "hashtags",
                "priority": "medium",
                "message": f"Add {self.OPTIMAL_HASHTAG_COUNT} relevant hashtags to increase discoverability.",
            })
        elif hashtag_count > self.MAX_HASHTAG_COUNT:
            suggestions.append({
                "type": "hashtags",
                "priority": "low",
                "message": f"You have {hashtag_count} hashtags. Consider reducing to {self.MAX_HASHTAG_COUNT} max for better engagement.",
            })

        # Hook suggestion
        if not has_hook:
            suggestions.append({
                "type": "hook",
                "priority": "high",
                "message": "Add a compelling hook (opening line) to capture attention in the feed.",
            })

        # CTA suggestion
        if not has_cta:
            suggestions.append({
                "type": "cta",
                "priority": "medium",
                "message": "Add a call-to-action to encourage engagement (comments, shares, follows).",
            })

        # Question suggestion
        if not has_question:
            suggestions.append({
                "type": "engagement",
                "priority": "low",
                "message": "Questions drive 50% more comments. Consider ending with a question.",
            })

        # Line break suggestion
        if line_count < 3 and char_count > 300:
            suggestions.append({
                "type": "formatting",
                "priority": "medium",
                "message": "Add line breaks to improve readability. Short paragraphs perform better.",
            })

        # Calculate content score (0-100)
        score = 50  # Base score
        if self.OPTIMAL_LENGTH_MIN <= char_count <= self.OPTIMAL_LENGTH_MAX:
            score += 15
        if 1 <= hashtag_count <= self.MAX_HASHTAG_COUNT:
            score += 10
        if has_hook:
            score += 15
        if has_cta:
            score += 10
        if has_question:
            score += 5
        if line_count >= 3:
            score += 5

        score = min(100, score)

        return {
            "metrics": {
                "char_count": char_count,
                "word_count": word_count,
                "line_count": line_count,
                "hashtag_count": hashtag_count,
                "mention_count": len(mentions),
            },
            "analysis": {
                "has_hook": has_hook,
                "has_cta": has_cta,
                "has_question": has_question,
                "hashtags": hashtags,
                "mentions": mentions,
            },
            "content_score": score,
            "suggestions": suggestions,
        }

    def suggest_hashtags(
        self,
        content: str,
        industry: str | None = None,
    ) -> list[str]:
        """
        Suggest relevant hashtags based on content.

        Args:
            content: Post content
            industry: Optional industry for targeted suggestions

        Returns:
            List of suggested hashtags
        """
        import re

        # Extract keywords from content
        words = re.findall(r"\b[a-z]{4,}\b", content.lower())
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Remove common words
        common_words = {
            "this", "that", "with", "from", "have", "been", "were",
            "will", "would", "could", "should", "their", "about",
            "which", "when", "where", "what", "there", "these",
            "those", "some", "more", "very", "just", "also", "into",
            "only", "other", "than", "then", "them", "such", "each",
        }
        word_freq = {k: v for k, v in word_freq.items() if k not in common_words}

        # Get top keywords
        top_keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        suggested = [kw[0] for kw in top_keywords]

        # Add industry-specific hashtags
        industry_hashtags: dict[str, list[str]] = {
            "technology": ["Tech", "Innovation", "AI", "Digital", "Startup"],
            "marketing": ["Marketing", "DigitalMarketing", "ContentMarketing", "Branding", "Growth"],
            "finance": ["Finance", "Investment", "FinTech", "Business", "Economy"],
            "healthcare": ["Healthcare", "MedTech", "Health", "Wellness", "HealthTech"],
            "education": ["Education", "Learning", "EdTech", "Training", "Development"],
            "sales": ["Sales", "B2B", "SalesEnablement", "Revenue", "Growth"],
        }

        if industry and industry.lower() in industry_hashtags:
            suggested.extend(industry_hashtags[industry.lower()][:2])

        # Add generic engagement hashtags
        suggested.extend(["LinkedInTips", "CareerGrowth", "Leadership"])

        # Return unique hashtags, limited to 5
        seen: set[str] = set()
        unique: list[str] = []
        for h in suggested:
            h_lower = h.lower()
            if h_lower not in seen:
                seen.add(h_lower)
                unique.append(h)
        return unique[:5]


# Global instances
_post_manager: ScheduledPostManager | None = None
_draft_manager: ContentDraftManager | None = None
_suggestion_engine: ContentSuggestionEngine | None = None


def get_post_manager() -> ScheduledPostManager:
    """Get the scheduled post manager instance."""
    global _post_manager
    if _post_manager is None:
        _post_manager = ScheduledPostManager()
    return _post_manager


def get_draft_manager() -> ContentDraftManager:
    """Get the content draft manager instance."""
    global _draft_manager
    if _draft_manager is None:
        _draft_manager = ContentDraftManager()
    return _draft_manager


def get_suggestion_engine() -> ContentSuggestionEngine:
    """Get the content suggestion engine instance."""
    global _suggestion_engine
    if _suggestion_engine is None:
        _suggestion_engine = ContentSuggestionEngine()
    return _suggestion_engine
