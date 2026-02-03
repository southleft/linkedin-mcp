# LinkedIn Content Intelligence Platform — Capabilities

> For Claude Code and Claude Desktop

```
╔══════════════════════════════════════════════════════════════════════════════════════════╗
║  LinkedIn Content Intelligence Platform — For Claude Code and Claude Desktop             ║
╠════════════════════╦═══════════════════════════════════╦═════════════════════════════════╣
║ Category           ║ Tool                              ║ What It Does                    ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ PROFILES           ║ get_my_profile                    ║ Your own profile data           ║
║                    ║ get_profile                       ║ Fetch full profile by ID or URN ║
║                    ║ get_profile_contact_info          ║ Email, phone, websites, Twitter ║
║                    ║ get_profile_skills                ║ Skills with endorsement counts  ║
║                    ║ get_profile_interests             ║ Who/what a person follows       ║
║                    ║ get_similar_profiles              ║ Find similar profiles           ║
║                    ║ get_profile_articles              ║ Articles written by profile     ║
║                    ║ get_profile_views                 ║ Your profile view stats         ║
║                    ║ get_network_stats                 ║ Connection & follower counts    ║
║                    ║ batch_get_profiles                ║ Fetch multiple profiles at once ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ PROFILE EDITING    ║ update_profile_headline           ║ Update your headline            ║
║                    ║ update_profile_summary            ║ Update your about section       ║
║                    ║ upload_profile_photo              ║ Upload profile picture          ║
║                    ║ upload_background_photo           ║ Upload banner image             ║
║                    ║ add_profile_skill                 ║ Add a skill to your profile     ║
║                    ║ get_profile_completeness          ║ Profile completeness score      ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ COMPANIES          ║ get_company                       ║ Company profile, industry, size ║
║                    ║ get_company_by_domain             ║ Look up company by website      ║
║                    ║ get_company_updates               ║ Company posts and updates       ║
║                    ║ get_organization_followers        ║ Follower count                  ║
║                    ║ get_school                        ║ University/school profiles      ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ SEARCH             ║ search_people                     ║ Find people by keywords, title  ║
║                    ║ search_companies                  ║ Find companies by keyword       ║
║                    ║ search_jobs                       ║ Jobs with filters (remote, exp) ║
║                    ║ search_ads                        ║ Search LinkedIn ads             ║
║                    ║ search_ads_by_advertiser          ║ Find ads by company             ║
║                    ║ search_ads_by_keyword             ║ Find ads by keyword             ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ JOBS               ║ search_jobs                       ║ Search job postings             ║
║                    ║ get_job                           ║ Detailed job information        ║
║                    ║ get_job_skills                    ║ Required skills for a job       ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ MESSAGING          ║ get_conversations                 ║ List all your conversations     ║
║                    ║ get_conversation                  ║ Full message history            ║
║                    ║ get_conversation_details          ║ Get conversation ID for profile ║
║                    ║ send_message                      ║ Send message to connections     ║
║                    ║ mark_conversation_as_seen         ║ Mark messages as read           ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ CONNECTIONS        ║ get_invitations                   ║ Pending connection requests     ║
║                    ║ send_connection_request           ║ Connect with optional note      ║
║                    ║ reply_invitation                  ║ Accept or ignore invitations    ║
║                    ║ remove_connection                 ║ Remove existing connection      ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ CONTENT CREATION   ║ create_post                       ║ Publish text posts              ║
║                    ║ create_image_post                 ║ Post with images                ║
║                    ║ create_video_post                 ║ Post with video                 ║
║                    ║ create_document_post              ║ Post with PDF/documents         ║
║                    ║ create_poll                       ║ Create interactive polls        ║
║                    ║ edit_post                         ║ Edit existing posts             ║
║                    ║ delete_post                       ║ Remove a published post         ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ ENGAGEMENT         ║ create_comment                    ║ Comment on posts                ║
║                    ║ delete_comment                    ║ Remove your comments            ║
║                    ║ create_reaction                   ║ React to posts (like, etc.)     ║
║                    ║ delete_reaction                   ║ Remove your reaction            ║
║                    ║ get_post_reactions                ║ See who reacted to a post       ║
║                    ║ get_post_comments                 ║ Get comments on a post          ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ DRAFTS             ║ create_draft                      ║ Save content for later          ║
║                    ║ list_drafts                       ║ View all saved drafts           ║
║                    ║ get_draft                         ║ Get a specific draft            ║
║                    ║ update_draft                      ║ Edit a draft                    ║
║                    ║ delete_draft                      ║ Remove a draft                  ║
║                    ║ publish_draft                     ║ Publish a saved draft           ║
║                    ║ analyze_draft_content             ║ Get AI improvement suggestions  ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ SCHEDULING         ║ schedule_post                     ║ Schedule for future posting     ║
║                    ║ list_scheduled_posts              ║ View all scheduled posts        ║
║                    ║ get_scheduled_post                ║ Get schedule details            ║
║                    ║ update_scheduled_post             ║ Modify scheduled post           ║
║                    ║ cancel_scheduled_post             ║ Cancel a scheduled post         ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ ANALYTICS          ║ get_feed                          ║ Your LinkedIn feed              ║
║                    ║ get_profile_posts                 ║ Posts from any profile          ║
║                    ║ get_post_analytics                ║ Impressions, clicks, engagement ║
║                    ║ analyze_engagement                ║ Deep engagement analysis        ║
║                    ║ analyze_content_performance       ║ Content pattern analysis        ║
║                    ║ analyze_optimal_posting_times     ║ Best times to post              ║
║                    ║ analyze_post_audience             ║ Post audience breakdown         ║
║                    ║ analyze_hashtag_performance       ║ Hashtag effectiveness           ║
║                    ║ generate_engagement_report        ║ Full engagement report          ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ CONTENT            ║ get_my_posts                      ║ Your published posts            ║
║ INTELLIGENCE       ║ get_my_post_analytics             ║ Analytics for your posts        ║
║                    ║ analyze_my_content_performance    ║ Your content patterns           ║
║                    ║ get_my_posting_recommendations    ║ Personalized recommendations    ║
║                    ║ generate_my_content_calendar      ║ AI-generated content calendar   ║
╠════════════════════╬═══════════════════════════════════╬═════════════════════════════════╣
║ DIAGNOSTICS        ║ get_auth_status                   ║ Check authentication status     ║
║                    ║ get_rate_limit_status             ║ Monitor API usage               ║
║                    ║ debug_context                     ║ Check server internal state     ║
║                    ║ get_cache_stats                   ║ Cache statistics                ║
║                    ║ check_browser_automation_status   ║ Browser fallback status         ║
╚════════════════════╩═══════════════════════════════════╩═════════════════════════════════╝
```

## Platform Features

| Feature | Description |
|---------|-------------|
| **OAuth 2.0 Authentication** | Secure official API access for posting and analytics |
| **Cookie Authentication** | Unofficial API access for extended features |
| **Multi-Source Fallback** | Automatic failover through 5 data sources |
| **Profile Caching** | 7-day cache for improved performance |
| **Rate Limiting** | Built-in protection against API limits |
| **Browser Automation** | Playwright fallback for enhanced reliability |
| **11 Browser Support** | Cookie extraction from Chrome, Arc, Brave, Edge, Firefox, Opera, Opera GX, Vivaldi, Chromium, Safari, LibreWolf |

## Tool Count by Category

| Category | Tools |
|----------|-------|
| Profiles | 10 |
| Profile Editing | 6 |
| Companies | 5 |
| Search | 6 |
| Jobs | 3 |
| Messaging | 5 |
| Connections | 4 |
| Content Creation | 7 |
| Engagement | 6 |
| Drafts | 7 |
| Scheduling | 5 |
| Analytics | 9 |
| Content Intelligence | 5 |
| Diagnostics | 5 |
| **Total** | **83** |

## Authentication Requirements

| Feature Set | OAuth 2.0 | Cookies | Notes |
|-------------|-----------|---------|-------|
| Post Creation | Required | - | Official API |
| Post Analytics | Required | - | Official API |
| Comments/Reactions | Required | - | Community Management API |
| Profile Research | - | Required | Unofficial API |
| Messaging | - | Required | Unofficial API |
| Connections | - | Required | Unofficial API |
| Job Search | - | Required | Unofficial API |
| Company Research | - | Required | Unofficial API |

## Data Source Priority

The platform automatically selects the best available data source:

| Priority | Source | Reliability | Speed |
|----------|--------|-------------|-------|
| 1 | Professional Network Data API | Highest | Fast |
| 2 | Fresh LinkedIn Data API | High | Fast |
| 3 | Marketing API | High (official) | Fast |
| 4 | Enhanced HTTP Client | Medium | Medium |
| 5 | Headless Browser | Medium | Slow |
| 6 | Unofficial API (linkedin-api) | Variable | Fast |
