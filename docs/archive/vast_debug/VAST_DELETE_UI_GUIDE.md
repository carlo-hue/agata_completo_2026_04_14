# VAST Job Delete - UI Guide

## Where to Find the Delete Button

In the VAST Job Detail page, at the bottom near the "Promote to Cataloghi_esterni" section:

```
https://app-test.astrogen.it/agata/admin/vast/jobs/<job_id>
```

### Location in UI

```
┌─────────────────────────────────────────────────────────────┐
│ Promotion Card                                              │
├─────────────────────────────────────────────────────────────┤
│ Transfer VAST lightcurve data (.dat files) and calibrated  │
│ coordinates into Cataloghi_esterni...                       │
│                                                             │
│ ☐ Exclude known variables                                  │
│                                                             │
│ [🚀 Promote to Cataloghi_esterni] [🗑️ Delete Job]  ← HERE │
└─────────────────────────────────────────────────────────────┘
```

---

## How to Use

### Step 1: Navigate to Job Detail
Click on any VAST job in the list:
```
https://app-test.astrogen.it/agata/admin/vast
```

### Step 2: Scroll to Bottom (Promotion Card)
Find the red "Delete Job" button

### Step 3: Click Delete Button
- Button text: 🗑️ **Delete Job** (red)
- Location: Right of the "Promote to Cataloghi_esterni" button

### Step 4: First Confirmation
```
⚠️ Cancella definitivamente il job VAST "VAST-2026-00042"?

Verranno eliminati tutti i risultati VAST (690+ stelle)

[Cancel] [OK]
```

**What it shows**:
- Job code (e.g., "VAST-2026-00042")
- Approximate number of results to delete

### Step 5: Second Confirmation
```
Ultima conferma: questa azione NON si può annullare!

Sei assolutamente sicuro?

[Cancel] [OK]
```

**Why two confirmations**: Delete is permanent and irreversible

### Step 6: Processing
Button changes to show loading:
```
🔄 Deleting...
```

The button is disabled during deletion

### Step 7: Success or Error

**On Success**:
```
✅ VAST job 'VAST-2026-00042' cancelled. Deleted 690 results.
```

Then automatically redirects to job list:
```
https://app-test.astrogen.it/agata/admin/vast
```

**On Error**:
```
❌ Errore: Failed to delete job: ...
```

Button re-enables so you can retry

---

## Permissions

**Who can see the Delete button**:
- ✅ Superuser (can use it)
- ❌ Admin (button hidden)
- ❌ Reviewer (button hidden)
- ❌ Analyst (button hidden)
- ❌ Viewer (button hidden)

---

## What Gets Deleted

| Item | Deleted | Notes |
|------|---------|-------|
| Job record | ✅ | agata_vast_jobs |
| VAST results (690+) | ✅ | agata_vast_results |
| Temporary files | ✅ | /tmp/vast_* |
| Audit entry | ✅ | Logged in audit_log |
| .dat files | ❌ | Preserved in /data/vast_dat_files/ |
| Imported projects | ❌ | Remain independent |
| Light curves | ❌ | Remain in projects |

---

## Example Workflow

### Before Delete
```
Job: VAST-2026-00042
State: completed ✅
Results: 690 VAST candidates
Created: 2026-02-16 15:00:00
```

### User Clicks Delete

```
[🗑️ Delete Job]
         ↓
First confirmation (reason + count)
         ↓
Second confirmation (are you sure?)
         ↓
[🔄 Deleting...]
         ↓
✅ Success! Redirecting...
         ↓
Job list (job no longer visible)
```

### After Delete
```
Job: VAST-2026-00042 - NOT FOUND
Database: 0 records
File system: /data/vast_dat_files/VAST-2026-00042/ preserved
```

---

## Server-Side Details

### API Endpoint Called
```
DELETE /agata/admin/api/vast/jobs/42
```

### Response on Success (HTTP 200)
```json
{
    "success": true,
    "message": "VAST job 'VAST-2026-00042' cancelled. Deleted 690 results."
}
```

### Response on Error (HTTP 500)
```json
{
    "success": false,
    "error": "Failed to delete job: ..."
}
```

### Server Logs
```
[INFO] Deleting VAST job 42 (VAST-2026-00042): NGC 5907
[INFO] Job VAST-2026-00042: 690 VAST results to delete
[INFO] Deleted 690 VAST results for job VAST-2026-00042
[INFO] VAST job VAST-2026-00042 successfully deleted
[audit] vast_job_deleted by superuser@example.com on 2026-02-16T18:40:00
```

---

## Browser Console (DevTools)

If something goes wrong, check browser console (F12 → Console):

**Normal flow**:
```
No errors - delete completes
Page redirects automatically
```

**Network error**:
```
❌ Error: Failed to fetch
Check internet connection
```

**Server error**:
```
Response: {success: false, error: "..."}
```

---

## FAQ

**Q: Can I recover a deleted job?**
A: No. Delete is permanent and irreversible.

**Q: Why two confirmations?**
A: Because deleting a VAST job with 690+ results is a major action with no undo.

**Q: What if the delete fails?**
A: The button re-enables and you can try again. Check server logs.

**Q: Can I delete a running job?**
A: Yes, but it's recommended to let it finish first or cancel it.

**Q: Does it delete the VAST .dat files?**
A: No, they're preserved in `/data/vast_dat_files/` for reference.

**Q: Can admin or reviewer delete jobs?**
A: No, only superuser can delete.

---

## Screenshots

### Button Location
```
┌────────────────────────────────┐
│ VAST Job VAST-2026-00042       │
│ Target: NGC 5907          ✅   │
├────────────────────────────────┤
│ Job Status & Progress          │
│ - Progress: 100%               │
│ - State: completed             │
│ - Results: 690 candidates      │
├────────────────────────────────┤
│ Promotion Card                 │
│ [Transfer VAST data to...]     │
│                                │
│ ☐ Exclude known variables      │
│                                │
│ [🚀 Promote] [🗑️ Delete]  ← HERE
└────────────────────────────────┘
```

---

## Implementation Details

### File Modified
- `agata/templates/admin/vast/job_detail.html`

### Button HTML
```html
<button class="btn btn-danger" onclick="deleteVastJob({{ job.id }})">
    <i class="fas fa-trash"></i> Delete Job
</button>
```

### JavaScript Function
```javascript
function deleteVastJob(jobId) {
    // 1. Get job code from UI
    // 2. Show first confirmation (reason + count)
    // 3. Show second confirmation (are you sure?)
    // 4. Call DELETE /agata/admin/api/vast/jobs/<jobId>
    // 5. On success: redirect to jobs list
    // 6. On error: show error message
}
```

### API Called
- **Endpoint**: `DELETE /agata/admin/api/vast/jobs/<job_id>`
- **Auth**: Superuser only (@superuser_required)
- **Response**: `{success: true, message: "..."}`
