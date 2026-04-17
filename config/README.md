# Configuration Files

This directory contains configuration files for VAST-Automation and other services.

## Files

### `google_client_secret.example.json`
**Template for Google OAuth 2.0 credentials**
- Download from: https://console.cloud.google.com/apis/credentials
- Copy to: `google_client_secret.json` (ignored by git)
- Never commit the actual credentials file

### `google_client_secret.json`
**Actual Google OAuth credentials (NOT committed)**
- Used by GoogleDriveService for OAuth 2.0 authentication
- Download from Google Cloud Console
- Permissions: 644 (readable by app)
- Protected by `.gitignore`

## Setup

1. Go to https://console.cloud.google.com/apis/credentials
2. Create "Desktop application" OAuth 2.0 credentials
3. Download JSON file
4. Save as `google_client_secret.json` in this directory
5. Verify: `cat google_client_secret.json | head -5`

## Security

✅ **What's protected:**
- `.gitignore` prevents accidental commits
- Credentials never appear in git history
- Only developers with repo access can see it

⚠️ **What's your responsibility:**
- Don't commit `google_client_secret.json`
- Don't share credentials file
- Use .gitignore if you add more secrets

## Format

```json
{
  "installed": {
    "client_id": "XXX.apps.googleusercontent.com",
    "project_id": "your-project",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_SECRET",
    "redirect_uris": ["http://localhost"]
  }
}
```

## Token Location

Once authenticated, tokens are saved to:
```
~/.agata/google_drive_token.json
```

This is NOT in the repo and is regenerated per-machine/per-user.

---

See `VAST_OAUTH_SETUP.md` for complete setup guide.
