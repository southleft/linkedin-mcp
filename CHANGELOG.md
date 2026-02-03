# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-03

### Added

#### Messaging Tools
- `get_conversations` - List all messaging conversations with pagination
- `get_conversation` - Get messages from a specific conversation
- `get_conversation_details` - Get conversation ID for a profile (to start messaging)
- `send_message` - Send direct messages to connections
- `mark_conversation_as_seen` - Mark conversations as read

#### Connection Management Tools
- `get_invitations` - View pending connection requests (received)
- `send_connection_request` - Send connection requests with optional message
- `reply_invitation` - Accept or reject connection invitations
- `remove_connection` - Remove existing connections

#### Job Search Tools
- `search_jobs` - Search LinkedIn job postings with filters (keywords, location, remote, experience level, job type)
- `get_job` - Get detailed job posting information
- `get_job_skills` - Get required skills for a job posting

#### Profile Analytics
- `get_profile_views` - Get profile view statistics for authenticated user

### Changed

#### Cookie Extraction Improvements
- Changed default browser from Firefox to Chrome for cookie extraction
- Added support for 6 additional browsers: Arc, Brave, Opera, Opera GX, Vivaldi, Safari
- Now supports 11 browsers total: Chrome, Arc, Brave, Edge, Firefox, Opera, Opera GX, Vivaldi, Chromium, Safari, LibreWolf
- Fixed JSESSIONID cookie extraction by checking multiple LinkedIn domains (`.linkedin.com` and `.www.linkedin.com`)
- Added fallback to scan all LinkedIn cookies when domain-specific extraction fails

#### Feature Flags
- Added `messaging_enabled` flag (default: true) - Enable/disable messaging tools
- Added `connections_enabled` flag (default: true) - Enable/disable connection tools
- Added `jobs_enabled` flag (default: true) - Enable/disable job search tools
- Feature flags allow granular control over unofficial API features

#### Authentication Status
- `get_auth_status` now shows enabled feature flags status

### Fixed
- Fixed `get_invitations` to use correct linkedin-api parameter signature (`start`, `limit` only)

## [0.1.0] - 2024-12-01

### Added
- Initial release
- Content creation tools (posts, images, polls, comments)
- Draft management system
- Post scheduling with timezone support
- Profile and company research tools
- Analytics and engagement tracking
- Multi-source profile enrichment with fallback chain
- OAuth 2.0 authentication for official API
- Cookie-based authentication for unofficial API
- Browser automation fallback with Playwright
- Secure credential storage in system keychain
