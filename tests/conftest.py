"""Pytest configuration and fixtures for LinkedIn MCP Server tests."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_linkedin_client() -> MagicMock:
    """Create a mock LinkedIn client."""
    client = MagicMock()
    client.rate_limit_remaining = 800

    # Mock async methods
    client.get_own_profile = AsyncMock(return_value={
        "firstName": "John",
        "lastName": "Doe",
        "headline": "Software Engineer",
        "summary": "Test summary",
        "locationName": "San Francisco, CA",
        "industryName": "Technology",
        "experience": [{"companyName": "Test Corp"}],
        "education": [{"schoolName": "Test University"}],
        "skills": [
            {"name": "Python", "endorsementCount": 50},
            {"name": "JavaScript", "endorsementCount": 30},
        ],
        "followerCount": 1000,
    })

    client.get_profile = AsyncMock(return_value={
        "firstName": "Jane",
        "lastName": "Smith",
        "headline": "Product Manager",
        "summary": "Product expert",
        "followerCount": 2000,
    })

    client.get_feed = AsyncMock(return_value=[
        {
            "urn": "urn:li:activity:123",
            "commentary": "Test post #technology",
            "numLikes": 50,
            "numComments": 10,
        },
        {
            "urn": "urn:li:activity:456",
            "commentary": "Another test post",
            "numLikes": 100,
            "numComments": 25,
        },
    ])

    client.get_profile_posts = AsyncMock(return_value=[
        {
            "urn": "urn:li:activity:789",
            "commentary": "Profile post #AI #technology",
            "numLikes": 75,
            "numComments": 15,
            "created": "2024-01-15T10:00:00Z",
        },
    ])

    client.get_post_reactions = AsyncMock(return_value=[
        {"reactionType": "LIKE"},
        {"reactionType": "LIKE"},
        {"reactionType": "CELEBRATE"},
    ])

    client.get_post_comments = AsyncMock(return_value=[
        {"text": "Great post!", "commenter": {"id": "user1"}},
        {"text": "Thanks for sharing", "commenter": {"id": "user2"}},
    ])

    client.get_profile_connections = AsyncMock(return_value=[
        {"firstName": "Alice", "industry": "Technology", "locationName": "NYC"},
        {"firstName": "Bob", "industry": "Finance", "locationName": "NYC"},
    ])

    client.create_post = AsyncMock(return_value={
        "urn": "urn:li:activity:999",
        "created": "2024-01-20T12:00:00Z",
    })

    client.react_to_post = AsyncMock(return_value=None)
    client.comment_on_post = AsyncMock(return_value={"urn": "urn:li:comment:111"})
    client.send_message = AsyncMock(return_value={"success": True})

    return client


@pytest.fixture
def sample_post() -> dict[str, Any]:
    """Sample post data for testing."""
    return {
        "urn": "urn:li:activity:123456",
        "commentary": "This is a test post about #AI and #technology. What do you think?",
        "numLikes": 150,
        "numComments": 25,
        "numShares": 10,
        "created": "2024-01-15T10:30:00Z",
    }


@pytest.fixture
def sample_profile() -> dict[str, Any]:
    """Sample profile data for testing."""
    return {
        "firstName": "John",
        "lastName": "Doe",
        "headline": "Senior Software Engineer | Python | AI/ML",
        "summary": "Passionate about building great software.",
        "locationName": "San Francisco Bay Area",
        "industryName": "Information Technology & Services",
        "experience": [
            {
                "companyName": "Tech Corp",
                "title": "Senior Engineer",
                "startDate": {"year": 2020, "month": 1},
            }
        ],
        "education": [
            {
                "schoolName": "Stanford University",
                "fieldOfStudy": "Computer Science",
            }
        ],
        "skills": [
            {"name": "Python", "endorsementCount": 99},
            {"name": "Machine Learning", "endorsementCount": 75},
            {"name": "AWS", "endorsementCount": 50},
        ],
        "followerCount": 5000,
        "connectionCount": 500,
    }


@pytest.fixture
def sample_reactions() -> list[dict[str, Any]]:
    """Sample reaction data for testing."""
    return [
        {"reactionType": "LIKE"},
        {"reactionType": "LIKE"},
        {"reactionType": "LIKE"},
        {"reactionType": "CELEBRATE"},
        {"reactionType": "CELEBRATE"},
        {"reactionType": "SUPPORT"},
        {"reactionType": "INSIGHTFUL"},
    ]


@pytest.fixture
def sample_comments() -> list[dict[str, Any]]:
    """Sample comment data for testing."""
    return [
        {
            "text": "Great insights!",
            "commenter": {
                "publicIdentifier": "user1",
                "industry": "Technology",
                "headline": "CEO at Startup",
            },
        },
        {
            "text": "Very helpful, thanks!",
            "commenter": {
                "publicIdentifier": "user2",
                "industry": "Technology",
                "headline": "Software Engineer",
            },
        },
        {
            "text": "Interesting perspective",
            "commenter": {
                "publicIdentifier": "user3",
                "industry": "Finance",
                "headline": "VP at Bank",
            },
        },
    ]
