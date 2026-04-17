# VAST-Automation OAuth 2.0 Setup Guide

## Overview

VAST-Automation now uses **OAuth 2.0 Device Flow** instead of service account JSON. This is more secure and functional.

## Setup Steps

### Step 1: Create OAuth 2.0 Credentials on Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials
2. Create new OAuth 2.0 Client ID:
   - **Application Type**: `Desktop application`
   - **Name**: `VAST-Automation`
3. Click "Create"
4. Download JSON file (button "Download OAuth 2.0 Credentials")

### Step 2: Copy Credentials File into Project

```bash
# Download JSON from Google Cloud Console
# Then copy to project directory:

cp ~/Downloads/client_secret.json ./config/google_client_secret.json

# Verify:
ls -l ./config/google_client_secret.json

# .env already configured:
cat .env | grep GOOGLE_CLIENT_SECRET_FILE
# Output: GOOGLE_CLIENT_SECRET_FILE=./config/google_client_secret.json
```

**Why in project?**
- ✅ Always available (not tied to /dati/ or external filesystem)
- ✅ Version controlled (git tracks if it changes)
- ✅ Easy to backup/migrate
- ✅ Docker-friendly (include in image)

**Security:**
- ✅ `.gitignore` prevents accidental commit
- ✅ Only developers with repo access can see it

### Step 3: Initialize OAuth Token (First Run Only)

This step will open a browser for you to authorize VAST-Automation:

```bash
cd /var/www/astrogen

# Start Flask with context
python << 'EOF'
from agata.admin.services.google_drive_service import GoogleDriveService

print("🔐 Initializing Google Drive OAuth...")
print("   A browser window will open. Please authorize VAST-Automation.")
print("")

try:
    service = GoogleDriveService()
    print("✅ OAuth initialization successful!")
    print(f"   Token saved to: ~/.agata/google_drive_token.json")
except Exception as e:
    print(f"❌ OAuth initialization failed: {e}")
    print("")
    print("Troubleshooting:")
    print("  1. Check ./config/google_client_secret.json exists and is valid")
    print("  2. Ensure you have a browser available")
    print("  3. Check internet connection")
EOF
```

**What happens:**
1. Browser opens automatically
2. Google login page appears
3. Select your account and grant permission to "VAST-Automation"
4. Authorization granted
5. Token saved to `~/.agata/google_drive_token.json`

### Step 4: Verify Setup

```bash
# Token should exist
ls -l ~/.agata/google_drive_token.json

# Test Drive connection
python << 'EOF'
from agata.admin.services.google_drive_service import GoogleDriveService

service = GoogleDriveService()
print("✅ Google Drive connection successful!")
EOF
```

### Step 5: Start Using VAST

```bash
python -m flask run
# Visit: /agata/admin/vast
```

---

## How It Works

### First Run (Setup)
```
user → clicks UI
     → VastService initializes
     → GoogleDriveService loads
     → No token found
     → OAuth flow starts
     → Browser opens
     → User authorizes
     → Token saved to ~/.agata/google_drive_token.json
     → Service ready
```

### Subsequent Runs
```
user → clicks UI
     → VastService initializes
     → GoogleDriveService loads
     → Token found and loaded
     → Token valid? Yes → Use it
     → Token expired? Refresh automatically
     → Ready to use
```

---

## Security

### What's Secure About This Approach

✅ **No hardcoded credentials** - No password in code or .env
✅ **Limited scope** - Only access to Google Drive
✅ **User consent** - User explicitly authorizes
✅ **Token encryption** - Token saved with 600 permissions (user-only read)
✅ **Auto-refresh** - Token refreshes automatically when expired
✅ **Revocable** - User can revoke access anytime

### What Gets Stored

```
~/.agata/google_drive_token.json   (permissions 600 - user-only)
├── access_token (expires in 1 hour)
├── refresh_token (doesn't expire)
└── Other metadata

client_secret.json (permissions 644)
└── OAuth app credentials (similar to old service account, but safer)
```

---

## Troubleshooting

### Issue: "Google client secret JSON not found"

```
FileNotFoundError: Google client secret JSON not found: /dati/codice/pythonvast/client_secret.json
```

**Fix:**
1. Download from Google Cloud Console
2. Save to correct path
3. Restart app

### Issue: Browser doesn't open during OAuth

**Cause:** Running Flask on headless server (no display)

**Fix:** Use alternative authorization method
```bash
python << 'EOF'
from google_auth_oauthlib.flow import InstalledAppFlow
import os

client_secret_file = '/dati/codice/pythonvast/client_secret.json'
flow = InstalledAppFlow.from_client_secrets_file(
    client_secret_file,
    ['https://www.googleapis.com/auth/drive']
)

# Headless mode - generates URL you can open manually
creds = flow.run_console()

print(f"✅ Visit this URL in your browser:")
print(f"   (URL will be printed if running headless)")
EOF
```

### Issue: Token expired?

**No action needed.** Token auto-refreshes automatically when expired.

If manual refresh needed:
```bash
rm ~/.agata/google_drive_token.json
# Next use will re-authenticate
```

### Issue: "Authorization required" after setup

**Fix:**
```bash
# Clear token and re-authenticate
rm ~/.agata/google_drive_token.json

# Restart Flask and re-run OAuth setup
python -m flask run
# Visit /agata/admin/vast
```

---

## Differences from Old Setup

| Feature | Old (Service Account) | New (OAuth) |
|---------|---------------------|------------|
| **Credentials** | JSON service account | OAuth client secret |
| **Auth method** | Service account key | User OAuth flow |
| **Browser required** | No | Yes (only first time) |
| **Token refresh** | Manual | Automatic |
| **Revocation** | Via GCP console | Via Google account |
| **Security** | Static credentials | Dynamic, user-approved |
| **Dependencies** | pydrive2, oauth2client | google-auth-oauthlib, google-api-python-client |

---

## FAQ

**Q: Do I need to re-authenticate every time?**
A: No. Token is cached and reused. Only first run requires authentication.

**Q: Can multiple users share the same token?**
A: The token is per-machine (~/.agata/). Works for single-user or headless servers.

**Q: What if I want multiple Google accounts?**
A: Currently one token per machine. Could extend to support multiple accounts with naming (e.g., `google_drive_token_account1.json`).

**Q: What if token is compromised?**
A: Visit myaccount.google.com/security → Revoke "VAST-Automation" access. No new token can be created without re-authorizing.

**Q: How long do tokens last?**
A: Access tokens: 1 hour. Refresh tokens: Until revoked (can be years).

---

## Setup Summary

```bash
# 1. Download client_secret.json from Google Cloud Console
#    https://console.cloud.google.com/apis/credentials

# 2. Copy into project:
cp ~/Downloads/client_secret.json ./config/google_client_secret.json

# 3. Verify:
cat ./config/google_client_secret.json | head -5

# 4. Start Flask:
python -m flask run

# 5. Visit and authenticate:
# https://localhost:5000/agata/admin/vast

# 6. Token saved automatically:
ls ~/.agata/google_drive_token.json
```

---

## Dependencies

Updated in requirements.txt:

```
# Old (removed)
pydrive2==1.15.3
gspread==5.12.0
oauth2client==4.1.3

# New (added)
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
google-api-python-client==2.105.0
```

Install:
```bash
pip install -r requirements.txt
```

---

## Next Steps

1. Download client_secret.json from Google Cloud Console
2. Save to `/dati/codice/pythonvast/client_secret.json`
3. Verify .env has `GOOGLE_CLIENT_SECRET_FILE` set
4. Run Flask app
5. Visit `/agata/admin/vast`
6. Follow OAuth flow in browser
7. Done! Token saved for future use

---

**Last Updated**: 2026-02-06
**Status**: OAuth 2.0 Implementation Complete
