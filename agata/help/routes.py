from flask import render_template, jsonify, abort, request
from flask_login import login_required, current_user

from agata.help import help_bp
from agata.help.service import get_article, list_articles, clear_cache, save_article


@help_bp.route('/')
@login_required
def help_center():
    articles = list_articles()
    return render_template('center.html', articles=articles)


@help_bp.route('/article/<path:help_id>')
@login_required
def article_page(help_id):
    article = get_article(help_id)
    if not article:
        abort(404)
    return render_template('article.html', article=article)


@help_bp.route('/api/article/<path:help_id>', methods=['GET'])
@login_required
def api_article(help_id):
    """Restituisce titolo + HTML renderizzato per il pannello offcanvas (AJAX)."""
    article = get_article(help_id)
    if not article:
        return jsonify({'error': 'Article not found'}), 404
    return jsonify({'title': article['title'], 'html': article['html'], 'raw': article['raw']})


@help_bp.route('/api/article/<path:help_id>', methods=['PUT'])
@login_required
def api_save_article(help_id):
    """Salva il contenuto Markdown di un articolo. Solo superuser."""
    if current_user.role != 'superuser':
        return jsonify({'error': 'Non autorizzato'}), 403
    data = request.get_json() or {}
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'error': 'Contenuto vuoto'}), 400
    try:
        article = save_article(help_id, content)
        return jsonify({'success': True, 'title': article['title'], 'html': article['html']})
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@help_bp.route('/api/cache/clear', methods=['POST'])
@login_required
def api_clear_cache():
    """Invalida la cache in-memory. Solo superuser."""
    if current_user.role != 'superuser':
        return jsonify({'error': 'Forbidden'}), 403
    clear_cache()
    return jsonify({'status': 'ok', 'message': 'Cache svuotata'})
