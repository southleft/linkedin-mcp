"""
LinkedIn Posts API Client.

Provides content creation capabilities using the official LinkedIn API
with the w_member_social scope (Share on LinkedIn product).

Supports:
- Text posts
- Image posts
- Video posts
- Document posts
- Polls
- Multi-image posts
"""

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import requests
import structlog

logger = structlog.get_logger(__name__)


class PostVisibility(str, Enum):
    """Post visibility options."""

    PUBLIC = "PUBLIC"
    CONNECTIONS = "CONNECTIONS"


class MediaType(str, Enum):
    """Media types for uploads."""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"


class LinkedInPostsClient:
    """
    LinkedIn Posts API client for content creation.

    Requires the w_member_social scope from "Share on LinkedIn" product.
    """

    API_BASE = "https://api.linkedin.com"
    API_VERSION = "202411"  # LinkedIn API versioning

    def __init__(self, access_token: str, member_urn: Optional[str] = None):
        """
        Initialize the Posts API client.

        Args:
            access_token: OAuth access token with w_member_social scope
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
                # The 'sub' field contains the member ID
                member_id = data.get("sub")
                return f"urn:li:person:{member_id}"
            else:
                logger.error("Failed to fetch member URN", status=response.status_code)
                raise ValueError("Could not fetch member URN")
        except Exception as e:
            logger.error("Error fetching member URN", error=str(e))
            raise

    def create_text_post(
        self,
        text: str,
        visibility: PostVisibility = PostVisibility.PUBLIC,
    ) -> Optional[dict[str, Any]]:
        """
        Create a text-only post.

        Args:
            text: The post content (max 3000 characters)
            visibility: Post visibility (PUBLIC or CONNECTIONS)

        Returns:
            Post data including URN if successful, None otherwise
        """
        if len(text) > 3000:
            logger.warning("Post text exceeds 3000 characters, will be truncated")
            text = text[:3000]

        payload = {
            "author": self.member_urn,
            "commentary": text,
            "visibility": visibility.value,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            response = self._session.post(
                f"{self.API_BASE}/rest/posts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                # Get the post URN from the response header
                post_urn = response.headers.get("x-restli-id", "")
                logger.info("Created text post", post_urn=post_urn)
                return {
                    "success": True,
                    "post_urn": post_urn,
                    "visibility": visibility.value,
                    "text_length": len(text),
                }
            else:
                logger.error(
                    "Failed to create text post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating text post", error=str(e))
            return {"success": False, "error": str(e)}

    def _initialize_upload(
        self,
        media_type: MediaType,
        file_size: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Initialize a media upload.

        Args:
            media_type: Type of media (IMAGE, VIDEO, DOCUMENT)
            file_size: Size of file in bytes (required for VIDEO)

        Returns:
            Upload initialization response with upload URL
        """
        if media_type == MediaType.VIDEO and not file_size:
            raise ValueError("file_size is required for video uploads")

        payload: dict[str, Any] = {
            "initializeUploadRequest": {
                "owner": self.member_urn,
            }
        }

        if media_type == MediaType.VIDEO:
            payload["initializeUploadRequest"]["fileSizeBytes"] = file_size
            payload["initializeUploadRequest"]["uploadCaptions"] = False
            payload["initializeUploadRequest"]["uploadThumbnail"] = False
            endpoint = f"{self.API_BASE}/rest/videos?action=initializeUpload"
        elif media_type == MediaType.IMAGE:
            endpoint = f"{self.API_BASE}/rest/images?action=initializeUpload"
        else:  # DOCUMENT
            endpoint = f"{self.API_BASE}/rest/documents?action=initializeUpload"

        try:
            response = self._session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )

            if response.ok:
                return response.json().get("value", {})
            else:
                logger.error(
                    "Failed to initialize upload",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except Exception as e:
            logger.error("Error initializing upload", error=str(e))
            return None

    def _upload_media(self, upload_url: str, file_path: Path) -> bool:
        """
        Upload media file to LinkedIn's servers.

        Args:
            upload_url: URL from initialize upload response
            file_path: Path to the file to upload

        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            logger.error("File not found", path=str(file_path))
            return False

        # Determine content type
        suffix = file_path.suffix.lower()
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".mp4": "video/mp4",
            ".mov": "video/quicktime",
            ".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        content_type = content_types.get(suffix, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                response = self._session.put(
                    upload_url,
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": content_type,
                    },
                    data=f,
                )

            if response.status_code in (200, 201):
                logger.info("Media uploaded successfully", path=str(file_path))
                return True
            else:
                logger.error(
                    "Failed to upload media",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return False

        except Exception as e:
            logger.error("Error uploading media", error=str(e))
            return False

    def create_image_post(
        self,
        text: str,
        image_path: Path,
        alt_text: Optional[str] = None,
        visibility: PostVisibility = PostVisibility.PUBLIC,
    ) -> Optional[dict[str, Any]]:
        """
        Create a post with an image.

        Args:
            text: Post text content
            image_path: Path to image file (JPG, PNG, GIF)
            alt_text: Accessibility text for the image
            visibility: Post visibility

        Returns:
            Post data if successful, None otherwise
        """
        # Initialize upload
        upload_data = self._initialize_upload(MediaType.IMAGE)
        if not upload_data:
            return {"success": False, "error": "Failed to initialize image upload"}

        upload_url = upload_data.get("uploadUrl")
        image_urn = upload_data.get("image")

        if not upload_url or not image_urn:
            return {"success": False, "error": "Invalid upload response"}

        # Upload the image
        if not self._upload_media(upload_url, image_path):
            return {"success": False, "error": "Failed to upload image"}

        # Create the post with the image
        payload = {
            "author": self.member_urn,
            "commentary": text[:3000] if text else "",
            "visibility": visibility.value,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "media": {
                    "id": image_urn,
                    "altText": alt_text or "",
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            response = self._session.post(
                f"{self.API_BASE}/rest/posts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                post_urn = response.headers.get("x-restli-id", "")
                logger.info("Created image post", post_urn=post_urn)
                return {
                    "success": True,
                    "post_urn": post_urn,
                    "image_urn": image_urn,
                    "visibility": visibility.value,
                }
            else:
                logger.error(
                    "Failed to create image post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating image post", error=str(e))
            return {"success": False, "error": str(e)}

    def create_poll(
        self,
        question: str,
        options: list[str],
        duration_days: int = 7,
        visibility: PostVisibility = PostVisibility.PUBLIC,
    ) -> Optional[dict[str, Any]]:
        """
        Create a poll post.

        Args:
            question: Poll question (also used as post text)
            options: List of poll options (2-4 options)
            duration_days: Poll duration in days (1, 3, 7, or 14)
            visibility: Post visibility

        Returns:
            Post data if successful, None otherwise
        """
        if len(options) < 2 or len(options) > 4:
            return {"success": False, "error": "Poll must have 2-4 options"}

        if duration_days not in (1, 3, 7, 14):
            duration_days = 7

        # Convert duration to settings format
        duration_map = {
            1: "ONE_DAY",
            3: "THREE_DAYS",
            7: "ONE_WEEK",
            14: "TWO_WEEKS",
        }

        poll_options = [{"text": opt[:140]} for opt in options]  # Max 140 chars per option

        payload = {
            "author": self.member_urn,
            "commentary": question[:3000],
            "visibility": visibility.value,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "poll": {
                    "question": question[:140],  # Max 140 chars for question
                    "options": poll_options,
                    "settings": {
                        "duration": duration_map[duration_days],
                    },
                }
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

        try:
            response = self._session.post(
                f"{self.API_BASE}/rest/posts",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                post_urn = response.headers.get("x-restli-id", "")
                logger.info("Created poll", post_urn=post_urn)
                return {
                    "success": True,
                    "post_urn": post_urn,
                    "question": question[:140],
                    "options": [o["text"] for o in poll_options],
                    "duration": duration_map[duration_days],
                    "visibility": visibility.value,
                }
            else:
                logger.error(
                    "Failed to create poll",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating poll", error=str(e))
            return {"success": False, "error": str(e)}

    def delete_post(self, post_urn: str) -> dict[str, Any]:
        """
        Delete a post.

        Args:
            post_urn: The URN of the post to delete

        Returns:
            Result dict with success status
        """
        try:
            # URL encode the URN
            encoded_urn = requests.utils.quote(post_urn, safe="")

            response = self._session.delete(
                f"{self.API_BASE}/rest/posts/{encoded_urn}",
                headers=self._get_headers(),
            )

            if response.status_code in (200, 204):
                logger.info("Deleted post", post_urn=post_urn)
                return {"success": True, "post_urn": post_urn}
            else:
                logger.error(
                    "Failed to delete post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error deleting post", error=str(e))
            return {"success": False, "error": str(e)}

    def get_post(self, post_urn: str) -> Optional[dict[str, Any]]:
        """
        Get details of a post.

        Args:
            post_urn: The URN of the post

        Returns:
            Post data if found, None otherwise
        """
        try:
            encoded_urn = requests.utils.quote(post_urn, safe="")

            response = self._session.get(
                f"{self.API_BASE}/rest/posts/{encoded_urn}",
                headers=self._get_headers(),
            )

            if response.ok:
                return response.json()
            else:
                logger.error(
                    "Failed to get post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return None

        except Exception as e:
            logger.error("Error getting post", error=str(e))
            return None

    def debug_context(self) -> dict[str, Any]:
        """
        Get debug information about the Posts client.

        Returns:
            Debug info dict
        """
        return {
            "client_type": "posts_api",
            "api_version": self.API_VERSION,
            "member_urn": self._member_urn or "not_fetched",
            "available_features": [
                "create_text_post",
                "create_image_post",
                "create_poll",
                "delete_post",
                "get_post",
            ],
            "required_scope": "w_member_social",
            "required_product": "Share on LinkedIn",
        }
