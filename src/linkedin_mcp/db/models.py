"""
Database models for LinkedIn MCP Server.

SQLAlchemy models for storing posts, analytics, scheduled jobs, and cached data.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Profile(Base):
    """Cached LinkedIn profile data."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    linkedin_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    public_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    profile_picture_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    connection_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_own_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author")

    def __repr__(self) -> str:
        return f"<Profile({self.public_id}, {self.first_name} {self.last_name})>"


class Post(Base):
    """LinkedIn post with engagement tracking."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_urn: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("profiles.id"), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str | None] = mapped_column(String(50), nullable=True)
    post_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # text, image, video, article
    media_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    mentions: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    is_own_post: Mapped[bool] = mapped_column(Boolean, default=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    author: Mapped[Profile | None] = relationship("Profile", back_populates="posts")
    analytics: Mapped[list["PostAnalytics"]] = relationship("PostAnalytics", back_populates="post")

    def __repr__(self) -> str:
        return f"<Post({self.post_urn})>"


class PostAnalytics(Base):
    """Time-series analytics for posts."""

    __tablename__ = "post_analytics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    # Engagement metrics
    likes_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    shares_count: Mapped[int] = mapped_column(Integer, default=0)
    views_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Requires Partner API

    # Reaction breakdown
    reaction_like: Mapped[int] = mapped_column(Integer, default=0)
    reaction_celebrate: Mapped[int] = mapped_column(Integer, default=0)
    reaction_support: Mapped[int] = mapped_column(Integer, default=0)
    reaction_love: Mapped[int] = mapped_column(Integer, default=0)
    reaction_insightful: Mapped[int] = mapped_column(Integer, default=0)
    reaction_funny: Mapped[int] = mapped_column(Integer, default=0)

    # Calculated metrics
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    post: Mapped[Post] = relationship("Post", back_populates="analytics")

    def __repr__(self) -> str:
        return f"<PostAnalytics(post_id={self.post_id}, recorded={self.recorded_at})>"


class ScheduledPost(Base):
    """Scheduled posts for future publishing."""

    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(50), default="PUBLIC")
    media_urls: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    # Scheduling info
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Status tracking
    status: Mapped[str] = mapped_column(
        Enum("pending", "published", "failed", "cancelled", name="scheduled_post_status"),
        default="pending",
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_post_urn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<ScheduledPost({self.job_id}, status={self.status})>"


class AnalyticsEvent(Base):
    """Event tracking for analytics."""

    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    profile_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    post_urn: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    def __repr__(self) -> str:
        return f"<AnalyticsEvent({self.event_type}, {self.created_at})>"


class CacheEntry(Base):
    """Generic cache for API responses."""

    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cache_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    cache_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<CacheEntry({self.cache_key}, expires={self.expires_at})>"

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at
