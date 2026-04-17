"""
Flask routes per catalog blueprint
Wrappa il modulo catalog esistente per esposizione HTTP
"""
from flask import request, jsonify
from flask_login import login_required, current_user
from agata.moduli.admin.decorators import admin_required

from . import catalog_bp
from .api.routes import post_query
from .services.query_service import QueryService
from .repositories.registry_repo import InMemoryRegistryRepo
from .repositories.cache_repo import InMemoryCacheRepo
from .repositories.events_repo import InMemoryEventsRepo
from .repositories.db_cache_repo import DBCacheRepo
from .repositories.catalog_registry_generated import apply_registry_to_repo

# Singleton instances (in-memory, per-process)
_registry_repo = InMemoryRegistryRepo()
_cache_repo = InMemoryCacheRepo()
_db_cache_repo = DBCacheRepo()  # Persistent DB cache
_events_repo = InMemoryEventsRepo()

# Carica cataloghi da CSV al primo import del modulo
apply_registry_to_repo(_registry_repo)

# Service singleton (with DB cache)
_query_service = QueryService(
    registry_repo=_registry_repo,
    cache_repo=_cache_repo,
    db_cache_repo=_db_cache_repo,
    events_repo=_events_repo
)


@catalog_bp.route('/api/db-attributes', methods=['GET'])
@login_required
@admin_required('analyst')
def api_db_attributes():
    """
    GET /agata/catalog/api/db-attributes?gaia_id=<id>&context=<optional>

    Legge attributi direttamente dal DB cache, senza query a Vizier.
    Utile per mostrare dati già disponibili nel tab cataloghi.

    Query params:
    - gaia_id: Gaia source ID (required)
    - context: Contesto opzionale (se omesso, ritorna tutti i contesti)

    Returns:
    {
        "gaia_id": str,
        "from_db": true,
        "has_data": bool,
        "fetched_at_latest": str | null,
        "results_by_context": {
            "identificativi": [
                {
                    "catalog_id": "I/305/out",
                    "catalog_label": "GSC 2.3",
                    "status": "db_cache",
                    "attributes": {
                        "GSC2.3": "value1",
                        "Umag": "value2"
                    },
                    "attribute_descriptions": {},
                    "fetched_at": "2026-04-10T..."
                }
            ]
        }
    }
    """
    gaia_id = request.args.get('gaia_id')
    context_filter = request.args.get('context')  # Optional filter

    if not gaia_id:
        return jsonify({"error": "gaia_id required"}), 400

    try:
        # Query all CatalogAttribute records for this gaia_id
        from agata.auth_models import CatalogAttribute
        from agata.db import SessionLocal
        from sqlalchemy import and_

        session = SessionLocal()
        try:
            # Get all attributes for this gaia_id
            records = session.query(CatalogAttribute).filter(
                CatalogAttribute.gaia_id == gaia_id
            ).all()

            if not records:
                return jsonify({
                    "gaia_id": gaia_id,
                    "from_db": True,
                    "has_data": False,
                    "fetched_at_latest": None,
                    "results_by_context": {}
                }), 200

            # Filter expired records
            active_records = [r for r in records if not r.is_expired]

            if not active_records:
                return jsonify({
                    "gaia_id": gaia_id,
                    "from_db": True,
                    "has_data": False,
                    "fetched_at_latest": None,
                    "results_by_context": {}
                }), 200

            # Group by context and catalog_id
            from collections import defaultdict
            grouped = defaultdict(lambda: defaultdict(dict))
            latest_fetched = None

            for record in active_records:
                # Skip if context filter applied and doesn't match
                if context_filter and record.contesto != context_filter:
                    continue

                context_key = record.contesto or "unknown"
                catalog_key = record.catalog_id

                grouped[context_key][catalog_key][record.attribute_name] = record.value

                # Track latest fetched_at
                if record.fetched_at:
                    if latest_fetched is None or record.fetched_at > latest_fetched:
                        latest_fetched = record.fetched_at

            # Get catalog labels from registry
            def get_catalog_label(catalog_id):
                try:
                    catalog_def = _registry_repo.get_catalog_definition(catalog_id)
                    return catalog_def.label if catalog_def else catalog_id
                except:
                    return catalog_id

            # Build results_by_context
            results_by_context = {}
            for context_name, catalogs in grouped.items():
                results_by_context[context_name] = []
                for catalog_id, attributes in catalogs.items():
                    results_by_context[context_name].append({
                        "catalog_id": catalog_id,
                        "catalog_label": get_catalog_label(catalog_id),
                        "status": "db_cache",
                        "attributes": attributes,
                        "attribute_descriptions": {},  # Could be enriched from registry if needed
                        "fetched_at": latest_fetched.isoformat() if latest_fetched else None
                    })

            return jsonify({
                "gaia_id": gaia_id,
                "from_db": True,
                "has_data": len(active_records) > 0,
                "fetched_at_latest": latest_fetched.isoformat() if latest_fetched else None,
                "results_by_context": results_by_context
            }), 200

        finally:
            session.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to load DB attributes: {str(e)}"}), 500


@catalog_bp.route('/api/query', methods=['POST'])
@login_required
@admin_required('analyst')
def api_query_catalogs():
    """
    POST /agata/catalog/api/query

    Body JSON:
    {
        "gaia_id": "6917570577208762624",   # Required
        "context": "identificativi",         # Optional, default "identificativi"
        "refresh": false,                    # Optional, superuser only
        "cone_radius": 5.0                   # Optional, cone search radius in arcsec (default: 5)
    }

    Returns:
    {
        "request_id": "uuid",
        "request_status": "complete" | "partial" | "failed",
        "context": "identificativi",
        "resolved_target": {
            "gaia_id": str,
            "gaia_release_used": "dr3" | "dr2",
            "ra_deg": float,
            "dec_deg": float
        },
        "results_by_context": {
            "identificativi": [
                {
                    "catalog_id": "I/355/gaiaedr3",
                    "status": "ok" | "no_match" | "error" | "timeout",
                    "from_cache": bool,
                    "needs_attention": bool,
                    "matches_count": int,
                    "payload": dict,
                    "fetched_at": str,
                    "expires_at": str,
                    "error_message": str | null
                }
            ]
        }
    }
    """
    data = request.get_json()
    gaia_id = data.get('gaia_id')
    context = data.get('context', 'identificativi')
    refresh = data.get('refresh', False)
    cone_radius = data.get('cone_radius')

    if not gaia_id:
        return jsonify({"error": "gaia_id required"}), 400

    # Validate cone_radius if provided
    if cone_radius is not None:
        try:
            cone_radius = float(cone_radius)
            if cone_radius <= 0:
                return jsonify({"error": "INVALID_CONE_RADIUS"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "INVALID_CONE_RADIUS"}), 400

    # Determina ruolo utente per permission check
    # current_user ha già le proprietà is_superuser, is_admin, role
    role = 'superuser' if current_user.is_superuser else 'admin' if current_user.is_admin else 'user'

    try:
        result = post_query(
            service=_query_service,
            gaia_id=str(gaia_id),
            context=context,
            role=role,
            refresh=refresh,
            max_matches=3,
            cone_radius=cone_radius
        )
        return jsonify(result), 200
    except ValueError as e:
        # Gaia ID not found, invalid context, etc.
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        # Unexpected errors (Vizier timeout, network issues, etc.)
        return jsonify({"error": f"Query failed: {str(e)}"}), 500
