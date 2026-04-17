"""
Help Service - carica e renderizza articoli Markdown dal filesystem.

Struttura contenuti:
    agata/help/content/
    ├── _config.yml        # mappa help_id -> {path, module}
    ├── editor/
    │   └── overview.md
    └── admin/
        └── projects.md

Ogni .md ha frontmatter YAML tra --- delimitatori:
    ---
    title: "Titolo articolo"
    tags: [tag1, tag2]
    ---
    Corpo Markdown...
"""
import os
import markdown
import yaml
import bleach
import logging

logger = logging.getLogger(__name__)

CONTENT_ROOT = os.path.join(os.path.dirname(__file__), 'content')

# Cache in-memory: {help_id: article_dict}
_cache: dict = {}
_config_cache: dict | None = None

# Tag HTML ammessi nel rendering
ALLOWED_TAGS = [
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'strong', 'em', 's',
    'code', 'pre', 'blockquote',
    'a', 'img',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'hr', 'br', 'div', 'span',
    'iframe',  # per embed YouTube/Vimeo
]

ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'width', 'height', 'style'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen', 'allow', 'style'],
    'th': ['align', 'style'],
    'td': ['align', 'style'],
    '*': ['class', 'style', 'id'],
}


def _parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Separa YAML frontmatter dal corpo Markdown."""
    if not raw.startswith('---'):
        return {}, raw
    parts = raw.split('---', 2)
    if len(parts) < 3:
        return {}, raw
    try:
        front = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        front = {}
    return front, parts[2].strip()


def load_config() -> dict:
    """Carica _config.yml. Risultato cached per il ciclo di vita del processo."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config_path = os.path.join(CONTENT_ROOT, '_config.yml')
    if not os.path.exists(config_path):
        logger.warning(f"Help config not found: {config_path}")
        _config_cache = {}
        return _config_cache
    try:
        with open(config_path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        _config_cache = data.get('articles', {})
    except Exception as e:
        logger.error(f"Error loading help config: {e}")
        _config_cache = {}
    return _config_cache


def get_article(help_id: str) -> dict | None:
    """
    Carica, renderizza e cache-izza un articolo per help_id.

    Returns:
        dict con chiavi: title, html, help_id, module, tags
        None se help_id non trovato o file mancante
    """
    if help_id in _cache:
        return _cache[help_id]

    config = load_config()
    entry = config.get(help_id)
    if not entry:
        return None

    file_path = os.path.join(CONTENT_ROOT, entry['path'])
    if not os.path.exists(file_path):
        logger.warning(f"Help article file not found: {file_path}")
        return None

    try:
        with open(file_path, encoding='utf-8') as f:
            raw = f.read()
    except Exception as e:
        logger.error(f"Error reading help article {file_path}: {e}")
        return None

    front, body = _parse_frontmatter(raw)
    html = markdown.markdown(body, extensions=['extra', 'tables', 'fenced_code'])
    html = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=False)

    result = {
        'title': front.get('title', help_id),
        'html': html,
        'raw': raw,
        'help_id': help_id,
        'module': entry.get('module', ''),
        'tags': front.get('tags', []),
    }
    _cache[help_id] = result
    return result


def save_article(help_id: str, content: str) -> dict:
    """
    Scrive il contenuto Markdown su disco e invalida la cache per help_id.

    Returns:
        L'articolo aggiornato (dict con title, html, raw, ...)
    Raises:
        ValueError se help_id non trovato in _config.yml
        IOError in caso di errore scrittura
    """
    config = load_config()
    entry = config.get(help_id)
    if not entry:
        raise ValueError(f"help_id '{help_id}' non trovato in _config.yml")
    file_path = os.path.join(CONTENT_ROOT, entry['path'])
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    _cache.pop(help_id, None)
    return get_article(help_id)


def list_articles() -> list[dict]:
    """
    Restituisce tutti gli articoli configurati, ordinati per modulo e titolo.
    Articoli con file mancante vengono saltati silenziosamente.
    """
    config = load_config()
    articles = []
    for help_id in config:
        article = get_article(help_id)
        if article:
            articles.append(article)
    return sorted(articles, key=lambda a: (a['module'], a['title']))


def clear_cache() -> None:
    """Svuota la cache in-memory (config + articoli)."""
    global _cache, _config_cache
    _cache = {}
    _config_cache = None
    logger.info("Help cache cleared")
