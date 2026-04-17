"""
Teams Parser Service - Parse Microsoft Teams channel exports (Graph API JSON)

Reads messages.json files from Teams channel backup directories.
Directory naming convention: 8-<TYPE>-GrAGVar<NNN>-<GaiaID>
"""
import json
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from bs4 import BeautifulSoup


class TeamsParserService:
    """Parse Teams channel exports and extract structured message data"""

    def __init__(self, output_dir: str = '/var/www/astrogen/kb_data/teams_parsed'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.output_dir / 'index.json'
        self.index = self._load_index()

    def _load_index(self) -> Dict:
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'messages': {}, 'metadata': {'total_messages': 0, 'last_updated': None}}

    def _save_index(self):
        self.index['metadata']['last_updated'] = datetime.now().isoformat()
        self.index['metadata']['total_messages'] = len(self.index['messages'])
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _clean_html(html_text: str) -> str:
        """Clean HTML to plain text using BeautifulSoup"""
        soup = BeautifulSoup(html_text, 'html.parser')
        for tag in soup(['script', 'style']):
            tag.decompose()
        # Remove attachment placeholder tags
        for tag in soup.find_all('attachment'):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @staticmethod
    def _extract_thread_metadata(dir_name: str) -> Dict:
        """
        Extract metadata from directory name.

        Convention: 8-<TYPE>-GrAGVar<NNN>-<GaiaID>
        Examples:
            8-RS-GrAGVar114-6109653414505458048
            8-DSCT-GrAGVar017-ex21-335686607973792000
            8-EA ROT-GrAGVar077-3982589037457609216
            9-0336-2255173119656110336  (no type/star info)
        """
        metadata = {
            'star_id': None,
            'variable_type': None,
            'gaia_id': None,
        }

        # Extract GrAGVar ID
        star_match = re.search(r'GrAGVar(\d+)', dir_name, re.IGNORECASE)
        if star_match:
            metadata['star_id'] = f'GrAGVar{star_match.group(1)}'

        # Extract variable type (between first dash and GrAGVar or TIC)
        type_match = re.match(r'\d+-(.+?)(?:-GrAGVar|-TIC\s)', dir_name)
        if type_match:
            vtype = type_match.group(1).strip()
            if vtype and not vtype.isdigit():
                metadata['variable_type'] = vtype

        # Extract Gaia ID (last numeric segment)
        parts = dir_name.split('-')
        if len(parts) >= 2:
            last_part = parts[-1]
            if len(last_part) > 10 and last_part.isdigit():
                metadata['gaia_id'] = last_part

        return metadata

    def parse_teams_directory(self, teams_dir: str, channel_name: str = 'Stelle variabili') -> Dict:
        """
        Parse all threads from a Teams channel export directory.

        Args:
            teams_dir: Root Teams backup directory (e.g., 'kb_data/canali teams')
            channel_name: Name of channel subdirectory

        Returns:
            Dict with parsing statistics
        """
        teams_path = Path(teams_dir) / channel_name
        if not teams_path.exists():
            raise FileNotFoundError(f"Teams channel directory not found: {teams_path}")

        stats = {
            'threads_processed': 0,
            'messages_parsed': 0,
            'skipped_empty': 0,
            'skipped_system': 0,
            'errors': 0,
        }

        thread_dirs = sorted([d for d in teams_path.iterdir() if d.is_dir()])
        print(f"Found {len(thread_dirs)} thread directories in '{channel_name}'")

        for thread_dir in thread_dirs:
            msg_file = thread_dir / 'messages.json'
            if not msg_file.exists() or msg_file.stat().st_size == 0:
                stats['skipped_empty'] += 1
                continue

            try:
                with open(msg_file, 'r', encoding='utf-8') as f:
                    messages = json.load(f)

                if not isinstance(messages, list):
                    continue

                thread_metadata = self._extract_thread_metadata(thread_dir.name)

                # List attachment files in the directory
                attachment_files = [
                    f.name for f in thread_dir.iterdir()
                    if f.is_file() and f.name != 'messages.json'
                ]

                for msg in messages:
                    try:
                        result = self._parse_message(msg, thread_dir.name,
                                                     thread_metadata, attachment_files)
                        if result:
                            stats['messages_parsed'] += 1
                        else:
                            stats['skipped_system'] += 1
                    except Exception as e:
                        print(f"Error parsing message in {thread_dir.name}: {e}")
                        stats['errors'] += 1

                stats['threads_processed'] += 1

            except Exception as e:
                print(f"Error reading {msg_file}: {e}")
                stats['errors'] += 1

        self._save_index()

        print(f"\nTeams parsing complete:")
        print(f"  Threads processed: {stats['threads_processed']}")
        print(f"  Messages parsed: {stats['messages_parsed']}")
        print(f"  Skipped (empty): {stats['skipped_empty']}")
        print(f"  Skipped (system): {stats['skipped_system']}")
        print(f"  Errors: {stats['errors']}")

        return stats

    def _parse_message(self, msg: Dict, thread_dir_name: str,
                       thread_metadata: Dict, attachment_files: List[str]) -> Optional[Dict]:
        """Parse a single Teams message and save to disk"""
        # Skip system messages (no user)
        if not msg.get('from') or not msg['from'].get('user'):
            return None

        # Skip empty body
        body = msg.get('body', {})
        body_content = body.get('content', '')
        if not body_content or not body_content.strip():
            return None

        # Generate unique ID
        msg_id = hashlib.md5(f"teams_{thread_dir_name}_{msg['id']}".encode()).hexdigest()

        # Skip if already indexed
        if msg_id in self.index['messages']:
            return None

        # Extract user info
        user = msg['from']['user']
        from_name = user.get('displayName', 'Unknown')

        # Clean body text
        if body.get('contentType') == 'html':
            body_text = self._clean_html(body_content)
        else:
            body_text = body_content.strip()

        # Skip if cleaned text is too short (likely just an attachment reference)
        if len(body_text) < 5:
            return None

        # Extract attachment names from message
        msg_attachments = []
        for att in msg.get('attachments', []):
            name = att.get('name', '')
            if name:
                msg_attachments.append(name)

        # Parse date
        date_str = msg.get('createdDateTime')

        # Build message data
        message_data = {
            'id': msg_id,
            'source': 'teams',
            'thread_id': thread_dir_name,
            'message_id': msg.get('id'),
            'subject': msg.get('subject') or '',
            'from_name': from_name,
            'date': date_str,
            'body_text': body_text[:15000],
            'body_length': len(body_text),
            'star_id': thread_metadata.get('star_id'),
            'variable_type': thread_metadata.get('variable_type'),
            'gaia_id': thread_metadata.get('gaia_id'),
            'attachments': msg_attachments,
            'thread_attachment_files': attachment_files,
            'reply_to_id': msg.get('replyToId'),
            'indexed_at': datetime.now().isoformat(),
        }

        # Save to disk
        out_file = self.output_dir / f"{msg_id}.json"
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(message_data, f, indent=2, ensure_ascii=False)

        # Update index
        self.index['messages'][msg_id] = {
            'thread_id': thread_dir_name,
            'from_name': from_name,
            'date': date_str,
            'star_id': thread_metadata.get('star_id'),
            'variable_type': thread_metadata.get('variable_type'),
            'body_length': len(body_text),
        }

        return message_data

    def get_summary(self) -> Dict:
        """Get summary of indexed Teams messages"""
        stars = {}
        types = {}
        for info in self.index['messages'].values():
            sid = info.get('star_id')
            if sid:
                stars[sid] = stars.get(sid, 0) + 1
            vt = info.get('variable_type')
            if vt:
                types[vt] = types.get(vt, 0) + 1

        return {
            'total_messages': len(self.index['messages']),
            'last_updated': self.index['metadata'].get('last_updated'),
            'stars_found': len(stars),
            'star_distribution': dict(sorted(stars.items())),
            'type_distribution': dict(sorted(types.items(), key=lambda x: -x[1])),
        }
