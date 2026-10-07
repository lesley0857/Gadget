# Automatic LinkedIn blog publishing

When a published blog post is saved, the site creates one public LinkedIn post linking to that article. Edits to a successfully posted article do not create duplicates. A draft is shared when saved as published. Failed attempts appear on the blog post in Django admin; saving it again retries.

Set these deployment environment variables:

- LINKEDIN_ACCESS_TOKEN: OAuth access token for an approved LinkedIn app.
- LINKEDIN_AUTHOR_URN: urn:li:organization:<id> for a company page, or urn:li:person:<id> for a member.
- PUBLIC_SITE_URL: public site origin, such as https://example.com (without a trailing slash).
- LINKEDIN_API_VERSION: optional YYYYMM API version; code defaults to 202610.

The token needs w_organization_social for organization posts or w_member_social for member posts, and the LinkedIn app and author must have the needed access. Apply migration blog.0003_blogpost_linkedin_publishing after deploying.

After correcting credentials or permissions, save a failed blog post again to retry.
