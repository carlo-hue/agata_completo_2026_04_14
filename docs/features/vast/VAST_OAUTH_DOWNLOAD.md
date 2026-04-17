# Download Google OAuth Credentials from Google Cloud Console

## Quick Steps

### 1. Go to Google Cloud Console
https://console.cloud.google.com/apis/credentials

### 2. Find Your Existing OAuth Credentials

Look for:
- **Application name**: `VAST-Automation` or similar
- **Application type**: `Desktop application` (or `OAuth 2.0 Client ID`)
- **Status**: Usually shows a green checkmark

### 3. Download the JSON

**Option A: Download from existing credential**
1. Click on the credential row (shows as a gear icon or app name)
2. Click the **"Download JSON"** button (top right area)
3. Save file

**Option B: Create new if none exists**
1. Click **"+ Create Credentials"** → **"OAuth 2.0 Client ID"**
2. Choose **"Desktop application"**
3. Name it: `VAST-Automation`
4. Click **"Create"**
5. Download JSON immediately

### 4. Copy to Your AGATA Project

```bash
cd /var/www/astrogen

# Copy the downloaded file
cp ~/Downloads/client_secret.json ./config/google_client_secret.json

# Verify it worked
cat ./config/google_client_secret.json | jq . | head -20
```

Expected output (should have these fields):
```json
{
  "installed": {
    "client_id": "XXX.apps.googleusercontent.com",
    "project_id": "your-project-id",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_secret": "GOCSPX-...",
    ...
  }
}
```

### 5. Verify Permission Scopes

In Google Cloud Console, check that your OAuth credential has these scopes:
- ✅ `https://www.googleapis.com/auth/drive` (Google Drive)
- ✅ Or broader scope like `https://www.googleapis.com/auth/drive.readonly` (if read-only)

If you need to add scopes:
1. Go to **APIs & Services** → **OAuth consent screen**
2. Click **"Edit"** on your app
3. Add scopes: Search for "Drive" and select `drive`
4. Save

### 6. Test the Connection

```bash
cd /var/www/astrogen

python << 'EOF'
from pathlib import Path
import json

# Verify file exists and is valid JSON
cred_file = Path('./config/google_client_secret.json')

if not cred_file.exists():
    print("❌ File not found at ./config/google_client_secret.json")
else:
    try:
        with open(cred_file) as f:
            data = json.load(f)

        print("✅ Credentials file is valid!")
        print(f"   Project ID: {data['installed']['project_id']}")
        print(f"   Client ID: {data['installed']['client_id']}")
        print("")
        print("Ready for OAuth setup!")

    except json.JSONDecodeError:
        print("❌ File is not valid JSON")
    except KeyError as e:
        print(f"❌ Missing required field: {e}")
EOF
```

### 7. Now Initialize OAuth

Once file is in place, initialize the OAuth token:

```bash
python << 'EOF'
from agata.admin.services.google_drive_service import GoogleDriveService

print("🔐 Initializing Google Drive OAuth...")
print("   A browser window will open.")
print("   Please authorize VAST-Automation to access Google Drive.")
print("")

try:
    service = GoogleDriveService()
    print("✅ Success!")
    print("   OAuth token saved to: ~/.agata/google_drive_token.json")
    print("")
    print("You can now use VAST-Automation to access Google Drive.")

except Exception as e:
    print(f"❌ Error: {e}")
    print("")
    print("Troubleshooting:")
    print("  1. Is ./config/google_client_secret.json readable?")
    print("  2. Is it valid JSON?")
    print("  3. Do you have internet connection?")
    print("  4. Is a browser available?")
EOF
```

---

## File Location Map

```
Google Cloud Console
        ↓
    Download JSON
        ↓
~/Downloads/client_secret.json
        ↓
    (copy command)
        ↓
./config/google_client_secret.json  ← HERE (in project)
        ↓
    (first Flask run)
        ↓
~/.agata/google_drive_token.json   ← Token (per-machine)
```

---

## Common Issues

### Issue: "File not found" or "Can't download"

**Solution:**
```bash
# Check what credentials exist in console
# https://console.cloud.google.com/apis/credentials

# Look for:
# - "OAuth 2.0 Client IDs" section
# - Application type: "Desktop application"

# If none exist, create one:
# 1. Click "+ Create Credentials"
# 2. Select "OAuth 2.0 Client ID"
# 3. Choose "Desktop application"
# 4. Click "Create"
# 5. Download JSON
```

### Issue: "Downloaded file is empty or has wrong format"

**Solution:**
```bash
# Verify the file
file ~/Downloads/client_secret.json
# Should say: JSON data

# Check content
head ~/Downloads/client_secret.json
# Should show JSON structure with "installed" key
```

### Issue: "JSON is valid but OAuth fails"

**Solution:**
1. Check scopes are set in Google Cloud Console
2. Verify client ID hasn't been regenerated
3. Try downloading a fresh copy from console

---

## Next Steps After Download

```bash
# 1. File in place
ls -l ./config/google_client_secret.json

# 2. Start Flask
python -m flask run

# 3. Open browser
# http://localhost:5000/agata/admin/vast

# 4. Create first VAST job
# → Browser redirects to Google login
# → Authorize
# → Token saved
# → Ready to use!
```

---

## Security Reminders

✅ **Do:**
- Keep file in `./config/` (already in .gitignore)
- Download only when needed
- Use from your existing GCP project

❌ **Don't:**
- Commit `google_client_secret.json` to git
- Share the file with others
- Paste credentials in slack/email

---

**Status**: Ready to download and integrate credentials!

See: https://console.cloud.google.com/apis/credentials
