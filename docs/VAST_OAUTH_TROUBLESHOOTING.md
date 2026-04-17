# VAST OAuth Folder Access Troubleshooting

**Issue**: The folder dropdown shows "No folders found" even though the folder exists.

**Status**: OAuth authentication works, but folder listing returns empty results.

---

## Diagnostic Steps

### 1. Run the Diagnostic Script

First, test folder access with our diagnostic script:

```bash
python scripts/test_vast_folder_access.py
```

This will check:
- ✅ .env configuration (VAST_DRIVE_FOLDER_ID set)
- ✅ OAuth credentials file exists and is valid
- ✅ OAuth authentication works
- ✅ Folder is accessible
- ✅ Subfolders can be listed

---

## Possible Issues & Solutions

### Issue 1: "Folder is Empty" or "No Subfolders Found"

**Symptoms**:
- Diagnostic script says folder exists but no subfolders
- Folder ID 1vhsDXOHMH1ruOICY6Sp3ljTTFxLiptVs is correct in Google Drive

**Cause**: The OAuth-authenticated user might not have access to the Shared Drive.

**Solution**:

#### For Shared Drives (Team Drives):

If the folder is on a **Shared Drive** (not just a personal shared folder):

1. **Check if Shared Drive**: Open folder in Google Drive → Look at the icon
   - 🗂️ Regular folder = Personal Drive
   - 🏢 Icon with multiple people = Shared Drive (Team Drive)

2. **Add OAuth User as Member**:
   - Go to Google Drive
   - Right-click the Shared Drive folder
   - Select "Share"
   - Add the Google account email used for OAuth authentication
   - Give "Viewer" or "Editor" role
   - Share it

3. **Regenerate OAuth Token** (important!):
   ```bash
   rm -f ~/.agata/google_drive_token.json
   python scripts/verify_oauth_credentials.py
   ```
   - Browser will open for re-authorization
   - You may see new scopes to approve (including Shared Drive access)
   - Click "Allow"

#### For Personal Shared Folders:

If the folder is shared but on your personal Drive:

1. Verify you have access
2. Regenerate OAuth token (step 3 above)

---

### Issue 2: "OAuth Token Doesn't Have Permission to List Shared Drive Items"

**Symptoms**:
- Diagnostic script says folder exists but fails when listing subfolders
- Error mentions "Shared Drive" or "Team Drive"

**Cause**: OAuth token was created before you were added to the Shared Drive.

**Solution**:

1. **Ensure you're a member of the Shared Drive**:
   - https://drive.google.com
   - Look for "Shared Drives" in left sidebar
   - You should see the drive listed there

2. **Regenerate OAuth token**:
   ```bash
   # Remove old token
   rm -f ~/.agata/google_drive_token.json

   # Regenerate with new permissions
   python scripts/verify_oauth_credentials.py
   ```

3. **Approve additional scopes** when browser opens:
   - You may see scopes related to "Shared Drives" or "Team Drives"
   - Click "Allow" to grant permissions

---

### Issue 3: "Client Secret Doesn't Have Correct Scopes"

**Symptoms**:
- OAuth authentication works
- But consistently fails when accessing Shared Drive

**Cause**: OAuth 2.0 credentials weren't configured with Shared Drive scope.

**Solution**:

1. **Go to Google Cloud Console**:
   - https://console.cloud.google.com/apis/credentials

2. **Check OAuth Application**:
   - Find your "Desktop application" credentials
   - Note the "Client ID" and "Client Secret"

3. **Regenerate Credentials** (if needed):
   - Delete old credentials
   - Create new "Desktop application" OAuth 2.0 credentials
   - Download and save to `./config/google_client_secret.json`

4. **Ensure Google Drive API is enabled**:
   - https://console.cloud.google.com/apis/library/drive.googleapis.com
   - Click "Enable"

5. **Regenerate OAuth token**:
   ```bash
   rm -f ~/.agata/google_drive_token.json
   python scripts/verify_oauth_credentials.py
   ```

---

## Step-by-Step Workflow

### If You're Not Sure What's Wrong:

1. **Run diagnostic**:
   ```bash
   python scripts/test_vast_folder_access.py
   ```

2. **If diagnostic says "No subfolders found"**:
   - Make sure you're a member of the Shared Drive:
     - Go to https://drive.google.com
     - Look for "Shared Drives" in sidebar
     - If you don't see the drive, ask the Shared Drive owner to add you

3. **Regenerate OAuth token**:
   ```bash
   rm -f ~/.agata/google_drive_token.json
   python scripts/verify_oauth_credentials.py
   ```
   - Approve all permission requests

4. **Run diagnostic again**:
   ```bash
   python scripts/test_vast_folder_access.py
   ```

5. **If still failing**: Post the diagnostic output - it will help identify the exact issue

---

## Important: Shared Drive vs. Personal Shared Folder

### Shared Drive (Team Drive) 🏢
- Appears in "Shared Drives" section in Google Drive
- Has organizational structure and team access
- You must be explicitly added as a member
- OAuth needs special permissions to access

### Personal Shared Folder 🗂️
- Regular folder in your personal Drive
- You share it directly with other people
- They see it in "Shared with me"
- Standard OAuth permissions usually work

**How to tell which you have**:
1. Go to https://drive.google.com
2. Look at the folder ID: `1vhsDXOHMH1ruOICY6Sp3ljTTFxLiptVs`
3. Check if it's under "Shared Drives" or "My Drive"

---

## Reference

### OAuth Scopes in Use

```python
SCOPES = ['https://www.googleapis.com/auth/drive']
```

This scope includes:
- ✅ Personal Drive (My Drive) access
- ✅ Shared folders in personal Drive
- ✅ Shared Drives (if you're a member)

### API Parameters Added

To support Shared Drives, we added:

```python
corpora='drive'                    # Include Shared Drives
includeTeamDriveItems=True        # Include Shared Drive items
supportsTeamDrives=True           # Declare support for Shared Drives
```

With fallback to `corpora='user'` for personal Drive access.

---

## Still Not Working?

1. **Run the diagnostic script**: `python scripts/test_vast_folder_access.py`
2. **Check the output** - it will tell you exactly what's wrong
3. **Follow the recommendations** in the output
4. **Regenerate OAuth token** if needed:
   ```bash
   rm -f ~/.agata/google_drive_token.json
   python scripts/verify_oauth_credentials.py
   ```

If the diagnostic still fails after these steps, the issue is likely with:
- Folder permissions (you're not a member of the Shared Drive)
- OAuth credentials (wrong or misconfigured)
- Google Drive API (not enabled in Cloud Console)
