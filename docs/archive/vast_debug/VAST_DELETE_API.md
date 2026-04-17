# VAST Job Delete API

## Overview

Nuova API per cancellare un VAST job intero (superuser only).

**Endpoint**: `DELETE /agata/admin/api/vast/jobs/<job_id>`

---

## Usage

### Via curl

```bash
curl -X DELETE https://app-test.astrogen.it/agata/admin/api/vast/jobs/42 \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_ID"
```

### Via JavaScript

```javascript
fetch(`/agata/admin/api/vast/jobs/${jobId}`, {
    method: 'DELETE',
    headers: {'Content-Type': 'application/json'}
})
.then(r => r.json())
.then(data => {
    if (data.success) {
        console.log(data.message);
        // Refresh page or update list
        location.reload();
    } else {
        alert(`Errore: ${data.error}`);
    }
})
.catch(error => console.error('Error:', error));
```

---

## Response Format

### Success (HTTP 200)
```json
{
    "success": true,
    "message": "VAST job 'VAST-2026-00042' cancelled. Deleted 690 results."
}
```

### Error - Job not found (HTTP 404)
```json
{
    "success": false,
    "error": "Job 999 not found"
}
```

### Error - Permission denied (HTTP 403)
```json
{
    "success": false,
    "error": "Superuser access required"
}
```

### Error - Internal error (HTTP 500)
```json
{
    "success": false,
    "error": "Failed to delete job: ..."
}
```

---

## What Gets Deleted

When you delete a VAST job:

1. ✅ **agata_vast_jobs record** - The job itself
2. ✅ **agata_vast_results** - All 690+ VAST candidate results
3. ✅ **Temporary files** - Temporary directory (if exists)
4. ✅ **Audit trail** - Logged in audit_log table

**What does NOT get deleted**:
- ❌ VAST .dat files (preserved for reference in /data/vast_dat_files/)
- ❌ Projects created from this job (they remain independent)
- ❌ Light curves imported from this job (they remain in projects)

---

## Frontend Integration

### Add Delete Button in Job Detail Page

```html
<button class="btn btn-danger btn-sm" onclick="deleteVastJob(jobId)">
    <i class="bi bi-trash"></i> Delete Job
</button>
```

### JavaScript Handler

```javascript
function deleteVastJob(jobId) {
    if (!confirm('⚠️ Cancella definitivamente questo job VAST e tutti i suoi risultati?')) {
        return;
    }

    const confirmed = confirm('Ultima conferma: sei sicuro? Questa azione NON si può annullare!');
    if (!confirmed) return;

    fetch(`/agata/admin/api/vast/jobs/${jobId}`, {
        method: 'DELETE',
        headers: {'Content-Type': 'application/json'}
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            location.href = '/agata/admin/vast';  // Redirect to jobs list
        } else {
            alert(`Errore: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Errore di rete');
    });
}
```

---

## Permissions

**Who can use this API**:
- ✅ Superuser only (requires `@superuser_required` decorator)

**Who cannot**:
- ❌ Admin (single association)
- ❌ Reviewer
- ❌ Analyst
- ❌ Viewer

---

## Audit Trail

Every delete is logged in the audit log:
```sql
SELECT * FROM audit_log
WHERE action = 'vast_job_deleted'
ORDER BY created_at DESC;
```

Shows:
- Who deleted
- When deleted
- Job ID / code
- Number of results deleted

---

## Database Impact

### Before Delete
```
agata_vast_jobs:      1 record (job 42)
agata_vast_results:   690 records (results for job 42)
Total DB size:        ~50 MB (photometric data)
```

### After Delete
```
agata_vast_jobs:      0 records
agata_vast_results:   0 records
Total DB size:        freed ~50 MB
```

---

## Server Logs

When a job is deleted, you'll see:

```
[INFO] Deleting VAST job 42 (VAST-2026-00042): NGC 5907
[INFO] Job VAST-2026-00042: 690 VAST results to delete
[INFO] Deleted 690 VAST results for job VAST-2026-00042
[INFO] Deleted temp directory: /tmp/vast_2026_00042/
[INFO] VAST job VAST-2026-00042 successfully deleted
[audit] vast_job_deleted by user@example.com on 2026-02-16T18:40:00
```

---

## Example Flow

### User Deletes a Job

1. Superuser navigates to: `/agata/admin/vast/jobs/42`
2. Sees job details: "VAST-2026-00042: 690 results"
3. Clicks "Delete Job"
4. Gets double confirmation:
   - "⚠️ Cancella definitivamente questo job VAST?"
   - "Ultima conferma: sei sicuro?"
5. POST DELETE `/agata/admin/api/vast/jobs/42`
6. Server:
   - Deletes 690 VAST results from DB
   - Deletes temp files
   - Deletes job record
   - Returns: `{success: true, message: "...deleted 690 results"}`
7. Frontend redirects to `/agata/admin/vast` (jobs list)
8. Job no longer appears in list

---

## Notes

- **Permanent**: Deletion is PERMANENT. No undelete available.
- **Fast**: Deletes 690+ results in <1 second (batch delete)
- **Safe**: Double confirmation + audit trail
- **Atomic**: All-or-nothing (if any step fails, whole transaction rolls back)

---

## Related APIs

- `POST /agata/admin/api/vast/jobs` - Create new job
- `GET /agata/admin/vast/jobs/<id>` - View job details
- `POST /agata/admin/api/vast/jobs/<id>/execute` - Run job
- `POST /agata/admin/api/vast/jobs/<id>/promote` - Promote results to projects
- `DELETE /agata/admin/api/vast/jobs/<id>` - **Delete job** (NEW)
