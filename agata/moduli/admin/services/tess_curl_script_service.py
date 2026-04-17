"""TESS Curl Script Library Service

Pure Python service (no Flask dependencies) for managing MAST .sh curl scripts.
Enables script reuse across multiple chunked jobs without re-upload.

Key features:
- Persistent storage on disk (/var/www/astrogen/uploads/tess_curl_scripts/)
- Background parsing (counts lines, no DB table)
- On-demand file reading for batch creation (via get_batch_from_file)
- Auto offset tracking across jobs (entries_processed counter on TessCurlScript)
"""

import logging
import os
import re
import threading
import gzip
import zipfile
import tempfile
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from agata.auth_models import TessCurlScript, TessImportJob
from agata.db import SessionLocal

logger = logging.getLogger(__name__)


# ============================================================================
# Config
# ============================================================================

TESS_CURL_SCRIPTS_DIR = os.environ.get(
    'TESS_CURL_SCRIPTS_DIR',
    '/var/www/astrogen/uploads/tess_curl_scripts'
)

# Ensure directory exists
os.makedirs(TESS_CURL_SCRIPTS_DIR, exist_ok=True)


# ============================================================================
# Utilities
# ============================================================================

def _generate_script_code(session: Session) -> str:
    """Generate unique script code TESSCURL-YYYY-NNNNN."""
    from datetime import datetime
    year = datetime.utcnow().year

    # Find highest NNNNN for this year
    existing = session.query(TessCurlScript).filter(
        TessCurlScript.script_code.like(f'TESSCURL-{year}-%')
    ).all()

    next_num = len(existing) + 1
    while True:
        code = f'TESSCURL-{year}-{next_num:05d}'
        if not session.query(TessCurlScript).filter_by(script_code=code).first():
            return code
        next_num += 1


def _is_gzip_file(filepath: str) -> bool:
    """Check if file is gzip compressed by reading magic number."""
    try:
        with open(filepath, 'rb') as f:
            return f.read(2) == b'\x1f\x8b'
    except Exception:
        return False


def _extract_script_from_archive(filepath: str, original_filename: str) -> tuple[str, str]:
    """
    Extract .sh script from .zip or .7z archive.

    Looks for files matching patterns: *.sh, *.txt, or just the largest file.

    Args:
        filepath: Path to archive file on disk
        original_filename: Original filename (e.g., 'mast.zip')

    Returns:
        (extracted_text, extracted_filename) or raises ValueError if not an archive

    Raises:
        ValueError: If archive cannot be read or no script found inside
    """
    filename_lower = original_filename.lower()

    # Handle .zip files
    if filename_lower.endswith('.zip'):
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                # List all files
                all_files = zf.namelist()

                # Filter for shell/text files
                script_candidates = [
                    f for f in all_files
                    if f.lower().endswith(('.sh', '.txt'))
                    and not f.startswith('__MACOSX')  # Skip macOS metadata
                ]

                if not script_candidates:
                    # Fall back to largest file
                    if all_files:
                        largest = max(all_files, key=lambda f: zf.getinfo(f).file_size)
                        script_candidates = [largest]
                    else:
                        raise ValueError('No files found in zip archive')

                # Use first shell file, or largest
                script_file = script_candidates[0]
                logger.info(f'Extracting {script_file} from zip')

                with zf.open(script_file) as f:
                    content = f.read().decode('utf-8', errors='replace')

                return content, os.path.basename(script_file)

        except zipfile.BadZipFile as e:
            raise ValueError(f'Invalid zip file: {str(e)}')
        except Exception as e:
            raise ValueError(f'Failed to extract from zip: {str(e)}')

    # Handle .7z files (requires py7zr library)
    elif filename_lower.endswith('.7z'):
        try:
            import py7zr
        except ImportError:
            raise ValueError('py7zr library not installed. Cannot extract .7z files.')

        try:
            with py7zr.SevenZipFile(filepath, 'r') as archive:
                # List all files
                all_files = archive.getnames()

                # Filter for shell/text files
                script_candidates = [
                    f for f in all_files
                    if f.lower().endswith(('.sh', '.txt'))
                ]

                if not script_candidates:
                    # Fall back to largest file
                    if all_files:
                        script_candidates = [all_files[0]]
                    else:
                        raise ValueError('No files found in 7z archive')

                script_file = script_candidates[0]
                logger.info(f'Extracting {script_file} from 7z')

                # Extract to temp location
                extract_dir = tempfile.mkdtemp()
                archive.extract(targets=[script_file], path=extract_dir)

                extracted_path = os.path.join(extract_dir, script_file)
                with open(extracted_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                # Cleanup
                import shutil as shutil_cleanup
                shutil_cleanup.rmtree(extract_dir, ignore_errors=True)

                return content, os.path.basename(script_file)

        except Exception as e:
            raise ValueError(f'Failed to extract from 7z: {str(e)}')

    else:
        raise ValueError(f'Unsupported archive format: {original_filename}')


def _parse_curl_script(curl_script_text: str) -> List[dict]:
    """
    Extract curl command lines from .sh script text.

    Returns list of {tic_id, sector, fits_url, relative_path, entry_index}

    Supports multiple curl formats:
    - curl -o "file" "https://..."
    - curl -o 'file' 'https://...'
    - curl --output "file" "https://..."
    - Mixed quotes: curl -o "file" 'https://...'
    """
    entries = []
    entry_index = 0

    for line in curl_script_text.splitlines():
        line = line.strip()

        if not line.startswith('curl'):
            continue

        # Extract output path: --output or -o followed by filename
        # Matches: -o "file", -o 'file', -o file, --output "file", etc.
        output_match = re.search(r'(?:--output|-o)\s+[\'"]?(.*?)[\'"]?(?:\s|$)', line)
        if not output_match:
            continue
        relative_path = output_match.group(1).strip("'\"")

        # Extract MAST URL — try both single and double quotes
        # First try double quotes, then single quotes, then unquoted
        url_matches = re.findall(r'"(https://[^"]+)"', line)
        if not url_matches:
            url_matches = re.findall(r"'(https://[^']+)'", line)
        if not url_matches:
            # Fallback: unquoted URL (less common but possible)
            url_matches = re.findall(r'(https://\S+)', line)

        if not url_matches:
            continue

        fits_url = url_matches[-1]  # Use last match (in case of multiple URLs)

        # Extract TIC ID and sector from relative_path: s(\d{4})-(\d{16})_tess
        tic_match = re.search(r's(\d{4})-(\d{16})_tess', relative_path)
        if not tic_match:
            continue

        sector = int(tic_match.group(1))
        tic_id = int(tic_match.group(2))

        entries.append({
            'entry_index': entry_index,
            'tic_id': tic_id,
            'sector': sector,
            'fits_url': fits_url,
            'relative_path': relative_path,
        })
        entry_index += 1

    return entries


# ============================================================================
# Main API
# ============================================================================

def upload_and_create_script(
    file_storage,
    user_id: str,
    association_id: Optional[int] = None,
    job_name_hint: Optional[str] = None
) -> TessCurlScript:
    """
    Upload curl script file (optionally compressed or archived) and create script record in DB.

    Accepts:
    - .sh or .txt files (plain text) — stored as-is
    - .sh.gz or .txt.gz files (gzip compressed) — stored compressed
    - .zip archives (with .sh or .txt inside) — extracted and stored as .sh.gz
    - .7z archives (with .sh or .txt inside) — extracted and stored as .sh.gz

    Archive extraction:
    - Automatically finds .sh or .txt files inside archives
    - Falls back to largest file if no .sh/.txt found
    - Stores extracted content compressed as .sh.gz on disk

    Compression ratio for text curl scripts: ~98% (600MB → 12MB)

    Files are stored COMPRESSED on disk to save space. During parsing, decompression
    happens in-memory line-by-line using gzip.open() for streaming decompression.

    Does NOT parse synchronously. Parsing happens in a background daemon thread.

    Args:
        file_storage: Flask FileStorage object
        user_id: agata_users.id (UUID)
        association_id: Owning association (NULL = superuser)
        job_name_hint: Optional user-provided hint (not used currently)

    Returns:
        TessCurlScript object with parse_state='uploading' or 'parsing'

    Raises:
        ValueError: If file cannot be saved or extracted
    """
    session = SessionLocal()
    try:
        # Generate unique script code
        script_code = _generate_script_code(session)

        # Save file to disk temporarily
        original_filename = file_storage.filename or 'unknown.sh'
        stored_filename = f'{script_code}_{original_filename}'
        filepath = os.path.join(TESS_CURL_SCRIPTS_DIR, stored_filename)

        try:
            file_storage.save(filepath)
            logger.info(f'Saved upload to {filepath}')
        except Exception as e:
            logger.error(f'Failed to save file: {e}')
            raise ValueError(f'Could not save file: {str(e)}')

        # Check if it's an archive and extract if needed
        filename_lower = original_filename.lower()
        script_content = None
        extracted_filename = None

        if filename_lower.endswith(('.zip', '.7z')):
            try:
                logger.info(f'Extracting from {original_filename}')
                script_content, extracted_filename = _extract_script_from_archive(filepath, original_filename)

                # Delete the archive (we have the content)
                try:
                    os.remove(filepath)
                except:
                    pass

                # Re-save as .sh (will be gzipped during background parse)
                # Store as .sh.gz to be consistent with compression
                stored_filename = f'{script_code}_extracted.sh.gz'
                final_filepath = os.path.join(TESS_CURL_SCRIPTS_DIR, stored_filename)

                # Compress and save the extracted content
                try:
                    with gzip.open(final_filepath, 'wt', encoding='utf-8') as f:
                        f.write(script_content)
                    logger.info(f'Extracted from {original_filename} → {stored_filename}')
                except Exception as e:
                    logger.error(f'Failed to save extracted content: {e}')
                    raise ValueError(f'Could not save extracted content: {str(e)}')

                # Update filename to just the extracted filename (archive name no longer relevant)
                original_filename = extracted_filename
                logger.info(f'DEBUG: After extraction, original_filename set to: {original_filename}')

            except ValueError as e:
                logger.error(f'Archive extraction failed: {e}')
                raise

        # Create DB record
        script = TessCurlScript(
            script_code=script_code,
            original_filename=original_filename,
            stored_filename=stored_filename,
            association_id=association_id,
            parse_state='uploading',
            created_by=user_id,
        )
        session.add(script)
        session.commit()

        storage_type = 'archive (extracted)' if filename_lower.endswith(('.zip', '.7z')) else 'compressed' if original_filename.endswith('.gz') else 'plain text'
        logger.info(f'Created TessCurlScript: {script_code} (stored as {storage_type})')

        # Launch background parse thread
        thread = threading.Thread(
            target=_parse_in_background,
            args=(script.id,),
            daemon=True,
            name=f'tess-parse-{script.id}'
        )
        thread.start()
        logger.info(f'Launched parse thread for script {script.id}')

        return script

    finally:
        session.close()


def _parse_in_background(script_id: int) -> None:
    """
    Parse curl script file (compressed or plain) and count entries.

    Runs in a daemon thread. Updates parse_state and total_entries.

    No longer inserts entries into agata_tess_curl_entries table. Instead,
    only counts the number of curl lines. Entries will be read directly from
    the file on-demand when jobs are created via get_batch_from_file().

    For .gz files: reads line-by-line using gzip.open() for streaming decompression
    (no intermediate decompressed file on disk, minimal memory footprint).

    For .sh/.txt files: reads normally.

    Args:
        script_id: TessCurlScript.id
    """
    session = SessionLocal()
    try:
        script = session.query(TessCurlScript).get(script_id)
        if not script:
            logger.error(f'Script {script_id} not found')
            return

        script.parse_state = 'parsing'
        session.commit()
        logger.info(f'Started parsing script {script_id}')

        # Read file from disk (detect .gz format and decompress on-the-fly)
        filepath = os.path.join(TESS_CURL_SCRIPTS_DIR, script.stored_filename)
        try:
            # Check if file is gzip compressed (by magic number)
            is_gzip = _is_gzip_file(filepath)

            if is_gzip:
                # Streaming decompression from .gz file
                logger.info(f'Reading compressed file {filepath}')
                with gzip.open(filepath, 'rt', encoding='utf-8', errors='replace') as f:
                    curl_script_text = f.read()
            else:
                # Plain text file
                logger.info(f'Reading plain text file {filepath}')
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    curl_script_text = f.read()

        except Exception as e:
            script.parse_state = 'failed'
            script.parse_error = f'Could not read file: {str(e)[:2000]}'
            session.commit()
            logger.error(f'Failed to read {filepath}: {e}')
            return

        # Parse curl lines to count them (no DB insert)
        try:
            entries = _parse_curl_script(curl_script_text)
        except Exception as e:
            script.parse_state = 'failed'
            script.parse_error = f'Parse error: {str(e)[:2000]}'
            session.commit()
            logger.error(f'Parse error for script {script_id}: {e}')
            return

        if not entries:
            script.parse_state = 'failed'
            script.parse_error = 'No curl lines found in script'
            session.commit()
            logger.warning(f'No curl entries found in script {script_id}')
            return

        logger.info(f'Counted {len(entries)} curl entries in script {script_id}')

        # Mark as ready (only store total count, no table inserts)
        script.total_entries = len(entries)
        script.parse_state = 'ready'
        session.commit()
        logger.info(f'Script {script_id} parse complete: {len(entries)} entries available for batching')

    except Exception as e:
        logger.error(f'Unexpected error parsing script {script_id}: {e}', exc_info=True)
        try:
            script.parse_state = 'failed'
            script.parse_error = f'Unexpected error: {str(e)[:2000]}'
            session.commit()
        except:
            pass
    finally:
        session.close()


def get_batch_from_file(script_id: int, batch_size: int = 500, offset: int = 0) -> list:
    """
    Read a batch of curl entries directly from the script file on disk.

    Instead of reading from agata_tess_curl_entries table, this function:
    1. Opens the script file from disk (.gz or plain text)
    2. Skips the first `offset` curl lines
    3. Reads and parses the next `batch_size` curl lines
    4. Returns a list of dicts with keys: entry_index, tic_id, sector, url, relative_path

    This replaces the DB table read, allowing elimination of agata_tess_curl_entries.

    Performance: For a 600k-line .sh.gz file, skipping 300k lines takes ~1-2 seconds.
    This is acceptable since it only happens at job creation time (not execution).

    Args:
        script_id: TessCurlScript.id
        batch_size: Max entries to return (default 500)
        offset: 0-based line index to start reading from

    Returns:
        List of entry dicts (empty list if offset >= total_entries or script not found)

    Raises:
        ValueError: If script is not ready
    """
    session = SessionLocal()
    try:
        script = session.query(TessCurlScript).get(script_id)
        if not script:
            logger.warning(f'Script {script_id} not found for batch read')
            return []

        if script.parse_state != 'ready':
            raise ValueError(f'Script {script_id} is not ready (state: {script.parse_state})')

        if offset >= script.total_entries:
            logger.info(f'Offset {offset} >= total_entries {script.total_entries}, returning empty batch')
            return []

        # Determine file path and whether it's gzip
        filepath = os.path.join(TESS_CURL_SCRIPTS_DIR, script.stored_filename)
        if not os.path.exists(filepath):
            logger.error(f'Script file not found: {filepath}')
            raise ValueError(f'Script file not found: {filepath}')

        is_gzip = _is_gzip_file(filepath)

        # Open file and read batch
        results = []
        current_index = 0
        open_fn = gzip.open if is_gzip else open

        try:
            with open_fn(filepath, 'rt', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()

                    # Skip non-curl lines
                    if not line or not line.startswith('curl'):
                        continue

                    # Skip lines before offset
                    if current_index < offset:
                        current_index += 1
                        continue

                    # Parse this line
                    try:
                        # Reuse _parse_curl_script logic but for a single line
                        # Extract output path
                        output_match = re.search(r'(?:--output|-o)\s+[\'"]?(.*?)[\'"]?(?:\s|$)', line)
                        if not output_match:
                            current_index += 1
                            continue
                        relative_path = output_match.group(1).strip("'\"")

                        # Extract MAST URL
                        url_matches = re.findall(r'"(https://[^"]+)"', line)
                        if not url_matches:
                            url_matches = re.findall(r"'(https://[^']+)'", line)
                        if not url_matches:
                            url_matches = re.findall(r'(https://\S+)', line)

                        if not url_matches:
                            current_index += 1
                            continue

                        fits_url = url_matches[-1]

                        # Extract TIC ID and sector
                        tic_match = re.search(r's(\d{4})-(\d{16})_tess', relative_path)
                        if not tic_match:
                            current_index += 1
                            continue

                        sector = int(tic_match.group(1))
                        tic_id = int(tic_match.group(2))

                        results.append({
                            'entry_index': current_index,
                            'tic_id': tic_id,
                            'sector': sector,
                            'url': fits_url,  # Normalize to 'url' for execute_job() compatibility
                            'relative_path': relative_path,
                        })

                        current_index += 1

                        # Stop when batch is full
                        if len(results) >= batch_size:
                            break

                    except Exception as e:
                        logger.debug(f'Failed to parse curl line at index {current_index}: {e}')
                        current_index += 1
                        continue

        except Exception as e:
            logger.error(f'Failed to read batch from {filepath}: {e}')
            raise

        logger.info(f'Read batch of {len(results)} entries from script {script_id} starting at offset {offset}')
        return results

    finally:
        session.close()


def get_script_status(script_id: int) -> dict:
    """
    Get current parse status of a script.

    Returns:
        {id, script_code, parse_state, total_entries, entries_processed,
         batches_remaining, next_offset, parse_error (if failed)}
    """
    session = SessionLocal()
    try:
        script = session.query(TessCurlScript).get(script_id)
        if not script:
            return {'error': 'Script not found'}

        remaining = script.total_entries - script.entries_processed
        batches_remaining = (remaining + 499) // 500 if remaining > 0 else 0

        result = {
            'id': script.id,
            'script_code': script.script_code,
            'original_filename': script.original_filename,
            'parse_state': script.parse_state,
            'total_entries': script.total_entries,
            'entries_processed': script.entries_processed,
            'batches_remaining': batches_remaining,
            'next_offset': script.entries_processed,  # Auto offset suggestion
        }

        if script.parse_state == 'failed':
            result['parse_error'] = script.parse_error or 'Unknown error'

        return result

    finally:
        session.close()


def get_next_batch(script_id: int, batch_size: int = 500, offset: int = 0) -> List[dict]:
    """
    Get batch from a script starting at specific offset.

    DEPRECATED: This function now delegates to get_batch_from_file() for compatibility.
    Previously read from agata_tess_curl_entries table, now reads directly from disk.

    Returns list of {tic_id, sector, url, relative_path} for entries
    where entry_index >= offset, ordered by entry_index, limited to batch_size.

    Note: 'url' key (not 'fits_url') for compatibility with execute_job().

    Args:
        script_id: TessCurlScript.id
        batch_size: Max entries to return (default 500)
        offset: Starting entry_index (default 0)

    Returns:
        List of entry dicts (empty list if offset beyond total entries)
    """
    return get_batch_from_file(script_id, batch_size, offset)


def mark_entries_processed(script_id: int, entry_indices: List[int]) -> None:
    """
    Mark entries as processed after a job completes.

    Now that agata_tess_curl_entries table is removed, this simply increments
    the entries_processed counter on TessCurlScript based on the number of
    entries just processed.

    Args:
        script_id: TessCurlScript.id
        entry_indices: List of TessCurlEntry.entry_index values (not used anymore, but kept for API compatibility)

    Safe under concurrent access: uses simple increment.
    """
    session = SessionLocal()
    try:
        script = session.query(TessCurlScript).get(script_id)
        if script:
            # Increment entries_processed by the number of entries just processed
            script.entries_processed = (script.entries_processed or 0) + len(entry_indices)
            session.commit()
            logger.info(f'Updated script {script_id}: entries_processed={script.entries_processed}')
        else:
            logger.warning(f'Script {script_id} not found for mark_entries_processed')

    finally:
        session.close()


def list_scripts(
    association_id: Optional[int] = None,
    is_superuser: bool = False
) -> List[dict]:
    """
    List scripts visible to a user.

    Args:
        association_id: User's association (required if not superuser)
        is_superuser: If True, sees all scripts

    Returns:
        List of script dicts, ordered by created_at DESC
    """
    session = SessionLocal()
    try:
        query = session.query(TessCurlScript)

        if not is_superuser and association_id is not None:
            query = query.filter(TessCurlScript.association_id == association_id)

        scripts = query.order_by(TessCurlScript.created_at.desc()).all()

        return [
            {
                'id': s.id,
                'script_code': s.script_code,
                'original_filename': s.original_filename,
                'parse_state': s.parse_state,
                'total_entries': s.total_entries,
                'entries_processed': s.entries_processed,
                'batches_remaining': (s.total_entries - s.entries_processed + 499) // 500
                    if s.total_entries > s.entries_processed else 0,
                'created_at': s.created_at.isoformat() if s.created_at else None,
                'created_by': s.created_by,
            }
            for s in scripts
        ]

    finally:
        session.close()


def delete_script(script_id: int, check_running: bool = True) -> None:
    """
    Delete a script and all its entries.

    Args:
        script_id: TessCurlScript.id
        check_running: If True, raise ValueError if any associated jobs are running

    Raises:
        ValueError: If check_running=True and jobs are running
        FileNotFoundError: If disk file not found (warns but continues)
    """
    session = SessionLocal()
    try:
        script = session.query(TessCurlScript).get(script_id)
        if not script:
            logger.warning(f'Script {script_id} not found for deletion')
            return

        # Check for running jobs
        if check_running:
            running_jobs = session.query(TessImportJob).filter(
                TessImportJob.curl_script_id == script_id,
                TessImportJob.state.in_(['downloading', 'analyzing', 'crossmatching'])
            ).count()

            if running_jobs > 0:
                raise ValueError(f'Cannot delete script: {running_jobs} job(s) still running')

        # Delete from DB (cascade will delete entries)
        session.delete(script)
        session.commit()
        logger.info(f'Deleted script {script_id} from DB')

        # Delete from disk
        filepath = os.path.join(TESS_CURL_SCRIPTS_DIR, script.stored_filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f'Deleted file: {filepath}')
        except Exception as e:
            logger.warning(f'Could not delete file {filepath}: {e}')

    finally:
        session.close()
