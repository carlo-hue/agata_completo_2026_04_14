# agata/admin/routes/stars_catalog.py
"""
Stars Catalog Routes

Interfaccia admin per gestire le stelle nel catalogo locale (agata_star_photometry):
- Lista stelle raggruppate per Gaia ID
- Dettaglio stella con tutti i dati fotometrici
- Cancellazione dati stella
- Assegnazione stelle a associazioni (senza progetto)
- Creazione Project da stella assegnata

Workflow:
1. Superuser carica stelle -> dati in agata_star_photometry (bacino centrale)
2. Superuser assegna stella a associazione -> record in star_assignments
3. Admin vede stelle assegnate -> crea progetto quando decide di lavorarci
"""
from flask import render_template, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
import urllib.parse

from agata.moduli.admin import admin_bp
from agata.moduli.admin.decorators import admin_required, superuser_required, audit_action
from agata.auth_models import Association, Project, StarAssignment
from agata.auth_models.catalog_import import CatalogImport
from agata.db import SessionLocal
from agata.moduli.admin.services.slack_service import get_slack_service

import logging
logger = logging.getLogger(__name__)


# =============================================================================
# FILTER BUILDER - Configurazione colonne filtrabili
# =============================================================================

FILTERABLE_COLUMNS = {
    'gaia_id':            {'label': 'Gaia DR3 ID',    'type': 'text',    'sql': 's.gaia_id'},
    'total_points':       {'label': 'Punti Totali',   'type': 'integer', 'sql': 's.total_points'},
    'num_catalogs':       {'label': 'N. Cataloghi',   'type': 'integer', 'sql': 's.num_catalogs'},
    'catalogs':           {'label': 'Catalogo',       'type': 'csv_set', 'sql': 's.catalogs'},
    'min_mag':            {'label': 'Mag Min',        'type': 'float',   'sql': 's.min_mag'},
    'max_mag':            {'label': 'Mag Max',        'type': 'float',   'sql': 's.max_mag'},
    'is_known_variable':  {'label': 'Variabile Nota', 'type': 'boolean', 'sql': 's.is_known_variable'},
    'variable_types':     {'label': 'Tipo Variabile', 'type': 'csv_set', 'sql': 's.variable_types'},
    'is_assigned':        {'label': 'Assegnata',       'type': 'boolean', 'sql': '(s.num_assignments > 0)'},
    'association_id':     {'label': 'Associazione',   'type': 'csv_set',
                           'sql': "(SELECT STRING_AGG(xa.name, ',' ORDER BY xa.name) "
                                  "FROM agata_star_assignments xsa "
                                  "JOIN agata_associations xa ON xa.id = xsa.association_id "
                                  "WHERE xsa.gaia_id = s.gaia_id)"},
    'has_active_project': {'label': 'Ha Progetto',    'type': 'boolean', 'sql': 's.has_active_project'},
    'last_imported_at':   {'label': 'Data Import',    'type': 'date',    'sql': 's.last_imported_at'},
    'import_id':          {'label': 'Import ID',      'type': 'integer', 'sql': 's.latest_import_id'},
}

_VALID_OPS_BY_TYPE = {
    'text':    {'contains', 'not_contains', 'starts_with', 'equals', 'not_equals', 'is_empty', 'is_not_empty'},
    'integer': {'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte', 'is_empty', 'is_not_empty'},
    'float':   {'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte', 'is_empty', 'is_not_empty'},
    'boolean': {'is_true', 'is_false'},
    'csv_set': {'contains', 'not_contains'},
    'date':    {'equals', 'gt', 'gte', 'lt', 'lte'},
}


def _cast_value(val, col_type):
    if col_type == 'integer':
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0
    elif col_type == 'float':
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0
    return val


def parse_adv_filters(raw_str):
    """
    Parse 'adv_filters' URL parameter.
    Format: comma-separated tokens col:op:urlencoded_val
    Returns list of dicts: [{'col', 'op', 'val', 'type', 'sql'}, ...]
    Silently drops invalid/unknown tokens.
    """
    if not raw_str:
        return []
    result = []
    for token in raw_str.split(','):
        token = token.strip()
        if not token:
            continue
        # Split on first two colons only
        first = token.find(':')
        if first < 0:
            continue
        col = token[:first]
        rest = token[first + 1:]
        second = rest.find(':')
        if second < 0:
            op = rest
            val = ''
        else:
            op = rest[:second]
            val = urllib.parse.unquote(rest[second + 1:])

        if col not in FILTERABLE_COLUMNS:
            continue
        col_cfg = FILTERABLE_COLUMNS[col]
        if op not in _VALID_OPS_BY_TYPE.get(col_cfg['type'], set()):
            continue
        result.append({'col': col, 'op': op, 'val': val,
                       'type': col_cfg['type'], 'sql': col_cfg['sql']})
    return result


def build_adv_filter_clauses(adv_filters):
    """
    Build parameterized SQL WHERE clauses from parsed adv_filters.
    Returns (list_of_sql_strings, params_dict).
    col_sql comes from FILTERABLE_COLUMNS (trusted constant), never interpolated from user input.
    All user values are bound as :adv_p0, :adv_p1, ...
    """
    clauses = []
    params = {}
    for i, f in enumerate(adv_filters):
        col_sql = f['sql']
        op = f['op']
        val = f['val']
        pname = f'adv_p{i}'
        col_type = f['type']

        if op == 'contains' and col_type == 'csv_set':
            clauses.append(f":{pname} = ANY(STRING_TO_ARRAY(COALESCE({col_sql}, ''), ','))")
            params[pname] = val
        elif op == 'not_contains' and col_type == 'csv_set':
            clauses.append(f":{pname} != ALL(STRING_TO_ARRAY(COALESCE({col_sql}, ''), ','))")
            params[pname] = val
        elif op == 'contains':
            clauses.append(f"{col_sql} LIKE :{pname}")
            params[pname] = f'%{val}%'
        elif op == 'not_contains':
            clauses.append(f"{col_sql} NOT LIKE :{pname}")
            params[pname] = f'%{val}%'
        elif op == 'starts_with':
            clauses.append(f"{col_sql} LIKE :{pname}")
            params[pname] = f'{val}%'
        elif op == 'equals':
            clauses.append(f"{col_sql} = :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'not_equals':
            clauses.append(f"{col_sql} != :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'gt':
            clauses.append(f"{col_sql} > :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'gte':
            clauses.append(f"{col_sql} >= :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'lt':
            clauses.append(f"{col_sql} < :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'lte':
            clauses.append(f"{col_sql} <= :{pname}")
            params[pname] = _cast_value(val, col_type)
        elif op == 'is_empty':
            clauses.append(f"({col_sql} IS NULL OR {col_sql} = '')")
        elif op == 'is_not_empty':
            clauses.append(f"({col_sql} IS NOT NULL AND {col_sql} != '')")
        elif op == 'is_true':
            clauses.append(f"{col_sql} = 1")
        elif op == 'is_false':
            clauses.append(f"{col_sql} = 0")
    return clauses, params


# =============================================================================
# HELPER: agata_star Update Hooks
# =============================================================================


@admin_bp.route('/stars-catalog')
@login_required
@admin_required('analyst')
def stars_catalog_page():
    """
    Pagina principale catalogo stelle - queries agata_star for O(1) page loads.
    agata_star is a denormalized cache kept in sync by update hooks.
    """
    db: Session = SessionLocal()
    try:
        is_superuser = current_user.role == 'superuser'
        is_admin = current_user.role == 'admin'
        is_reviewer = current_user.role == 'reviewer'
        is_analyst = current_user.role == 'analyst'

        # === 1. Parse request parameters ===
        filter_association_id = None if is_superuser else current_user.association_id

        state_filter = request.args.get('state', 'all')
        date_filter = request.args.get('date_filter', 'all')
        project_filter = request.args.get('project_filter', 'all')
        catalog_filter = request.args.get('catalog', '')
        import_filter = request.args.get('import_id', '', type=str)
        gaia_search = request.args.get('gaia_id', '')
        sort_by = request.args.get('sort', 'import_id')
        sort_order = request.args.get('order', 'desc')
        variable_type_filter = request.args.get('variable_type', '')
        variable_status_filter = request.args.get('variable_status_filter', '')
        adv_filters_raw = request.args.get('adv_filters', '')
        adv_filters = parse_adv_filters(adv_filters_raw)
        page = request.args.get('page', 1, type=int)
        per_page = 50

        should_load_stars = True

        # Admin default: show assigned stars without project
        if is_admin and state_filter == 'all':
            state_filter = 'assigned'

        # === 2. Associations dropdown (superuser only) ===
        associations = []
        if is_superuser:
            associations = db.query(Association).filter(
                Association.is_active == True
            ).order_by(Association.name).all()

        # === 3. Build and execute main query ===
        stars = []
        total = 0
        all_catalogs = set()
        all_variable_types = set()

        if should_load_stars:
            # Build query parameters
            params = {
                'filter_assoc_id': filter_association_id,
                'state_filter': state_filter,
                'date_filter': date_filter,
                'catalog_filter': catalog_filter,
                'gaia_search': f'%{gaia_search}%' if gaia_search else '',
                'variable_type_filter': variable_type_filter,
                'variable_status': variable_status_filter,
                'sort_by': sort_by,
                'per_page': per_page,
                'offset': (page - 1) * per_page,
                'analyst_user_id': str(current_user.id) if is_analyst else None,
            }

            # Import filter: if set, restrict to gaia_ids with that catalog_import_id
            import_gaia_subquery = ""
            if import_filter:
                try:
                    import_id_int = int(import_filter)
                    params['import_filter_id'] = import_id_int
                    import_gaia_subquery = """
                        AND s.gaia_id IN (
                            SELECT source_id::text
                            FROM agata_star_photometry
                            WHERE catalog_import_id = :import_filter_id
                        )
                    """
                except ValueError:
                    pass

            # Association filter: which gaia_ids are visible to this user
            if is_analyst:
                # Analyst: only stars with projects assigned to them
                assoc_filter_clause = """
                    AND s.gaia_id IN (
                        SELECT gaia_id FROM agata_projects
                        WHERE assigned_to = :analyst_user_id
                          AND state != 'cancelled'
                          AND association_id = :filter_assoc_id
                    )
                """
            elif filter_association_id:
                # Admin/Reviewer/Superuser with assoc filter: only assigned stars
                assoc_filter_clause = """
                    AND s.gaia_id IN (
                        SELECT gaia_id FROM agata_star_assignments
                        WHERE association_id = :filter_assoc_id
                    )
                """
            else:
                # Superuser no assoc filter: all stars
                assoc_filter_clause = ""

            # State filter
            state_clause = {
                'all': "1=1",
                'unassigned': "s.num_assignments = 0",
                'assigned': "s.num_assignments > 0",
                'with_project': "EXISTS (SELECT 1 FROM agata_projects WHERE gaia_id = s.gaia_id AND state != 'cancelled')",
            }.get(state_filter, "1=1")

            # Date filter
            date_clause = {
                'all': "1=1",
                '24h': "s.last_imported_at >= NOW() - INTERVAL '1 day'",
                '7d': "s.last_imported_at >= NOW() - INTERVAL '7 days'",
            }.get(date_filter, "1=1")

            # Catalog filter
            catalog_clause = (":catalog_filter = ANY(STRING_TO_ARRAY(s.catalogs, ','))"
                              if catalog_filter else "1=1")

            # Gaia ID search
            gaia_clause = ("s.gaia_id LIKE :gaia_search"
                           if gaia_search else "1=1")

            # Variable type filter
            vtype_clause = (":variable_type_filter = ANY(STRING_TO_ARRAY(COALESCE(s.variable_types,''), ','))"
                            if variable_type_filter else "1=1")

            # Variable status filter
            vstatus_clause = {
                'known': "s.is_known_variable = 1",
                'unknown': "s.is_known_variable = 0",
            }.get(variable_status_filter, "1=1")

            # Sort ORDER BY
            sort_dir = "DESC" if sort_order == 'desc' else "ASC"
            # In PostgreSQL, use NULLS LAST to push NULLs to the bottom when descending
            nulls_clause = "NULLS LAST" if sort_order == 'desc' else "NULLS FIRST"
            sort_map = {
                'gaia_id': f"CAST(s.gaia_id AS BIGINT) {sort_dir}",
                'points': f"s.total_points {sort_dir}",
                'catalogs': f"s.num_catalogs {sort_dir}",
                'min_mag': f"s.min_mag {sort_dir}",
                'max_mag': f"s.max_mag {sort_dir}",
                'date': f"s.last_imported_at {sort_dir}",
                'updated_at': f"s.last_imported_at {sort_dir}",
                'import_id': f"s.latest_import_id {sort_dir} {nulls_clause}",
            }
            # Default sort: by latest_import_id DESC with NULLs last
            default_order = f"s.latest_import_id {sort_dir} {nulls_clause}"
            order_clause = sort_map.get(sort_by, default_order)

            # Advanced filter builder clauses
            adv_clauses, adv_params = build_adv_filter_clauses(adv_filters)
            params.update(adv_params)
            adv_sql_block = ('\n  AND '.join([''] + adv_clauses)) if adv_clauses else ''

            # === MAIN QUERY ===
            main_sql = text(f"""
                SELECT
                    s.gaia_id,
                    s.total_points,
                    s.num_catalogs,
                    s.catalogs,
                    s.min_hjd,
                    s.max_hjd,
                    s.min_mag,
                    s.max_mag,
                    s.last_imported_at,
                    s.latest_import_id,
                    s.is_known_variable,
                    s.variable_types,
                    s.catalog_matches,
                    s.num_assignments,
                    s.has_active_project,
                    (
                        SELECT STRING_AGG(
                            sa.id::text || ':' || sa.association_id::text || ':' ||
                            a.name || ':' || DATE(sa.assigned_at)::text,
                            '|'
                            ORDER BY sa.assigned_at
                        )
                        FROM agata_star_assignments sa
                        JOIN agata_associations a ON a.id = sa.association_id
                        WHERE sa.gaia_id = s.gaia_id
                          AND (CAST(:filter_assoc_id AS INTEGER) IS NULL OR sa.association_id = :filter_assoc_id)
                    ) AS assignments_packed,
                    p.id        AS project_id,
                    p.project_code,
                    p.state     AS project_state,
                    pa.name     AS project_association_name,
                    ci.search_type AS import_search_type,
                    ci.search_value AS import_search_value
                FROM agata_star s
                LEFT JOIN agata_projects p
                    ON p.gaia_id = s.gaia_id
                   AND (CAST(:filter_assoc_id AS INTEGER) IS NULL OR p.association_id = :filter_assoc_id)
                LEFT JOIN agata_associations pa ON pa.id = p.association_id
                LEFT JOIN agata_catalog_imports ci ON ci.id = s.latest_import_id
                WHERE {state_clause}
                  AND {date_clause}
                  AND {catalog_clause}
                  AND {gaia_clause}
                  AND {vtype_clause}
                  AND {vstatus_clause}
                  {assoc_filter_clause}
                  {import_gaia_subquery}
                  {adv_sql_block}
                ORDER BY {order_clause}
                LIMIT :per_page OFFSET :offset
            """)

            count_sql = text(f"""
                SELECT COUNT(*) as cnt
                FROM agata_star s
                WHERE {state_clause}
                  AND {date_clause}
                  AND {catalog_clause}
                  AND {gaia_clause}
                  AND {vtype_clause}
                  AND {vstatus_clause}
                  {assoc_filter_clause}
                  {import_gaia_subquery}
                  {adv_sql_block}
            """)

            raw_rows = db.execute(main_sql, params).fetchall()
            total = db.execute(count_sql, params).fetchone().cnt

            # === Parse rows into dicts ===
            STATE_LABELS = {
                'incoming': 'In arrivo',
                'available': 'Disponibile',
                'assigned': 'Assegnato',
                'in_review': 'In revisione',
                'submitted_aavso': 'Inviato AAVSO',
                'accepted_aavso': 'Accettato AAVSO',
                'rejected_aavso': 'Rifiutato AAVSO',
                'cancelled': 'Cancellato',
            }
            CLOSED_STATES = {'cancelled', 'rejected_aavso', 'accepted_aavso'}
            for row in raw_rows:
                # Parse assignments_packed: "id:assoc_id:assoc_name:date|..."
                all_assignments = []
                if row.assignments_packed:
                    for part in row.assignments_packed.split('|'):
                        chunks = part.split(':', 3)
                        if len(chunks) == 4:
                            all_assignments.append({
                                'id': int(chunks[0]),
                                'association_id': int(chunks[1]),
                                'association_name': chunks[2],
                                'assigned_at': chunks[3],
                            })

                catalogs_list = row.catalogs.split(',') if row.catalogs else []
                variable_types_list = [
                    t.strip() for t in (row.variable_types or '').split(',') if t.strip()
                ]
                catalog_matches_list = [
                    c.strip() for c in (row.catalog_matches or '').split(',') if c.strip()
                ]

                # can_create_project logic
                can_create_project = False
                if all_assignments and not row.project_id:
                    if is_superuser:
                        can_create_project = True
                    elif is_admin:
                        can_create_project = any(
                            a['association_id'] == filter_association_id
                            for a in all_assignments
                        )

                stars.append({
                    'gaia_id': row.gaia_id,
                    'total_points': row.total_points,
                    'num_catalogs': row.num_catalogs,
                    'catalogs': catalogs_list,
                    'min_hjd': row.min_hjd,
                    'max_hjd': row.max_hjd,
                    'min_mag': row.min_mag,
                    'max_mag': row.max_mag,
                    'last_data_date': row.last_imported_at,
                    'all_assignments': all_assignments,
                    'project_id': row.project_id,
                    'project_code': row.project_code,
                    'project_state': STATE_LABELS.get(row.project_state, row.project_state or ''),
                    'project_is_closed': row.project_state in CLOSED_STATES if row.project_state else False,
                    'project_association': row.project_association_name,
                    'import_info': {
                        'id': row.latest_import_id,
                        'search_type': row.import_search_type,
                        'search_value': row.import_search_value,
                    } if row.latest_import_id else None,
                    'import_ids': [row.latest_import_id] if row.latest_import_id else [],
                    'variable_types': variable_types_list,
                    'is_known_variable': bool(row.is_known_variable),
                    'catalog_matches': catalog_matches_list,
                    'can_create_project': can_create_project,
                    'can_self_assign': False,
                })
                all_catalogs.update(catalogs_list)
                all_variable_types.update(variable_types_list)

        stars_in_page = len({s['gaia_id'] for s in stars})

        # === 4. Available imports for dropdown ===
        available_imports = []
        if not is_analyst:
            try:
                available_imports = db.query(CatalogImport).filter(
                    CatalogImport.state == 'completed'
                ).order_by(CatalogImport.created_at.desc()).all()
            except Exception as e:
                logger.error(f"Errore nel recupero degli import: {e}")

        return render_template(
            'admin/stars_catalog/list.html',
            stars=stars,
            stars_in_page=stars_in_page,
            associations=associations,
            available_catalogs=sorted(list(all_catalogs if should_load_stars else [])),
            available_imports=available_imports,
            available_variable_types=sorted(list(all_variable_types if should_load_stars else [])),
            filter_association_id=filter_association_id,
            state_filter=state_filter,
            date_filter=date_filter,
            project_filter=project_filter,
            catalog_filter=catalog_filter,
            variable_type_filter=variable_type_filter,
            variable_status_filter=variable_status_filter,
            import_filter=import_filter,
            gaia_search=gaia_search,
            sort_by=sort_by,
            sort_order=sort_order,
            current_page=page,
            total_stars=total,
            per_page=per_page,
            is_superuser=is_superuser,
            is_admin=is_admin,
            should_load_stars=should_load_stars,
            is_analyst=is_analyst,
            adv_filters_raw=adv_filters_raw,
            adv_filters=adv_filters,
            filterable_columns={k: v for k, v in FILTERABLE_COLUMNS.items()
                                 if k != 'association_id' or is_superuser},
        )
    finally:
        db.close()

@admin_bp.route('/stars-catalog/<gaia_id>')
@login_required
@admin_required('analyst')
def star_detail(gaia_id):
    """
    Dettaglio singola stella con tutti i dati per catalogo.

    - Superuser: vede tutte le assegnazioni e progetti, può assegnare a nuove associazioni
    - Admin associazione: vede assegnazione e progetto della propria associazione
    - Analyst: vede progetti della propria associazione
    """
    db: Session = SessionLocal()
    try:
        is_superuser = current_user.role == 'superuser'
        is_admin = current_user.role == 'admin'

        # Verifica che la stella esista (e sia accessible)
        check_query = text("""
            SELECT COUNT(*) as cnt FROM agata_star_photometry
            WHERE source_id = :gaia_id
              AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
        """)
        check_params = {
            'gaia_id': gaia_id,
            'user_assoc_id': current_user.association_id if not is_superuser else None,
            'is_superuser': 1 if is_superuser else 0
        }
        result = db.execute(check_query, check_params).fetchone()
        if not result or result.cnt == 0:
            abort(404)

        # Dati per catalogo (filtra per association_id_owner)
        # Per superuser: include anche l'association_id_owner per mostrare chi ha caricato
        catalogs_query = text("""
            SELECT
                catalogo,
                association_id_owner,
                COUNT(*) as points,
                MIN(hjd) as min_hjd,
                MAX(hjd) as max_hjd,
                MIN(Vmag) as min_mag,
                MAX(Vmag) as max_mag,
                AVG(Vmag) as avg_mag
            FROM agata_star_photometry
            WHERE source_id = :gaia_id
              AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
            GROUP BY catalogo, association_id_owner
            ORDER BY points DESC
        """)

        catalog_params = {
            'gaia_id': gaia_id,
            'user_assoc_id': current_user.association_id if not is_superuser else None,
            'is_superuser': 1 if is_superuser else 0
        }
        catalogs_result = db.execute(catalogs_query, catalog_params)
        catalogs = []
        total_points = 0
        for row in catalogs_result:
            catalog_entry = {
                'name': row.catalogo,
                'points': row.points,
                'min_hjd': row.min_hjd,
                'max_hjd': row.max_hjd,
                'min_mag': row.min_mag,
                'max_mag': row.max_mag,
                'avg_mag': row.avg_mag,
            }

            # Se superuser: mostra quale associazione ha caricato (NULL = bacino centrale)
            if is_superuser and row.association_id_owner is not None:
                association = db.query(Association).filter(
                    Association.id == row.association_id_owner
                ).first()
                if association:
                    catalog_entry['owner_association'] = association.name
                    catalog_entry['owner_association_id'] = association.id
            elif is_superuser and row.association_id_owner is None:
                catalog_entry['owner_association'] = 'Bacino centrale'
                catalog_entry['owner_association_id'] = None

            catalogs.append(catalog_entry)
            total_points += row.points

        # Import associato - cerca prima via foreign key (catalog_import_id), poi via resolved_gaia_id
        import_ids_query = db.execute(
            text("SELECT DISTINCT catalog_import_id FROM agata_star_photometry WHERE source_id = :gaia_id AND catalog_import_id IS NOT NULL LIMIT 1"),
            {"gaia_id": gaia_id}
        ).fetchone()

        import_record = None
        if import_ids_query and import_ids_query[0]:
            import_record = db.query(CatalogImport).filter(
                CatalogImport.id == import_ids_query[0]
            ).first()

        # Fallback: cerca via resolved_gaia_id (per import vecchi senza foreign key)
        if not import_record:
            import_record = db.query(CatalogImport).filter(
                CatalogImport.resolved_gaia_id == str(gaia_id)
            ).order_by(CatalogImport.created_at.desc()).first()

        # Assegnazioni per questa stella
        assignments_query = db.query(StarAssignment).filter(
            StarAssignment.gaia_id == str(gaia_id)
        )

        if not is_superuser:
            assignments_query = assignments_query.filter(
                StarAssignment.association_id == current_user.association_id
            )

        assignments = assignments_query.order_by(StarAssignment.assigned_at.desc()).all()

        # Progetti ATTIVI associati (escludi cancellati)
        # Superuser vede TUTTI i progetti per questa stella
        # Admin/Analyst vedono solo i progetti della loro associazione
        active_projects_query = db.query(Project).filter(
            Project.gaia_id == str(gaia_id),
            Project.state != 'cancelled'
        )

        if not is_superuser:
            active_projects_query = active_projects_query.filter(
                Project.association_id == current_user.association_id
            )

        active_projects = active_projects_query.order_by(Project.created_at.desc()).all()

        # Progetti cancellati (storico)
        cancelled_projects_query = db.query(Project).filter(
            Project.gaia_id == str(gaia_id),
            Project.state == 'cancelled'
        )

        if not is_superuser:
            cancelled_projects_query = cancelled_projects_query.filter(
                Project.association_id == current_user.association_id
            )

        cancelled_projects = cancelled_projects_query.order_by(Project.created_at.desc()).all()

        # Associazioni per form assegnazione (solo superuser)
        # Escludi associazioni che hanno già un'assegnazione per questa stella
        associations = []
        if is_superuser:
            assigned_assoc_ids = [a.association_id for a in db.query(StarAssignment).filter(
                StarAssignment.gaia_id == str(gaia_id)
            ).all()]

            associations = db.query(Association).filter(
                Association.is_active == True,
                ~Association.id.in_(assigned_assoc_ids) if assigned_assoc_ids else True
            ).order_by(Association.name).all()

        # Can create project if:
        # - Admin: has assignment without project to their own association
        # - Superuser: has any assignment without project (can create for any association)
        can_create_project = False
        my_assignment = None
        if is_superuser:
            # Superuser can create if there are any assignments without a project
            assignments_without_project = db.query(StarAssignment).filter(
                StarAssignment.gaia_id == str(gaia_id),
                StarAssignment.project_id == None
            ).first()
            can_create_project = assignments_without_project is not None
        elif is_admin:
            my_assignment = db.query(StarAssignment).filter(
                StarAssignment.gaia_id == str(gaia_id),
                StarAssignment.association_id == current_user.association_id,
                StarAssignment.project_id == None
            ).first()
            can_create_project = my_assignment is not None

        return render_template(
            'admin/stars_catalog/detail.html',
            gaia_id=gaia_id,
            catalogs=catalogs,
            total_points=total_points,
            import_record=import_record,
            assignments=assignments,
            active_projects=active_projects,
            cancelled_projects=cancelled_projects,
            associations=associations,
            is_superuser=is_superuser,
            is_admin=is_admin,
            can_create_project=can_create_project,
            my_assignment=my_assignment
        )
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/<gaia_id>/delete', methods=['POST'])
@login_required
@superuser_required
def api_delete_star_data(gaia_id):
    """
    API: Cancella tutti i dati di una stella dal catalogo.

    Body JSON (opzionale):
    - catalogs: list[str] - cataloghi specifici da cancellare (default: tutti)

    Returns:
        JSON con success e count di record cancellati
    """
    data = request.get_json() or {}
    catalogs_to_delete = data.get('catalogs')  # None = tutti

    db: Session = SessionLocal()
    try:
        # Converti gaia_id
        try:
            source_id = int(gaia_id)
        except (ValueError, TypeError):
            return jsonify({'error': 'Gaia ID non valido'}), 400

        # Cancella i dati
        if catalogs_to_delete:
            # Cancella solo cataloghi specificati
            deleted_count = 0
            for catalog in catalogs_to_delete:
                delete_sql = text("""
                    DELETE FROM agata_star_photometry
                    WHERE source_id = :source_id AND catalogo = :catalogo
                """)
                result = db.execute(delete_sql, {'source_id': source_id, 'catalogo': catalog})
                deleted_count += result.rowcount
        else:
            # Cancella tutti i dati della stella
            delete_sql = text("""
                DELETE FROM agata_star_photometry WHERE source_id = :source_id
            """)
            result = db.execute(delete_sql, {'source_id': source_id})
            deleted_count = result.rowcount

        db.commit()

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cancellati {deleted_count} record'
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/bulk-assign', methods=['POST'])
@login_required
@superuser_required
@audit_action('stars_bulk_assigned', 'star_assignment')
def api_bulk_assign_stars():
    """
    API: Assegna multiple stelle a un'associazione (SENZA creare progetto).

    Il superuser assegna stelle alle associazioni. L'admin dell'associazione
    deciderà poi se creare progetti.

    Body JSON:
    - gaia_ids: list[str] - liste di Gaia ID da assegnare (required)
    - association_id: int - associazione target (required)
    - notes: str (opzionale)

    Returns:
        JSON con risultati assegnazione
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON richiesto'}), 400

    gaia_ids = data.get('gaia_ids')
    association_id = data.get('association_id')

    if not gaia_ids or not isinstance(gaia_ids, list) or len(gaia_ids) == 0:
        return jsonify({'error': 'gaia_ids è obbligatorio e deve essere una lista non vuota'}), 400
    if not association_id:
        return jsonify({'error': 'association_id è obbligatorio'}), 400

    try:
        association_id = int(association_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'association_id non valido'}), 400

    db: Session = SessionLocal()
    try:
        # Verifica associazione
        association = db.query(Association).filter(Association.id == association_id).first()
        if not association:
            return jsonify({'error': 'Associazione non trovata'}), 404

        successful = 0
        failed = []
        already_assigned = []

        for gaia_id in gaia_ids:
            try:
                # Verifica che la stella esista nel catalogo
                check_query = text("""
                    SELECT COUNT(*) as cnt FROM agata_star_photometry WHERE source_id = :gaia_id
                """)
                result = db.execute(check_query, {'gaia_id': gaia_id}).fetchone()
                if not result or result.cnt == 0:
                    failed.append(f'{gaia_id}: stella non trovata nel catalogo')
                    continue

                # Verifica che non esista già un'assegnazione per questa stella + associazione
                existing = db.query(StarAssignment).filter(
                    StarAssignment.gaia_id == str(gaia_id),
                    StarAssignment.association_id == association_id
                ).first()
                if existing:
                    already_assigned.append(gaia_id)
                    continue

                # Crea l'assegnazione
                assignment = StarAssignment(
                    gaia_id=str(gaia_id),
                    association_id=association_id,
                    assigned_by=current_user.id,
                    notes=data.get('notes')
                )
                db.add(assignment)
                successful += 1

            except Exception as e:
                failed.append(f'{gaia_id}: {str(e)}')

        db.commit()

        # Batch UPDATE agata_star num_assignments for all successfully assigned stars (best-effort)
        # Use separate session to avoid aborting main transaction
        try:
            assigned_gaia_ids = [
                str(gid) for gid in gaia_ids
                if str(gid) not in [f.split(':')[0] for f in failed]
            ]
            if assigned_gaia_ids:
                db2 = SessionLocal()
                try:
                    for gid in assigned_gaia_ids:
                        db2.execute(text("""
                            INSERT INTO agata_star (gaia_id, num_assignments, created_at, updated_at)
                            VALUES (:gid, 1, NOW(), NOW())
                            ON CONFLICT (gaia_id) DO UPDATE SET
                                num_assignments = (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = :gid),
                                updated_at = NOW()
                        """), {'gid': gid})
                    db2.commit()
                finally:
                    db2.close()
        except Exception as _e:
            logger.warning(f"agata_star bulk assign update failed: {_e}")

        response = {
            'success': True,
            'assigned': successful,
            'already_assigned': len(already_assigned),
            'failed': len(failed),
            'message': f'Assegnate {successful} stelle a {association.name}'
        }

        if failed:
            response['failed_details'] = failed
        if already_assigned:
            response['already_assigned_ids'] = already_assigned

        return jsonify(response), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


def _get_filtered_gaia_ids(filter_association_id, catalog_filter, import_filter, gaia_search):
    """
    Ricostruisce la lista di Gaia IDs basata sui filtri attuali.
    Usato da api_bulk_delete_stars() quando delete_mode == 'all_in_filter'.
    """
    db: Session = SessionLocal()
    try:
        # Stessa logica di stars_catalog_page() ma ritorna solo la lista di Gaia IDs
        gaia_ids = []

        # Se superuser, filtra per association se fornito
        if filter_association_id:
            assigned_gaia_ids = db.query(StarAssignment.gaia_id).filter(
                StarAssignment.association_id == filter_association_id
            ).all()
            gaia_ids_set = set(row.gaia_id for row in assigned_gaia_ids)
        else:
            gaia_ids_set = None  # Significa: TUTTE le stelle del bacino centrale

        # Costruisci WHERE clause
        import_where_clause = ""
        if import_filter:
            try:
                import_id = int(import_filter)
                import_where_clause = f" AND catalog_import_id = {import_id}"
            except ValueError:
                pass

        # Query base
        if gaia_ids_set is not None:
            placeholders = ','.join([f':gaia_{i}' for i in range(len(gaia_ids_set))])
            query_params = {f'gaia_{i}': gid for i, gid in enumerate(gaia_ids_set)}

            query = text(f"""
                SELECT DISTINCT source_id as gaia_id
                FROM agata_star_photometry
                WHERE source_id IN ({placeholders})
                  {import_where_clause}
            """)
            result = db.execute(query, query_params).fetchall()
        else:
            # Bacino centrale: TUTTE le stelle
            query = text(f"""
                SELECT DISTINCT source_id as gaia_id
                FROM agata_star_photometry
                WHERE association_id_owner IS NULL
                  {import_where_clause}
            """)
            result = db.execute(query).fetchall()

        gaia_ids = [str(row.gaia_id) for row in result]
        return gaia_ids
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/bulk-delete', methods=['POST'])
@login_required
@superuser_required
@audit_action('stars_bulk_deleted', 'catalog_import')
def api_bulk_delete_stars():
    """
    API: Cancella multiple stelle dal catalogo (solo bacino centrale).

    Deletes ALL photometric data (agata_star_photometry records) for specified Gaia IDs.
    Only superuser can delete. Stars with active projects/assignments are protected.

    Cascading deletes:
    - agata_star_assignments (orphan assignments only)
    - agata_catalog_attributes (cached Vizier data)
    - agata_star_photometry (main photometric data)

    Body JSON (delete_mode='selected'):
    - gaia_ids: list[str] - Gaia IDs da cancellare (required)
    - delete_mode: 'selected'

    Body JSON (delete_mode='all_in_filter'):
    - delete_mode: 'all_in_filter'
    - association_id: int (opzionale, per filtrare associazione)
    - import_id: str (opzionale, per filtrare import)
    - catalog: str (opzionale, per filtrare catalogo)
    - gaia_id: str (opzionale, per filtrare per Gaia ID specifico)

    Returns:
        JSON with deleted_count, failed_count, failed_details
    """
    from agata.auth_models.catalog_attribute import CatalogAttribute

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON richiesto'}), 400

    delete_mode = data.get('delete_mode')
    if delete_mode not in ['selected', 'all_in_filter']:
        return jsonify({'error': 'delete_mode deve essere "selected" o "all_in_filter"'}), 400

    # Raccogli Gaia IDs da cancellare
    if delete_mode == 'selected':
        gaia_ids = data.get('gaia_ids')
        if not gaia_ids or not isinstance(gaia_ids, list) or len(gaia_ids) == 0:
            return jsonify({'error': 'gaia_ids è obbligatorio per delete_mode="selected"'}), 400
    else:
        # delete_mode == 'all_in_filter'
        filter_association_id = data.get('association_id')
        import_filter = data.get('import_id', '')
        catalog_filter = data.get('catalog', '')
        gaia_search = data.get('gaia_id', '')

        gaia_ids = _get_filtered_gaia_ids(filter_association_id, catalog_filter, import_filter, gaia_search)
        if not gaia_ids:
            return jsonify({'error': 'Nessuna stella trovata con i filtri specificati'}), 400

    db: Session = SessionLocal()
    try:
        failed = []

        # === OPTIMIZED BATCH APPROACH (100x faster) ===
        # Convert Gaia IDs to proper types for batch queries
        gaia_ids_str = [str(gid) for gid in gaia_ids]
        gaia_ids_int = [int(gid) for gid in gaia_ids]

        # === STEP 1-2: BATCH Pre-screening (find protected stars) ===
        logger.info(f"Batch pre-screening {len(gaia_ids)} stars for protection...")

        # Single query: Find stars with active projects
        protected_by_project = set(
            row[0] for row in db.query(Project.gaia_id).filter(
                Project.gaia_id.in_(gaia_ids_str),
                Project.state != 'cancelled'
            ).all()
        )

        # Single query: Find stars with linked assignments
        protected_by_assignment = set(
            row[0] for row in db.query(StarAssignment.gaia_id).filter(
                StarAssignment.gaia_id.in_(gaia_ids_str),
                StarAssignment.project_id.isnot(None)
            ).all()
        )

        # Compute deletable set (no protection)
        protected = protected_by_project | protected_by_assignment
        deletable_ids = [gid for gid in gaia_ids_str if gid not in protected]
        deletable_ids_int = [int(gid) for gid in deletable_ids]

        # Record failed (protected stars)
        for gid in protected_by_project:
            failed.append(f'{gid}: progetto attivo')

        for gid in protected_by_assignment:
            if gid not in protected_by_project:  # Avoid duplicate errors
                failed.append(f'{gid}: assegnazione collegata a progetto')

        logger.info(f"Pre-screening complete: {len(deletable_ids)} deletable, {len(protected)} protected")

        # === STEP 3-6: BATCH Deletes (all in 3-4 queries) ===
        if deletable_ids and len(deletable_ids) > 0:
            logger.info(f"Starting batch deletion of {len(deletable_ids)} stars...")

            # Convert to tuple for SQL IN clause
            deletable_ids_tuple = tuple(deletable_ids)
            deletable_ids_int_tuple = tuple(deletable_ids_int)

            # BULK delete orphan assignments (single query)
            orphan_count = db.query(StarAssignment).filter(
                StarAssignment.gaia_id.in_(deletable_ids),
                StarAssignment.project_id.is_(None)
            ).delete(synchronize_session=False)

            # BULK delete catalog attributes (single query)
            attr_count = db.query(CatalogAttribute).filter(
                CatalogAttribute.gaia_id.in_(deletable_ids_int)
            ).delete(synchronize_session=False)

            # BATCH VAST check: Single query to get all orphan counts
            vast_results = db.execute(text("""
                SELECT gaia_source_id, COUNT(*) as cnt
                FROM agata_vast_results
                WHERE gaia_source_id IN :gids
                GROUP BY gaia_source_id
            """), {'gids': deletable_ids_int_tuple}).fetchall()

            for gaia_id, count in vast_results:
                if count > 0:
                    logger.warning(f"Deleting {gaia_id} will orphan {count} VAST result(s)")

            # BULK delete all photometric data (single query)
            result = db.execute(text("""
                DELETE FROM agata_star_photometry
                WHERE source_id IN :sources
            """), {'sources': deletable_ids_int_tuple})

            deleted_count = len(deletable_ids)
            points_deleted = result.rowcount

            logger.info(
                f"Batch deletion complete: {deleted_count} stars, "
                f"{points_deleted} photometric points, "
                f"{orphan_count} orphan assignments, "
                f"{attr_count} catalog attributes"
            )
        else:
            deleted_count = 0
            logger.info("No stars to delete (all protected)")

        # === HOOK H: Clean up agata_star for deleted gaia_ids (best-effort) ===
        if deletable_ids and len(deletable_ids) > 0:
            try:
                ph = ','.join([f':dg{i}' for i in range(len(deletable_ids))])
                ph_params = {f'dg{i}': gid for i, gid in enumerate(deletable_ids)}
                db.execute(text(f"DELETE FROM agata_star WHERE gaia_id IN ({ph})"), ph_params)
            except Exception as _e:
                logger.warning(f"agata_star cleanup after bulk delete failed: {_e}")

        db.commit()

        response = {
            'success': True,
            'deleted_count': deleted_count,
            'failed_count': len(failed),
            'message': f'Cancellate {deleted_count} stelle dal catalogo'
        }

        if failed:
            response['failed_details'] = failed

        return jsonify(response), 200

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass  # Ignore rollback errors
        error_msg = str(e)[:500]  # Limit error message to 500 chars
        logger.error(f"Bulk delete failed: {error_msg}", exc_info=True)
        return jsonify({'error': error_msg}), 500
    finally:
        try:
            db.close()
        except Exception:
            pass  # Ignore close errors


@admin_bp.route('/api/stars-catalog/<gaia_id>/assign', methods=['POST'])
@login_required
@superuser_required
@audit_action('star_assigned', 'star_assignment')
def api_assign_star_to_association(gaia_id):
    """
    API: Assegna stella a un'associazione (SENZA creare progetto).

    Il superuser assegna stelle alle associazioni. L'admin dell'associazione
    deciderà poi se creare un progetto.

    Body JSON:
    - association_id: int - associazione target (required)
    - notes: str (opzionale)

    Returns:
        JSON con assignment_id
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Body JSON richiesto'}), 400

    association_id = data.get('association_id')
    if not association_id:
        return jsonify({'error': 'association_id è obbligatorio'}), 400

    try:
        association_id = int(association_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'association_id non valido'}), 400

    db: Session = SessionLocal()
    try:
        # Verifica che la stella esista nel catalogo
        check_query = text("""
            SELECT COUNT(*) as cnt FROM agata_star_photometry WHERE source_id = :gaia_id
        """)
        result = db.execute(check_query, {'gaia_id': gaia_id}).fetchone()
        if not result or result.cnt == 0:
            return jsonify({'error': 'Stella non trovata nel catalogo'}), 404

        # Verifica che non esista già un'assegnazione per questa stella + associazione
        existing = db.query(StarAssignment).filter(
            StarAssignment.gaia_id == str(gaia_id),
            StarAssignment.association_id == association_id
        ).first()
        if existing:
            return jsonify({
                'error': f'Stella già assegnata a questa associazione'
            }), 400

        # Verifica associazione
        association = db.query(Association).filter(Association.id == association_id).first()
        if not association:
            return jsonify({'error': 'Associazione non trovata'}), 404

        # Crea l'assegnazione
        assignment = StarAssignment(
            gaia_id=str(gaia_id),
            association_id=association_id,
            assigned_by=current_user.id,
            notes=data.get('notes')
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)

        # UPDATE agata_star num_assignments (best-effort) - use separate session to avoid aborting main transaction
        try:
            db2 = SessionLocal()
            try:
                db2.execute(text("""
                    INSERT INTO agata_star (gaia_id, num_assignments, created_at, updated_at)
                    VALUES (:gid, 1, NOW(), NOW())
                    ON CONFLICT (gaia_id) DO UPDATE SET
                        num_assignments = (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = :gid),
                        updated_at = NOW()
                """), {'gid': str(gaia_id)})
                db2.commit()
            finally:
                db2.close()
        except Exception as _e:
            logger.warning(f"agata_star num_assignments update failed for {gaia_id}: {_e}")

        # Notifica Slack (best-effort) - opzionale - use separate session to avoid aborting main transaction
        try:
            slack_service = get_slack_service()
            if slack_service and slack_service.is_configured():
                db_slack = SessionLocal()
                try:
                    slack_service.notify_star_assigned(db_slack, assignment, association)
                finally:
                    db_slack.close()
        except Exception as slack_error:
            logger.warning(f"Notifica Slack fallita per assegnazione stella {gaia_id}: {slack_error}")

        return jsonify({
            'success': True,
            'assignment_id': assignment.id,
            'message': f'Stella {gaia_id} assegnata a {association.name}'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/<gaia_id>/create-project', methods=['POST'])
@login_required
@admin_required('admin')
@audit_action('project_created_from_assignment', 'project')
def api_create_project_from_assignment(gaia_id):
    """
    API: Crea Project AGATA da stella assegnata.

    L'admin può creare un progetto solo se:
    - La stella è assegnata alla sua associazione
    - Non esiste già un progetto attivo per questa stella nella sua associazione

    Body JSON (opzionale):
    - title: str

    Returns:
        JSON con project_id e project_code
    """
    from datetime import datetime

    data = request.get_json() or {}

    db: Session = SessionLocal()
    try:
        # Verifica che la stella sia assegnata all'associazione dell'admin
        assignment = db.query(StarAssignment).filter(
            StarAssignment.gaia_id == str(gaia_id),
            StarAssignment.association_id == current_user.association_id
        ).first()

        if not assignment:
            return jsonify({
                'error': 'Stella non assegnata alla tua associazione'
            }), 403

        # Verifica che non esista già un progetto attivo
        existing = db.query(Project).filter(
            Project.gaia_id == str(gaia_id),
            Project.association_id == current_user.association_id,
            Project.state != 'cancelled'
        ).first()
        if existing:
            return jsonify({
                'error': f'Progetto già esistente: {existing.project_code}'
            }), 400

        # Verifica associazione
        association = db.query(Association).filter(
            Association.id == current_user.association_id
        ).first()

        # Genera project_code
        year = datetime.utcnow().year
        count_query = text("""
            SELECT COUNT(*) + 1 as next_num
            FROM agata_projects
            WHERE project_code LIKE :pattern
        """)
        result = db.execute(count_query, {'pattern': f'AGATA-{year}-%'}).fetchone()
        next_num = result.next_num if result else 1
        project_code = f"AGATA-{year}-{next_num:03d}"

        # Crea il progetto in stato 'available' (pronto per assegnazione analyst)
        title = data.get('title') or f"Stella Gaia DR3 {gaia_id}"

        project = Project(
            project_code=project_code,
            title=title,
            gaia_id=str(gaia_id),
            association_id=current_user.association_id,
            state='available'  # Admin lo crea già disponibile
        )
        db.add(project)
        db.flush()

        # Collega assegnazione al progetto
        assignment.project_id = project.id
        db.commit()
        db.refresh(project)

        # UPDATE agata_star has_active_project (best-effort) - use separate session
        try:
            db2 = SessionLocal()
            try:
                db2.execute(text("""
                    UPDATE agata_star SET has_active_project = 1, updated_at = NOW()
                    WHERE gaia_id = :gid
                """), {'gid': str(gaia_id)})
                db2.commit()
            finally:
                db2.close()
        except Exception as _e:
            logger.warning(f"agata_star project flag update failed: {_e}")

        # Notifica Slack (best-effort) - use separate session to avoid aborting main transaction
        try:
            slack_service = get_slack_service()
            db_slack = SessionLocal()
            try:
                slack_service.notify_new_project(db_slack, project, association)
            finally:
                db_slack.close()
        except Exception as slack_error:
            logger.warning(f"Notifica Slack fallita per progetto {project_code}: {slack_error}")

        return jsonify({
            'success': True,
            'project_id': project.id,
            'project_code': project.project_code,
            'message': f'Creato progetto {project.project_code} - pronto per assegnazione'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/star-assignments/<int:assignment_id>', methods=['DELETE'])
@login_required
@superuser_required
@audit_action('star_assignment_deleted', 'star_assignment')
def api_delete_star_assignment(assignment_id):
    """
    API: Rimuove un'assegnazione stella.

    Solo superuser può rimuovere assegnazioni.
    Non è possibile rimuovere assegnazioni che hanno già un progetto.

    Returns:
        JSON con success
    """
    db: Session = SessionLocal()
    try:
        assignment = db.query(StarAssignment).filter(
            StarAssignment.id == assignment_id
        ).first()

        if not assignment:
            return jsonify({'error': 'Assegnazione non trovata'}), 404

        if assignment.project_id:
            return jsonify({
                'error': 'Impossibile rimuovere: assegnazione collegata a un progetto'
            }), 400

        gaia_id = assignment.gaia_id
        assoc_name = assignment.association.name

        db.delete(assignment)
        db.commit()

        # UPDATE agata_star: recount and update has_active_project (best-effort)
        try:
            db.execute(text("""
                UPDATE agata_star SET
                    num_assignments = (SELECT COUNT(*) FROM agata_star_assignments WHERE gaia_id = :gid),
                    has_active_project = (SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END
                                         FROM agata_projects WHERE gaia_id = :gid AND state != 'cancelled'),
                    updated_at = NOW()
                WHERE gaia_id = :gid
            """), {'gid': str(gaia_id)})
            db.commit()
        except Exception as _e:
            logger.warning(f"agata_star post-delete update failed for {gaia_id}: {_e}")

        return jsonify({
            'success': True,
            'message': f'Assegnazione rimossa per stella {gaia_id} da {assoc_name}'
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog')
@login_required
@admin_required('analyst')
def api_list_stars():
    """
    API: Lista stelle nel catalogo con filtri.

    Query params:
    - limit: numero risultati (default 100)
    - offset: offset per paginazione
    - search: cerca per Gaia ID

    Returns:
        JSON array di stelle
    """
    limit = min(int(request.args.get('limit', 100)), 500)
    offset = int(request.args.get('offset', 0))
    search = request.args.get('search', '')

    db: Session = SessionLocal()
    try:
        is_superuser = current_user.role == 'superuser'
        user_assoc_id = current_user.association_id if not is_superuser else None

        if search:
            query = text("""
                SELECT
                    source_id as gaia_id,
                    COUNT(*) as total_points,
                    COUNT(DISTINCT catalogo) as num_catalogs,
                    STRING_AGG(DISTINCT catalogo, ',') as catalogs
                FROM agata_star_photometry
                WHERE source_id IS NOT NULL AND source_id > 0
                  AND source_id::text LIKE :search
                  AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
                GROUP BY source_id
                ORDER BY total_points DESC
                LIMIT :limit OFFSET :offset
            """)
            result = db.execute(query, {
                'search': f'%{search}%',
                'limit': limit,
                'offset': offset,
                'user_assoc_id': user_assoc_id,
                'is_superuser': 1 if is_superuser else 0
            })
        else:
            query = text("""
                SELECT
                    source_id as gaia_id,
                    COUNT(*) as total_points,
                    COUNT(DISTINCT catalogo) as num_catalogs,
                    STRING_AGG(DISTINCT catalogo, ',') as catalogs
                FROM agata_star_photometry
                WHERE source_id IS NOT NULL AND source_id > 0
                  AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
                GROUP BY source_id
                ORDER BY total_points DESC
                LIMIT :limit OFFSET :offset
            """)
            result = db.execute(query, {
                'limit': limit,
                'offset': offset,
                'user_assoc_id': user_assoc_id,
                'is_superuser': 1 if is_superuser else 0
            })

        stars = []
        for row in result:
            stars.append({
                'gaia_id': str(row.gaia_id),
                'total_points': row.total_points,
                'num_catalogs': row.num_catalogs,
                'catalogs': row.catalogs.split(',') if row.catalogs else []
            })

        return jsonify(stars)

    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/field-values')
@login_required
@admin_required('analyst')
def api_field_values():
    """
    Restituisce i valori distinti per un campo filtrabile.
    Usato dal Filter Builder per popolare i dropdown di autocomplete.

    Query params:
    - field: chiave di FILTERABLE_COLUMNS (obbligatorio)
    - association_id: filtro associazione (opzionale, superuser only)

    Returns:
        JSON {"values": ["val1", "val2", ...]}
    """
    field = request.args.get('field', '')
    if field not in FILTERABLE_COLUMNS:
        return jsonify({'error': 'Campo non valido'}), 400

    col_cfg = FILTERABLE_COLUMNS[field]
    col_type = col_cfg['type']
    col_sql = col_cfg['sql']  # from trusted constant, safe to interpolate

    db: Session = SessionLocal()
    try:
        is_superuser = current_user.role == 'superuser'
        filter_association_id = request.args.get('association_id', type=int)
        if not is_superuser:
            filter_association_id = current_user.association_id

        if filter_association_id:
            assoc_where = """
                AND s.gaia_id IN (
                    SELECT gaia_id FROM agata_star_assignments
                    WHERE association_id = :fv_assoc_id
                )
            """
            assoc_params = {'fv_assoc_id': filter_association_id}
        else:
            assoc_where = ''
            assoc_params = {}

        if col_type == 'boolean':
            return jsonify({'values': ['1', '0']})

        elif field == 'association_id':
            q = text("SELECT name FROM agata_associations WHERE is_active = 1 ORDER BY name")
            rows = db.execute(q).fetchall()
            return jsonify({'values': [r.name for r in rows]})

        elif col_type == 'csv_set':
            q = text(f"""
                SELECT {col_sql} as val
                FROM agata_star s
                WHERE {col_sql} IS NOT NULL AND {col_sql} != ''
                {assoc_where}
                LIMIT 5000
            """)
            rows = db.execute(q, assoc_params).fetchall()
            values_set = set()
            for row in rows:
                for token in (row.val or '').split(','):
                    token = token.strip()
                    if token:
                        values_set.add(token)
            values = sorted(values_set)[:200]

        else:
            q = text(f"""
                SELECT DISTINCT {col_sql} as val
                FROM agata_star s
                WHERE {col_sql} IS NOT NULL
                {assoc_where}
                ORDER BY {col_sql}
                LIMIT 200
            """)
            rows = db.execute(q, assoc_params).fetchall()
            values = [str(row.val) for row in rows if row.val is not None]

        return jsonify({'values': values})

    except Exception as e:
        logger.error(f"api_field_values error field={field}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/api/stars-catalog/<gaia_id>/preview-data.arrow')
@login_required
@admin_required('analyst')
def preview_data_arrow(gaia_id):
    """
    Carica dati fotometrici campionati per il minigrafico preview.

    Query params:
    - max_points: numero massimo di punti da caricare (default 1000)

    Restituisce Arrow IPC stream con campi:
    - hjd: float64 - Julian Date
    - mag: float32 - magnitudine
    - catalogo: string - nome catalogo

    Campionamento server-side:
    - Se punti <= 500: carica tutti
    - Se punti 500-5000: carica il 50%
    - Se punti > 5000: carica il 10%
    """
    import pyarrow as pa

    db: Session = SessionLocal()
    try:
        is_superuser = current_user.role == 'superuser'
        max_points = request.args.get('max_points', 1000, type=int)

        # Verifica che l'utente possa accedere a questa stella
        check_query = text("""
            SELECT COUNT(*) as cnt FROM agata_star_photometry
            WHERE source_id = :gaia_id
              AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
        """)
        check_params = {
            'gaia_id': gaia_id,
            'user_assoc_id': current_user.association_id if not is_superuser else None,
            'is_superuser': 1 if is_superuser else 0
        }
        result = db.execute(check_query, check_params).fetchone()
        if not result or result.cnt == 0:
            return jsonify({'error': 'Stella non accessibile'}), 403

        # Carica dati fotometrici con limite e campionamento
        data_query = text("""
            SELECT hjd, vmag as mag, catalogo
            FROM agata_star_photometry
            WHERE source_id = :gaia_id
              AND (association_id_owner IS NULL OR association_id_owner = :user_assoc_id OR :is_superuser = 1)
            ORDER BY hjd
        """)

        data_params = {
            'gaia_id': gaia_id,
            'user_assoc_id': current_user.association_id if not is_superuser else None,
            'is_superuser': 1 if is_superuser else 0
        }

        rows = db.execute(data_query, data_params).fetchall()

        if not rows:
            # Ritorna tabella Arrow vuota
            table = pa.table({
                'hjd': pa.array([], type=pa.float64()),
                'mag': pa.array([], type=pa.float32()),
                'catalogo': pa.array([], type=pa.string())
            })
        else:
            # Campionamento server-side intelligente
            total_points = len(rows)

            if total_points <= 500:
                # Carica tutti
                sampling_percent = 100
                sampled_indices = list(range(total_points))
            elif total_points <= 5000:
                # Carica il 50%
                sampling_percent = 50
                step = 2
                sampled_indices = list(range(0, total_points, step))
            else:
                # Carica il 10%
                sampling_percent = 10
                step = max(10, total_points // max_points)
                sampled_indices = list(range(0, total_points, step))

            # Estrai dati campionati
            hjd_data = []
            mag_data = []
            catalog_data = []

            for idx in sampled_indices:
                if idx < total_points:
                    row = rows[idx]
                    hjd_data.append(float(row.hjd))
                    mag_data.append(float(row.mag) if row.mag is not None else 0.0)
                    catalog_data.append(str(row.catalogo))

            # Crea Arrow Table
            table = pa.table({
                'hjd': pa.array(hjd_data, type=pa.float64()),
                'mag': pa.array(mag_data, type=pa.float32()),
                'catalogo': pa.array(catalog_data, type=pa.string())
            })

        # Serializza a IPC stream binario
        sink = pa.BufferOutputStream()
        writer = pa.ipc.new_stream(sink, table.schema)
        writer.write_table(table)
        writer.close()

        # Ritorna come Response binaria
        from flask import Response
        return Response(
            sink.getvalue().to_pybytes(),
            mimetype='application/octet-stream',
            headers={'Content-Disposition': 'attachment; filename=preview.arrow'}
        )

    finally:
        db.close()
