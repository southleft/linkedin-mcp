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


class ReactionType(str, Enum):
    """
    LinkedIn reaction types for posts and comments.

    Maps to the UI labels:
    - LIKE = "Like" (thumbs up)
    - PRAISE = "Celebrate" (clapping hands)
    - EMPATHY = "Love" (heart)
    - INTEREST = "Insightful" (lightbulb)
    - APPRECIATION = "Support" (hands together)
    - ENTERTAINMENT = "Funny" (laughing face)

    Note: MAYBE is deprecated since API version 202307.
    """

    LIKE = "LIKE"
    PRAISE = "PRAISE"  # Celebrate
    EMPATHY = "EMPATHY"  # Love
    INTEREST = "INTEREST"  # Insightful
    APPRECIATION = "APPRECIATION"  # Support
    ENTERTAINMENT = "ENTERTAINMENT"  # Funny


def escape_little_text(text: str, preserve_hashtags: bool = True) -> str:
    """
    Escape reserved characters for LinkedIn's 'little text' format.

    LinkedIn's Posts API uses a special text format that requires certain
    characters to be escaped with a backslash to be treated as plaintext.

    Reserved characters: | { } @ [ ] ( ) < > # \\ * _ ~

    Args:
        text: The text to escape
        preserve_hashtags: If True, don't escape # when followed by word characters
                          (allows hashtags like #AI to work). Default True.

    See: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format
    """
    import re

    # Characters to always escape (order matters: backslash first)
    always_escape = ["\\", "|", "{", "}", "[", "]", "<", ">", "*", "_", "~"]

    # Start with the original text
    result = text

    # Escape backslash first to avoid double-escaping
    for char in always_escape:
        result = result.replace(char, f"\\{char}")

    # Handle @ - escape unless it looks like a mention @[Name](urn:...)
    # For now, escape all @ since we don't support mentions yet
    result = result.replace("@", "\\@")

    # Handle ( and ) - escape them
    result = result.replace("(", "\\(")
    result = result.replace(")", "\\)")

    # Handle # - preserve hashtags if requested
    if preserve_hashtags:
        # Escape # only when NOT followed by a word character (not a hashtag)
        # This preserves #hashtag but escapes standalone # or # followed by space
        result = re.sub(r"#(?!\w)", r"\\#", result)
    else:
        result = result.replace("#", "\\#")

    return result


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

        # Escape reserved characters for LinkedIn's 'little text' format
        # This prevents truncation issues with special characters
        escaped_text = escape_little_text(text)
        logger.debug(
            "Escaped text for LinkedIn",
            original_length=len(text),
            escaped_length=len(escaped_text),
        )

        payload = {
            "author": self.member_urn,
            "commentary": escaped_text,
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

    def _upload_video_chunked(
        self,
        upload_instructions: list[dict],
        file_path: Path,
    ) -> list[str] | None:
        """
        Upload video file using chunked/multi-part upload.

        LinkedIn's video API requires chunked uploads for larger files.
        Each chunk is uploaded to a separate URL with specific byte ranges.
        The ETag from each chunk response is required for finalization.

        Args:
            upload_instructions: List of upload instructions from initializeUpload response.
                Each instruction contains: firstByte, lastByte, uploadUrl
            file_path: Path to the video file to upload

        Returns:
            List of ETags from each chunk upload (required for finalization),
            or None if upload failed
        """
        if not file_path.exists():
            logger.error("Video file not found", path=str(file_path))
            return None

        file_size = file_path.stat().st_size

        # Determine content type
        suffix = file_path.suffix.lower()
        content_type = "video/mp4" if suffix == ".mp4" else "video/quicktime"

        total_chunks = len(upload_instructions)
        uploaded_part_ids: list[str] = []

        logger.info(
            "Starting chunked video upload",
            path=str(file_path),
            file_size_mb=file_size / 1024 / 1024,
            total_chunks=total_chunks,
        )

        try:
            with open(file_path, "rb") as f:
                for i, instruction in enumerate(upload_instructions):
                    first_byte = instruction.get("firstByte", 0)
                    last_byte = instruction.get("lastByte", file_size - 1)
                    upload_url = instruction.get("uploadUrl")

                    if not upload_url:
                        logger.error("Missing uploadUrl in instruction", chunk=i + 1)
                        return None

                    # Calculate chunk size
                    chunk_size = last_byte - first_byte + 1

                    # Seek to the correct position and read the chunk
                    f.seek(first_byte)
                    chunk_data = f.read(chunk_size)

                    logger.info(
                        "Uploading video chunk",
                        chunk=i + 1,
                        total=total_chunks,
                        first_byte=first_byte,
                        last_byte=last_byte,
                        chunk_size_mb=chunk_size / 1024 / 1024,
                    )

                    # Upload this chunk
                    response = self._session.put(
                        upload_url,
                        headers={
                            "Authorization": f"Bearer {self.access_token}",
                            "Content-Type": content_type,
                        },
                        data=chunk_data,
                    )

                    if response.status_code not in (200, 201):
                        logger.error(
                            "Failed to upload video chunk",
                            chunk=i + 1,
                            status=response.status_code,
                            error=response.text[:500],
                        )
                        return None

                    # Capture ETag from response headers (required for finalization)
                    etag = response.headers.get("ETag", "").strip('"')
                    if etag:
                        uploaded_part_ids.append(etag)
                        logger.info(
                            "Video chunk uploaded successfully",
                            chunk=i + 1,
                            total=total_chunks,
                            etag=etag,
                        )
                    else:
                        logger.warning(
                            "No ETag in chunk response",
                            chunk=i + 1,
                            headers=dict(response.headers),
                        )
                        # Still add empty string to maintain order
                        uploaded_part_ids.append("")

            logger.info(
                "All video chunks uploaded successfully",
                total_chunks=total_chunks,
                file_size_mb=file_size / 1024 / 1024,
                etag_count=len([e for e in uploaded_part_ids if e]),
            )
            return uploaded_part_ids

        except Exception as e:
            logger.error("Error during chunked video upload", error=str(e))
            return None

    def _finalize_video_upload(
        self,
        upload_token: str,
        uploaded_part_ids: list[str],
        video_urn: str,
    ) -> bool:
        """
        Finalize video upload after all chunks have been uploaded.

        LinkedIn requires this finalization step before the video can be used
        in a post. Without it, the video won't appear in the feed.

        Args:
            upload_token: Token from initializeUpload response
            uploaded_part_ids: List of ETags from each chunk upload
            video_urn: The video URN from initializeUpload response

        Returns:
            True if finalization successful, False otherwise
        """
        endpoint = f"{self.API_BASE}/rest/videos?action=finalizeUpload"

        payload = {
            "finalizeUploadRequest": {
                "uploadToken": upload_token,
                "uploadedPartIds": uploaded_part_ids,
                "video": video_urn,
            }
        }

        logger.info(
            "Finalizing video upload",
            video_urn=video_urn,
            part_count=len(uploaded_part_ids),
        )

        try:
            response = self._session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )

            if response.ok:
                logger.info(
                    "Video upload finalized successfully",
                    video_urn=video_urn,
                )
                return True
            else:
                logger.error(
                    "Failed to finalize video upload",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return False

        except Exception as e:
            logger.error("Error finalizing video upload", error=str(e))
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
        # Escape reserved characters for LinkedIn's 'little text' format
        escaped_text = escape_little_text(text[:3000]) if text else ""

        payload = {
            "author": self.member_urn,
            "commentary": escaped_text,
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

        # Escape reserved characters for LinkedIn's 'little text' format
        escaped_question = escape_little_text(question[:3000])

        payload = {
            "author": self.member_urn,
            "commentary": escaped_question,
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

    def create_video_post(
        self,
        text: str,
        video_path: Path,
        title: Optional[str] = None,
        visibility: PostVisibility = PostVisibility.PUBLIC,
    ) -> Optional[dict[str, Any]]:
        """
        Create a post with a video.

        LinkedIn supports video uploads up to 10 minutes for most users,
        up to 15 minutes for some accounts.

        Supported formats: MP4 (recommended), MOV
        Recommended specs: 1080p, H.264 codec, AAC audio, 30fps

        Args:
            text: Post text content
            video_path: Path to video file
            title: Optional title for the video
            visibility: Post visibility

        Returns:
            Post data if successful, None otherwise
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return {"success": False, "error": f"Video file not found: {video_path}"}

        # Get file size for upload initialization
        file_size = video_path.stat().st_size

        # LinkedIn limits: 200MB for most videos, up to 5GB for some accounts
        max_size = 200 * 1024 * 1024  # 200MB
        if file_size > max_size:
            return {
                "success": False,
                "error": f"Video file too large ({file_size / 1024 / 1024:.1f}MB). Maximum is 200MB.",
            }

        # Initialize upload with file size
        upload_data = self._initialize_upload(MediaType.VIDEO, file_size=file_size)
        if not upload_data:
            return {"success": False, "error": "Failed to initialize video upload"}

        # Video API returns uploadInstructions array for chunked uploads
        upload_instructions = upload_data.get("uploadInstructions", [])
        video_urn = upload_data.get("video")
        upload_token = upload_data.get("uploadToken")

        if not upload_instructions or not video_urn:
            logger.error("Invalid video upload response", upload_data=upload_data)
            return {"success": False, "error": "Invalid upload response - missing uploadInstructions or video URN"}

        logger.info(
            "Uploading video",
            path=str(video_path),
            size_mb=file_size / 1024 / 1024,
            video_urn=video_urn,
            chunks=len(upload_instructions),
            has_upload_token=bool(upload_token),
        )

        # Upload the video using chunked upload (handles both single and multi-part)
        # Returns list of ETags required for finalization
        uploaded_part_ids = self._upload_video_chunked(upload_instructions, video_path)
        if uploaded_part_ids is None:
            return {"success": False, "error": "Failed to upload video"}

        # Finalize the video upload if uploadToken is provided
        # Small files (single-chunk) get uploadToken; large files (multi-chunk) may not
        finalized = False
        if upload_token:
            finalized = self._finalize_video_upload(upload_token, uploaded_part_ids, video_urn)
            if not finalized:
                logger.warning(
                    "Video finalization failed, video may not appear in feed",
                    video_urn=video_urn,
                )
        else:
            # Large multi-part uploads may not receive uploadToken
            # Video might still work but finalization couldn't be confirmed
            logger.info(
                "No uploadToken provided by LinkedIn, skipping finalization",
                video_urn=video_urn,
                file_size_mb=file_size / 1024 / 1024,
            )

        # Wait a moment for video processing to start
        time.sleep(2)

        # Create the post with the video
        escaped_text = escape_little_text(text[:3000]) if text else ""

        payload = {
            "author": self.member_urn,
            "commentary": escaped_text,
            "visibility": visibility.value,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "media": {
                    "id": video_urn,
                    "title": title or "",
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
                logger.info("Created video post", post_urn=post_urn, video_urn=video_urn, finalized=finalized)
                return {
                    "success": True,
                    "post_urn": post_urn,
                    "video_urn": video_urn,
                    "visibility": visibility.value,
                    "file_size_mb": round(file_size / 1024 / 1024, 2),
                    "finalized": finalized,
                    "note": "Video may take a few minutes to process before it appears in the feed.",
                }
            else:
                logger.error(
                    "Failed to create video post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating video post", error=str(e))
            return {"success": False, "error": str(e)}

    def create_document_post(
        self,
        text: str,
        document_path: Path,
        title: Optional[str] = None,
        visibility: PostVisibility = PostVisibility.PUBLIC,
    ) -> Optional[dict[str, Any]]:
        """
        Create a post with a document (PDF, PPTX, DOCX).

        Documents appear as carousel-style slideshows in the LinkedIn feed.
        Great for sharing presentations, guides, reports, etc.

        Supported formats: PDF (recommended), PPTX, DOCX
        Maximum size: 100MB

        Args:
            text: Post text content
            document_path: Path to document file
            title: Optional title for the document
            visibility: Post visibility

        Returns:
            Post data if successful, None otherwise
        """
        document_path = Path(document_path)
        if not document_path.exists():
            return {"success": False, "error": f"Document file not found: {document_path}"}

        # Validate file type
        valid_extensions = {".pdf", ".pptx", ".docx"}
        if document_path.suffix.lower() not in valid_extensions:
            return {
                "success": False,
                "error": f"Invalid document type '{document_path.suffix}'. Supported: PDF, PPTX, DOCX",
            }

        file_size = document_path.stat().st_size

        # LinkedIn limit: 100MB for documents
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            return {
                "success": False,
                "error": f"Document file too large ({file_size / 1024 / 1024:.1f}MB). Maximum is 100MB.",
            }

        # Initialize upload
        upload_data = self._initialize_upload(MediaType.DOCUMENT)
        if not upload_data:
            return {"success": False, "error": "Failed to initialize document upload"}

        upload_url = upload_data.get("uploadUrl")
        document_urn = upload_data.get("document")

        if not upload_url or not document_urn:
            return {"success": False, "error": "Invalid upload response"}

        logger.info(
            "Uploading document",
            path=str(document_path),
            size_mb=file_size / 1024 / 1024,
            document_urn=document_urn,
        )

        # Upload the document
        if not self._upload_media(upload_url, document_path):
            return {"success": False, "error": "Failed to upload document"}

        # Create the post with the document
        escaped_text = escape_little_text(text[:3000]) if text else ""

        # Use the filename as title if not provided
        doc_title = title or document_path.stem.replace("_", " ").replace("-", " ")

        payload = {
            "author": self.member_urn,
            "commentary": escaped_text,
            "visibility": visibility.value,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {
                "media": {
                    "id": document_urn,
                    "title": doc_title,
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
                logger.info("Created document post", post_urn=post_urn, document_urn=document_urn)
                return {
                    "success": True,
                    "post_urn": post_urn,
                    "document_urn": document_urn,
                    "title": doc_title,
                    "visibility": visibility.value,
                    "file_size_mb": round(file_size / 1024 / 1024, 2),
                }
            else:
                logger.error(
                    "Failed to create document post",
                    status=response.status_code,
                    error=response.text[:500],
                )
                return {
                    "success": False,
                    "error": response.text[:500],
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating document post", error=str(e))
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

    def create_comment(
        self,
        post_urn: str,
        text: str,
        parent_comment_urn: Optional[str] = None,
        image_path: Optional[Path] = None,
    ) -> dict[str, Any]:
        """
        Create a comment on a post or reply to an existing comment.

        Args:
            post_urn: The URN of the post to comment on (e.g., "urn:li:share:123" or "urn:li:activity:123")
            text: The comment text content
            parent_comment_urn: Optional URN of parent comment for nested replies
            image_path: Optional path to image file (only supported for nested comments/replies)

        Returns:
            Result dict with success status and comment details

        Note:
            LinkedIn only allows images in nested comments (replies to other comments),
            not in top-level comments directly on posts.
        """
        try:
            # The socialActions API accepts share, ugcPost, or activity URNs directly
            # Do NOT convert between URN types - the IDs are different
            # Path format: /rest/socialActions/{shareUrn|ugcPostUrn|commentUrn}/comments
            social_action_urn = post_urn

            # CRITICAL: For nested replies (when parent_comment_urn is provided),
            # we must use the ACTIVITY URN embedded in the comment URN, not the post URN.
            # Comment URN format: urn:li:comment:(urn:li:activity:XXXXX,YYYYY)
            # We need to extract: urn:li:activity:XXXXX
            if parent_comment_urn and parent_comment_urn.startswith("urn:li:comment:("):
                import re
                # Extract activity URN from comment URN
                match = re.search(r"urn:li:comment:\((urn:li:activity:\d+),", parent_comment_urn)
                if match:
                    activity_urn = match.group(1)
                    logger.info(
                        "Extracted activity URN for nested reply",
                        parent_comment_urn=parent_comment_urn,
                        activity_urn=activity_urn,
                    )
                    social_action_urn = activity_urn
                else:
                    logger.warning(
                        "Could not extract activity URN from parent comment URN",
                        parent_comment_urn=parent_comment_urn,
                    )

            # Validate URN format
            valid_prefixes = ("urn:li:share:", "urn:li:ugcPost:", "urn:li:activity:")
            if not social_action_urn.startswith(valid_prefixes):
                logger.warning("Unexpected URN format for comment", post_urn=social_action_urn)
                # Try to use as-is anyway

            # Handle image upload if provided
            image_urn = None
            if image_path:
                if not parent_comment_urn:
                    logger.warning(
                        "Image provided for top-level comment - LinkedIn only supports images in nested comments"
                    )
                    return {
                        "success": False,
                        "error": "LinkedIn only allows images in nested comments (replies to other comments). "
                        "To add an image, you must reply to an existing comment using parent_comment_urn.",
                    }

                # Upload the image
                logger.info("Uploading image for comment", image_path=str(image_path))
                upload_data = self._initialize_upload(MediaType.IMAGE)
                if not upload_data:
                    return {"success": False, "error": "Failed to initialize image upload for comment"}

                upload_url = upload_data.get("uploadUrl")
                image_urn = upload_data.get("image")

                if not upload_url or not image_urn:
                    return {"success": False, "error": "Invalid upload response for comment image"}

                if not self._upload_media(upload_url, image_path):
                    return {"success": False, "error": "Failed to upload comment image"}

                logger.info("Uploaded comment image", image_urn=image_urn)

            # Build the endpoint URL
            encoded_urn = requests.utils.quote(social_action_urn, safe="")
            endpoint = f"{self.API_BASE}/rest/socialActions/{encoded_urn}/comments"

            # Build the request payload
            payload = {
                "actor": self.member_urn,
                "object": social_action_urn,
                "message": {
                    "text": text[:1250] if text else "",  # LinkedIn comment limit
                },
            }

            # Add parent comment for nested replies
            if parent_comment_urn:
                payload["parentComment"] = parent_comment_urn

            # Add image content if uploaded
            if image_urn:
                payload["content"] = [{"entity": {"image": image_urn}}]

            logger.info(
                "Creating comment",
                post_urn=post_urn,
                endpoint_urn=social_action_urn,
                has_parent=bool(parent_comment_urn),
                has_image=bool(image_urn),
            )

            response = self._session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                comment_id = response.headers.get("x-restli-id", "")
                logger.info("Created comment", comment_id=comment_id, post_urn=post_urn)
                result = {
                    "success": True,
                    "comment_id": comment_id,
                    "post_urn": post_urn,
                    "text": text[:100] + "..." if len(text) > 100 else text,
                }
                if image_urn:
                    result["image_urn"] = image_urn
                return result
            elif response.status_code == 429:
                logger.warning("Comment rate limited", post_urn=post_urn)
                return {
                    "success": False,
                    "error": "Rate limited. LinkedIn limits comment frequency. Please wait a moment and try again.",
                    "status_code": 429,
                }
            elif response.status_code == 403 and image_urn and not parent_comment_urn:
                # This shouldn't happen due to our check above, but handle it anyway
                return {
                    "success": False,
                    "error": "LinkedIn does not allow images in top-level comments. Images are only supported in nested comment replies.",
                    "status_code": 403,
                }
            elif response.status_code == 403:
                error_text = response.text[:500]
                # Check for the specific permission error
                if "partnerApiSocialActions" in error_text or "PERMISSION" in error_text.upper():
                    logger.warning(
                        "Comment permission denied - requires Community Management API",
                        status=response.status_code,
                        post_urn=post_urn,
                    )
                    return {
                        "success": False,
                        "error": "Commenting requires the 'Community Management API' product, not just 'Share on LinkedIn'.",
                        "details": (
                            "The 'Share on LinkedIn' product only allows creating posts. "
                            "To comment on posts, you need to:\n"
                            "1. Go to LinkedIn Developer Portal → Your App → Products\n"
                            "2. Request access to 'Community Management API'\n"
                            "3. LinkedIn will review your application (may take days/weeks)\n"
                            "4. Once approved, commenting will work automatically"
                        ),
                        "status_code": 403,
                        "permission_required": "Community Management API",
                    }
                else:
                    logger.error(
                        "Failed to create comment - 403 Forbidden",
                        status=response.status_code,
                        error=error_text,
                        post_urn=post_urn,
                    )
                    return {
                        "success": False,
                        "error": error_text,
                        "status_code": 403,
                    }
            else:
                error_text = response.text[:500]
                logger.error(
                    "Failed to create comment",
                    status=response.status_code,
                    error=error_text,
                    post_urn=post_urn,
                )
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating comment", error=str(e), post_urn=post_urn)
            return {"success": False, "error": str(e)}

    def get_post_comments(
        self,
        post_urn: str,
        start: int = 0,
        count: int = 50,
    ) -> dict[str, Any]:
        """
        Get comments on a post via the Official LinkedIn API.

        Requires Community Management API access (w_member_social_feed scope).

        Args:
            post_urn: The URN of the post (e.g., "urn:li:share:123" or "urn:li:ugcPost:123")
            start: Pagination start index (default: 0)
            count: Number of comments to return (default: 50, max: 100)

        Returns:
            Dict containing:
                - success: Boolean indicating success
                - comments: List of comment objects with URN, author, text, etc.
                - paging: Pagination info (start, count, total)
                - error: Error message if failed
        """
        try:
            # Use original URN directly - do NOT convert between URN types
            social_action_urn = post_urn

            # Build the endpoint URL with pagination
            encoded_urn = requests.utils.quote(social_action_urn, safe="")
            endpoint = f"{self.API_BASE}/rest/socialActions/{encoded_urn}/comments"

            params = {
                "start": start,
                "count": min(count, 100),  # Cap at 100
            }

            logger.info(
                "Fetching comments via official API",
                post_urn=post_urn,
                start=start,
                count=count,
            )

            response = self._session.get(
                endpoint,
                headers=self._get_headers(),
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])

                # Normalize comments for easier consumption
                comments = []
                for element in elements:
                    # Extract actor info
                    actor_urn = element.get("actor", "")
                    actor_name = None

                    # Try to get actor name from nested object if available
                    actor_obj = element.get("actorInfo", {})
                    if actor_obj:
                        actor_name = actor_obj.get("name")

                    # Extract comment ID and full URN
                    # LinkedIn returns both 'id' (numeric) and 'commentUrn' (full compound URN)
                    # The commentUrn is needed for nested replies
                    comment_id = element.get("id") or element.get("$URN", "")
                    # Use the full commentUrn for replies - format: urn:li:comment:(urn:li:activity:XXX,YYY)
                    comment_urn = element.get("commentUrn", "")
                    if not comment_urn:
                        # Fallback to constructing a simple URN (won't work for nested replies)
                        comment_urn = f"urn:li:comment:{comment_id}" if comment_id else ""

                    # Extract message text
                    message = element.get("message", {})
                    text = message.get("text", "") if isinstance(message, dict) else str(message)

                    # Extract parent comment if this is a reply
                    parent_comment = element.get("parentComment")

                    comment = {
                        "id": comment_id,
                        "urn": comment_urn,  # Full URN for use with create_comment parent_comment_urn
                        "actor_urn": actor_urn,
                        "actor_name": actor_name,
                        "text": text,
                        "parent_comment": parent_comment,
                        "created_at": element.get("createdAt") or element.get("created", {}).get("time"),
                        "content": element.get("content", []),
                        "_raw": element,  # Include raw data for debugging
                    }
                    comments.append(comment)

                logger.info(
                    "Retrieved comments via official API",
                    post_urn=post_urn,
                    comment_count=len(comments),
                )

                return {
                    "success": True,
                    "comments": comments,
                    "paging": data.get("paging", {"start": start, "count": len(comments)}),
                    "total": data.get("paging", {}).get("total", len(comments)),
                }

            elif response.status_code == 403:
                error_text = response.text[:500]
                if "PERMISSION" in error_text.upper() or "partnerApiSocialActions" in error_text:
                    logger.warning(
                        "Comments retrieval requires Community Management API",
                        status=response.status_code,
                    )
                    return {
                        "success": False,
                        "error": "Fetching comments requires the 'Community Management API' product.",
                        "details": "Request access in LinkedIn Developer Portal → Products → Community Management API",
                        "status_code": 403,
                        "comments": [],
                    }
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": 403,
                    "comments": [],
                }

            elif response.status_code == 404:
                logger.warning("Post not found or no comments", post_urn=post_urn)
                return {
                    "success": True,
                    "comments": [],
                    "paging": {"start": start, "count": 0},
                    "total": 0,
                    "message": "Post not found or has no comments",
                }

            else:
                error_text = response.text[:500]
                logger.error(
                    "Failed to fetch comments",
                    status=response.status_code,
                    error=error_text,
                )
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": response.status_code,
                    "comments": [],
                }

        except Exception as e:
            logger.error("Error fetching comments", error=str(e), post_urn=post_urn)
            return {"success": False, "error": str(e), "comments": []}

    def delete_comment(
        self,
        post_urn: str,
        comment_id: str,
    ) -> dict[str, Any]:
        """
        Delete a comment from a post.

        Requires Community Management API access (w_member_social_feed scope).

        Args:
            post_urn: The URN of the post containing the comment
            comment_id: The ID or URN of the comment to delete

        Returns:
            Result dict with success status
        """
        try:
            # Use original URN directly - do NOT convert between URN types
            # The socialActions API accepts share, ugcPost, or activity URNs
            social_action_urn = post_urn

            # Extract comment ID if full URN provided
            # Comment URN format: urn:li:comment:(urn:li:activity:123,456)
            if comment_id.startswith("urn:li:comment:"):
                # Extract just the numeric ID
                import re
                match = re.search(r",(\d+)\)$", comment_id)
                if match:
                    comment_id = match.group(1)
                else:
                    # Try to use as-is
                    pass

            # Build the endpoint URL
            encoded_urn = requests.utils.quote(social_action_urn, safe="")
            endpoint = f"{self.API_BASE}/rest/socialActions/{encoded_urn}/comments/{comment_id}"

            logger.info(
                "Deleting comment",
                post_urn=post_urn,
                comment_id=comment_id,
            )

            response = self._session.delete(
                endpoint,
                headers=self._get_headers(),
            )

            if response.status_code in (200, 204):
                logger.info("Deleted comment", comment_id=comment_id, post_urn=post_urn)
                return {
                    "success": True,
                    "comment_id": comment_id,
                    "post_urn": post_urn,
                }
            elif response.status_code == 403:
                error_text = response.text[:500]
                if "PERMISSION" in error_text.upper() or "partnerApiSocialActions" in error_text:
                    return {
                        "success": False,
                        "error": "Deleting comments requires the 'Community Management API' product.",
                        "details": "Request access in LinkedIn Developer Portal → Products → Community Management API",
                        "status_code": 403,
                    }
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": 403,
                }
            elif response.status_code == 404:
                return {
                    "success": False,
                    "error": "Comment not found",
                    "status_code": 404,
                }
            else:
                error_text = response.text[:500]
                logger.error(
                    "Failed to delete comment",
                    status=response.status_code,
                    error=error_text,
                )
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error deleting comment", error=str(e))
            return {"success": False, "error": str(e)}

    def create_reaction(
        self,
        target_urn: str,
        reaction_type: ReactionType | str = ReactionType.LIKE,
    ) -> dict[str, Any]:
        """
        Add a reaction to a post or comment.

        Requires Community Management API access (w_member_social_feed scope).

        Args:
            target_urn: The URN of the post or comment to react to
                       (e.g., "urn:li:share:123", "urn:li:activity:123",
                        "urn:li:comment:(urn:li:activity:123,456)")
            reaction_type: Type of reaction to add. Options:
                - LIKE (👍 Like)
                - PRAISE (👏 Celebrate)
                - EMPATHY (❤️ Love)
                - INTEREST (💡 Insightful)
                - APPRECIATION (🙏 Support)
                - ENTERTAINMENT (😄 Funny)

        Returns:
            Result dict with success status and reaction details
        """
        try:
            # Normalize reaction type
            if isinstance(reaction_type, str):
                reaction_type = reaction_type.upper()
                # Handle UI names
                reaction_map = {
                    "CELEBRATE": "PRAISE",
                    "LOVE": "EMPATHY",
                    "INSIGHTFUL": "INTEREST",
                    "SUPPORT": "APPRECIATION",
                    "FUNNY": "ENTERTAINMENT",
                }
                reaction_type = reaction_map.get(reaction_type, reaction_type)
            else:
                reaction_type = reaction_type.value

            # Validate reaction type
            valid_reactions = ["LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION", "ENTERTAINMENT"]
            if reaction_type not in valid_reactions:
                return {
                    "success": False,
                    "error": f"Invalid reaction type '{reaction_type}'. Valid types: {', '.join(valid_reactions)}",
                }

            # Use original URN directly - do NOT convert between URN types
            # The reactions API accepts share, ugcPost, activity, or comment URNs
            root_urn = target_urn

            # Build the endpoint - actor parameter is URL-encoded member URN
            encoded_actor = requests.utils.quote(self.member_urn, safe="")
            endpoint = f"{self.API_BASE}/rest/reactions?actor={encoded_actor}"

            # Build payload
            payload = {
                "root": root_urn,
                "reactionType": reaction_type,
            }

            logger.info(
                "Creating reaction",
                target_urn=target_urn,
                root_urn=root_urn,
                reaction_type=reaction_type,
            )

            response = self._session.post(
                endpoint,
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code == 201:
                # Parse the response for the reaction ID
                try:
                    result_data = response.json()
                    reaction_id = result_data.get("id", "")
                except Exception:
                    reaction_id = response.headers.get("x-restli-id", "")

                logger.info(
                    "Created reaction",
                    reaction_id=reaction_id,
                    reaction_type=reaction_type,
                    target_urn=target_urn,
                )
                return {
                    "success": True,
                    "reaction_id": reaction_id,
                    "reaction_type": reaction_type,
                    "target_urn": target_urn,
                }
            elif response.status_code == 409:
                # Already reacted - this is technically success
                logger.info("Already reacted to this content", target_urn=target_urn)
                return {
                    "success": True,
                    "already_reacted": True,
                    "reaction_type": reaction_type,
                    "target_urn": target_urn,
                }
            elif response.status_code == 403:
                error_text = response.text[:500]
                if "PERMISSION" in error_text.upper() or "w_member_social_feed" in error_text:
                    return {
                        "success": False,
                        "error": "Reactions require the 'Community Management API' product (w_member_social_feed scope).",
                        "details": "Request access in LinkedIn Developer Portal → Products → Community Management API",
                        "status_code": 403,
                    }
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": 403,
                }
            elif response.status_code == 400:
                error_text = response.text[:500]
                if "MAYBE" in error_text:
                    return {
                        "success": False,
                        "error": "The MAYBE reaction type is deprecated. Use LIKE, PRAISE, EMPATHY, INTEREST, APPRECIATION, or ENTERTAINMENT.",
                        "status_code": 400,
                    }
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": 400,
                }
            else:
                error_text = response.text[:500]
                logger.error(
                    "Failed to create reaction",
                    status=response.status_code,
                    error=error_text,
                )
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error creating reaction", error=str(e))
            return {"success": False, "error": str(e)}

    def delete_reaction(
        self,
        target_urn: str,
    ) -> dict[str, Any]:
        """
        Remove a reaction from a post or comment.

        Requires Community Management API access (w_member_social_feed scope).

        Args:
            target_urn: The URN of the post or comment to remove the reaction from
                       (e.g., "urn:li:share:123", "urn:li:activity:123")

        Returns:
            Result dict with success status
        """
        try:
            # Use original URN directly - do NOT convert between URN types
            # The reactions API accepts share, ugcPost, activity, or comment URNs
            root_urn = target_urn

            # Build the reaction key for deletion
            # LinkedIn REST API uses compound keys with special encoding
            # Format: (actor:{encoded_actor},entity:{encoded_entity})
            encoded_actor = requests.utils.quote(self.member_urn, safe="")
            encoded_entity = requests.utils.quote(root_urn, safe="")

            # Use the compound key format for REST API
            compound_key = f"(actor:{encoded_actor},entity:{encoded_entity})"

            endpoint = f"{self.API_BASE}/rest/reactions/{compound_key}"

            logger.info(
                "Deleting reaction",
                target_urn=target_urn,
                compound_key=compound_key,
            )

            response = self._session.delete(
                endpoint,
                headers=self._get_headers(),
            )

            if response.status_code in (200, 204):
                logger.info("Deleted reaction", target_urn=target_urn)
                return {
                    "success": True,
                    "target_urn": target_urn,
                }
            elif response.status_code == 404:
                # No reaction to delete - still success
                return {
                    "success": True,
                    "no_reaction": True,
                    "target_urn": target_urn,
                }
            elif response.status_code == 403:
                error_text = response.text[:500]
                if "PERMISSION" in error_text.upper():
                    return {
                        "success": False,
                        "error": "Deleting reactions requires the 'Community Management API' product.",
                        "status_code": 403,
                    }
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": 403,
                }
            else:
                error_text = response.text[:500]
                logger.error(
                    "Failed to delete reaction",
                    status=response.status_code,
                    error=error_text,
                )
                return {
                    "success": False,
                    "error": error_text,
                    "status_code": response.status_code,
                }

        except Exception as e:
            logger.error("Error deleting reaction", error=str(e))
            return {"success": False, "error": str(e)}

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
                "create_video_post",
                "create_document_post",
                "create_poll",
                "create_comment",
                "delete_comment",
                "create_reaction",
                "delete_reaction",
                "delete_post",
                "get_post",
            ],
            "required_scopes": {
                "posts": "w_member_social",
                "comments_reactions": "w_member_social_feed",
            },
            "required_products": {
                "posts": "Share on LinkedIn",
                "comments_reactions": "Community Management API",
            },
        }
