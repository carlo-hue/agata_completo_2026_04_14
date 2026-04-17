"""
Star Index Service - Build and query a star-based knowledge index

Maps each GrAGVar star to all related emails, Teams messages,
expert corrections, variable types discussed, and period values.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from agata.kb.services.star_knowledge_extractor import extract_knowledge

logger = logging.getLogger(__name__)

KB_DATA_DIR = Path('/var/www/astrogen/kb_data')
STAR_INDEX_PATH = KB_DATA_DIR / 'star_index.json'
TEAMS_CHANNEL_DIR = KB_DATA_DIR / 'canali teams' / 'Stelle variabili'

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif'}
DOC_EXTENSIONS = {'.xlsx', '.docx', '.txt', '.csv', '.pdf'}


def build_star_index(
    gmail_dir: Optional[str] = None,
    teams_dir: Optional[str] = None,
) -> Dict:
    """
    Build the star index from all parsed emails and Teams messages.

    Reads all parsed JSON files, runs the knowledge extractor on each,
    and groups results by star ID.

    Returns:
        The complete star index dict
    """
    gmail_path = Path(gmail_dir or KB_DATA_DIR / 'gmail_parsed')
    teams_path = Path(teams_dir or KB_DATA_DIR / 'teams_parsed')

    star_index = {}

    # Process emails
    email_count = 0
    if gmail_path.exists():
        for json_file in sorted(gmail_path.glob('*.json')):
            if json_file.name == 'index.json':
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    email_data = json.load(f)

                body = email_data.get('body_text', '')
                subject = email_data.get('subject', '')
                from_info = email_data.get('from', {})
                from_email = from_info.get('email', '') if isinstance(from_info, dict) else ''
                from_name = from_info.get('name', '') if isinstance(from_info, dict) else ''

                knowledge = extract_knowledge(body, subject, from_email, from_name)

                if not knowledge.star_ids:
                    continue

                msg_id = email_data.get('id', json_file.stem)
                date = email_data.get('date', '')

                for star_id in knowledge.star_ids:
                    _add_to_index(star_index, star_id, {
                        'source': 'email',
                        'msg_id': msg_id,
                        'subject': subject,
                        'from_name': from_name,
                        'from_email': from_email,
                        'date': date,
                        'knowledge': knowledge,
                        'body_preview': body[:500] if body else '',
                    })

                email_count += 1
            except Exception as e:
                logger.warning(f"Error processing email {json_file.name}: {e}")

    # Process Teams messages
    teams_count = 0
    if teams_path.exists():
        for json_file in sorted(teams_path.glob('*.json')):
            if json_file.name == 'index.json':
                continue
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    msg_data = json.load(f)

                body = msg_data.get('body_text', '')
                subject = msg_data.get('subject', '')
                from_name = msg_data.get('from_name', '')

                # Teams messages have star_id from directory name
                dir_star_id = msg_data.get('star_id')
                dir_var_type = msg_data.get('variable_type')

                knowledge = extract_knowledge(body, subject)

                # Add directory-derived star ID if not already extracted
                if dir_star_id and dir_star_id not in knowledge.star_ids:
                    knowledge.star_ids.append(dir_star_id)

                # Add directory-derived variable type
                if dir_var_type and dir_var_type not in knowledge.variable_types:
                    knowledge.variable_types.insert(0, dir_var_type)

                if not knowledge.star_ids:
                    continue

                msg_id = msg_data.get('id', json_file.stem)
                date = msg_data.get('date', '')
                attachments = msg_data.get('thread_attachment_files', [])

                for star_id in knowledge.star_ids:
                    _add_to_index(star_index, star_id, {
                        'source': 'teams',
                        'msg_id': msg_id,
                        'subject': subject,
                        'from_name': from_name,
                        'from_email': None,
                        'date': date,
                        'knowledge': knowledge,
                        'body_preview': body[:500] if body else '',
                        'attachments': attachments,
                    })

                teams_count += 1
            except Exception as e:
                logger.warning(f"Error processing Teams message {json_file.name}: {e}")

    # Finalize index entries
    for star_id, entry in star_index.items():
        _finalize_entry(entry)

    # Save to disk
    _save_index(star_index)

    print(f"\nStar index built:")
    print(f"  Stars indexed: {len(star_index)}")
    print(f"  From emails: {email_count}")
    print(f"  From Teams: {teams_count}")

    return star_index


def _add_to_index(index: Dict, star_id: str, item: Dict):
    """Add a message's knowledge to the star index"""
    if star_id not in index:
        index[star_id] = {
            'email_ids': [],
            'teams_ids': [],
            'expert_emails': [],
            'messages': [],
            'variable_types_discussed': set(),
            'period_values': set(),
            'amplitude_values': set(),
            'corrections': [],
            'attachments': set(),
            'last_expert_date': None,
            'last_message_date': None,
        }

    entry = index[star_id]
    knowledge = item['knowledge']
    msg_id = item['msg_id']

    # Track message IDs by source
    if item['source'] == 'email':
        if msg_id not in entry['email_ids']:
            entry['email_ids'].append(msg_id)
        if knowledge.is_expert and msg_id not in entry['expert_emails']:
            entry['expert_emails'].append(msg_id)
    elif item['source'] == 'teams':
        if msg_id not in entry['teams_ids']:
            entry['teams_ids'].append(msg_id)

    # Aggregate knowledge
    entry['variable_types_discussed'].update(knowledge.variable_types)
    entry['period_values'].update(knowledge.period_values)
    entry['amplitude_values'].update(knowledge.amplitude_values)

    # Track corrections (with source context)
    for correction in knowledge.corrections:
        entry['corrections'].append({
            'text': correction,
            'from': item['from_name'],
            'date': item['date'],
            'is_expert': knowledge.is_expert,
            'source': item['source'],
        })

    # Track attachments from Teams
    if item.get('attachments'):
        entry['attachments'].update(item['attachments'])

    # Store message summary for context display
    entry['messages'].append({
        'msg_id': msg_id,
        'source': item['source'],
        'subject': item['subject'],
        'from_name': item['from_name'],
        'date': item['date'],
        'is_expert': knowledge.is_expert,
        'topic': knowledge.topic,
        'body_preview': item['body_preview'],
    })

    # Track dates
    date = item['date']
    if date:
        if knowledge.is_expert:
            if not entry['last_expert_date'] or date > entry['last_expert_date']:
                entry['last_expert_date'] = date
        if not entry['last_message_date'] or date > entry['last_message_date']:
            entry['last_message_date'] = date


def _finalize_entry(entry: Dict):
    """Convert sets to sorted lists for JSON serialization"""
    entry['variable_types_discussed'] = sorted(entry['variable_types_discussed'])
    entry['period_values'] = sorted(entry['period_values'])
    entry['amplitude_values'] = sorted(entry['amplitude_values'])
    entry['attachments'] = sorted(entry['attachments'])

    # Sort messages by date
    entry['messages'].sort(key=lambda m: m.get('date') or '', reverse=True)

    # Sort corrections: expert first, then by date
    entry['corrections'].sort(
        key=lambda c: (not c.get('is_expert', False), c.get('date') or ''),
        reverse=True
    )


def _save_index(star_index: Dict):
    """Save star index to disk"""
    STAR_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STAR_INDEX_PATH, 'w', encoding='utf-8') as f:
        json.dump(star_index, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved to: {STAR_INDEX_PATH}")


def load_star_index() -> Dict:
    """Load star index from disk. Returns empty dict if not found."""
    if STAR_INDEX_PATH.exists():
        with open(STAR_INDEX_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_star_context(star_id: str) -> Optional[Dict]:
    """
    Get all KB context for a specific star.

    Args:
        star_id: Star identifier (e.g., 'GrAGVar049')

    Returns:
        Star index entry or None if not found
    """
    index = load_star_index()
    return index.get(star_id)


def get_star_images(star_id: str) -> List[Dict]:
    """
    Returns list of image files available for a star from Teams attachments.

    Each entry: {'filename': str, 'path': str, 'thread_dir': str}
    Path is absolute on disk (for serving).
    """
    if not TEAMS_CHANNEL_DIR.exists():
        return []

    images = []
    # Thread dirs contain star_id in their name (e.g. 8-ACV-GrAGVar049-...)
    for thread_dir in TEAMS_CHANNEL_DIR.iterdir():
        if not thread_dir.is_dir():
            continue
        if star_id.upper() not in thread_dir.name.upper():
            continue
        for f in sorted(thread_dir.iterdir()):
            if f.suffix.lower() in IMAGE_EXTENSIONS:
                images.append({
                    'filename': f.name,
                    'path': str(f),
                    'thread_dir': thread_dir.name,
                })
    return images


def get_star_docs(star_id: str) -> List[Dict]:
    """Returns list of document files (xlsx, docx...) for a star from Teams."""
    if not TEAMS_CHANNEL_DIR.exists():
        return []

    docs = []
    for thread_dir in TEAMS_CHANNEL_DIR.iterdir():
        if not thread_dir.is_dir():
            continue
        if star_id.upper() not in thread_dir.name.upper():
            continue
        for f in sorted(thread_dir.iterdir()):
            if f.suffix.lower() in DOC_EXTENSIONS:
                docs.append({
                    'filename': f.name,
                    'path': str(f),
                    'thread_dir': thread_dir.name,
                })
    return docs


def get_index_summary() -> Dict:
    """Get summary statistics of the star index"""
    index = load_star_index()
    if not index:
        return {'total_stars': 0, 'total_emails': 0, 'total_teams': 0,
                'stars_with_expert': 0, 'stars_with_corrections': 0}

    total_emails = sum(len(e.get('email_ids', [])) for e in index.values())
    total_teams = sum(len(e.get('teams_ids', [])) for e in index.values())
    with_expert = sum(1 for e in index.values() if e.get('expert_emails'))
    with_corrections = sum(1 for e in index.values() if e.get('corrections'))

    return {
        'total_stars': len(index),
        'total_emails': total_emails,
        'total_teams': total_teams,
        'stars_with_expert': with_expert,
        'stars_with_corrections': with_corrections,
    }
