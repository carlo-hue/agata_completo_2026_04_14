# agata/admin/routes/saved_queries.py
"""
Saved Queries & Query Presets API

Endpoint per gestione query personali salvate e preset superuser.
"""
from flask import jsonify, request
from flask_login import login_required, current_user

from agata.moduli.admin import admin_bp
from agata.moduli.admin.decorators import admin_required, superuser_required
from agata.moduli.admin.services.saved_query_service import (
    list_user_queries, create_user_query, update_user_query, delete_user_query,
    list_presets, create_preset, update_preset, delete_preset,
)
from agata.db import SessionLocal


# =============================================================================
# QUERY PERSONALI
# =============================================================================

@admin_bp.route('/api/saved-queries', methods=['GET'])
@login_required
@admin_required('analyst')
def api_list_saved_queries():
    """Lista query salvate dell'utente corrente per un contesto."""
    context = request.args.get('context', 'stars_catalog')
    db = SessionLocal()
    try:
        queries = list_user_queries(db, current_user.id, context)
        return jsonify([{
            'id': q.id,
            'name': q.name,
            'description': q.description,
            'filter_params': q.filter_params,
            'is_default': q.is_default,
            'created_at': q.created_at.isoformat(),
            'updated_at': q.updated_at.isoformat(),
        } for q in queries])
    finally:
        db.close()


@admin_bp.route('/api/saved-queries', methods=['POST'])
@login_required
@admin_required('analyst')
def api_create_saved_query():
    """Salva una nuova query personale."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Nome obbligatorio'}), 422
    context = data.get('context', 'stars_catalog')
    filter_params = data.get('filter_params')
    if not isinstance(filter_params, dict):
        return jsonify({'error': 'filter_params deve essere un oggetto JSON'}), 422

    db = SessionLocal()
    try:
        q = create_user_query(
            db=db,
            user_id=current_user.id,
            context=context,
            name=name,
            filter_params=filter_params,
            description=data.get('description'),
        )
        return jsonify({'id': q.id, 'name': q.name}), 201
    finally:
        db.close()


@admin_bp.route('/api/saved-queries/<int:query_id>', methods=['PUT'])
@login_required
@admin_required('analyst')
def api_update_saved_query(query_id):
    """Aggiorna nome/descrizione/filtri di una query personale."""
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        q = update_user_query(
            db=db,
            query_id=query_id,
            user_id=current_user.id,
            name=data.get('name'),
            description=data.get('description'),
            filter_params=data.get('filter_params'),
            is_default=data.get('is_default'),
        )
        if not q:
            return jsonify({'error': 'Query non trovata o non autorizzato'}), 404
        return jsonify({'id': q.id, 'name': q.name})
    finally:
        db.close()


@admin_bp.route('/api/saved-queries/<int:query_id>', methods=['DELETE'])
@login_required
@admin_required('analyst')
def api_delete_saved_query(query_id):
    """Elimina una query personale."""
    db = SessionLocal()
    try:
        ok = delete_user_query(db, query_id, current_user.id)
        if not ok:
            return jsonify({'error': 'Query non trovata o non autorizzato'}), 404
        return jsonify({'ok': True})
    finally:
        db.close()


# =============================================================================
# PRESET (superuser)
# =============================================================================

@admin_bp.route('/api/query-presets', methods=['GET'])
@login_required
@admin_required('analyst')
def api_list_query_presets():
    """Lista preset visibili all'utente corrente per un contesto."""
    context = request.args.get('context', 'stars_catalog')
    is_superuser = current_user.role == 'superuser'
    db = SessionLocal()
    try:
        presets = list_presets(db, context, current_user.association_id, is_superuser)
        return jsonify([{
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'filter_params': p.filter_params,
            'association_id': p.association_id,
            'sort_order': p.sort_order,
            'created_at': p.created_at.isoformat(),
        } for p in presets])
    finally:
        db.close()


@admin_bp.route('/api/query-presets', methods=['POST'])
@login_required
@superuser_required
def api_create_query_preset():
    """Crea un nuovo preset (solo superuser)."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Nome obbligatorio'}), 422
    filter_params = data.get('filter_params')
    if not isinstance(filter_params, dict):
        return jsonify({'error': 'filter_params deve essere un oggetto JSON'}), 422

    db = SessionLocal()
    try:
        p = create_preset(
            db=db,
            context=data.get('context', 'stars_catalog'),
            name=name,
            filter_params=filter_params,
            created_by=current_user.id,
            description=data.get('description'),
            association_id=data.get('association_id') or None,
            sort_order=data.get('sort_order', 0),
        )
        return jsonify({'id': p.id, 'name': p.name}), 201
    finally:
        db.close()


@admin_bp.route('/api/query-presets/<int:preset_id>', methods=['PUT'])
@login_required
@superuser_required
def api_update_query_preset(preset_id):
    """Aggiorna un preset (solo superuser)."""
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        p = update_preset(
            db=db,
            preset_id=preset_id,
            name=data.get('name'),
            description=data.get('description'),
            filter_params=data.get('filter_params'),
            association_id=data.get('association_id'),
            is_active=data.get('is_active'),
            sort_order=data.get('sort_order'),
        )
        if not p:
            return jsonify({'error': 'Preset non trovato'}), 404
        return jsonify({'id': p.id, 'name': p.name})
    finally:
        db.close()


@admin_bp.route('/api/query-presets/<int:preset_id>', methods=['DELETE'])
@login_required
@superuser_required
def api_delete_query_preset(preset_id):
    """Elimina un preset (solo superuser)."""
    db = SessionLocal()
    try:
        ok = delete_preset(db, preset_id)
        if not ok:
            return jsonify({'error': 'Preset non trovato'}), 404
        return jsonify({'ok': True})
    finally:
        db.close()
