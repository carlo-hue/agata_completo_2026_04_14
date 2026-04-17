#!/usr/bin/env python3
"""
enrich_csv_from_vizier.py

Script una-tantum per arricchire cataloghi_gvt.csv con metadati Vizier.

Per ogni riga del CSV con `descrizione` o `unita` vuote, interroga Vizier
per recuperare automaticamente:
  - descrizione della colonna (col.info.description)
  - unità di misura (col.unit)
  - UCD (Unified Content Descriptor)

Non sovrascrive i valori già valorizzati a mano nel CSV.

Uso:
    cd /var/www/astrogen
    python scripts/enrich_csv_from_vizier.py

    # Solo preview senza modificare il CSV:
    python scripts/enrich_csv_from_vizier.py --dry-run

    # Forza aggiornamento anche dei campi già valorizzati:
    python scripts/enrich_csv_from_vizier.py --overwrite
"""

import argparse
import csv
import sys
import time
from pathlib import Path

# Aggiunge la root del progetto al path per importare le dipendenze Flask se necessario
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from astroquery.vizier import Vizier
    import astropy.units as u
except ImportError:
    print("ERRORE: astroquery non installato. Esegui: pip install astroquery")
    sys.exit(1)

CSV_PATH = ROOT / "agata" / "catalog" / "cataloghi_gvt.csv"
DELAY_SECONDS = 0.5   # pausa tra query Vizier per non sovraccaricare il server


def fetch_column_metadata(catalog_id: str, column_name: str) -> dict:
    """
    Interroga Vizier per ottenere i metadati di una colonna specifica.
    Restituisce {'descrizione': str, 'unita': str, 'ucd': str} oppure None se fallisce.
    """
    try:
        # Usa una query per oggetto arbitrario con 1 risultato per ottenere la struttura della tabella
        v = Vizier(columns=[column_name], row_limit=1)
        v.TIMEOUT = 20

        # query_constraints con wildcard per ottenere almeno una riga (e quindi i metadati)
        tables = v.query_constraints(catalog=catalog_id)

        if not tables or len(tables) == 0:
            return None

        table = tables[0]
        if column_name not in table.colnames:
            # Prova con la prima tabella disponibile
            return None

        col = table[column_name]
        descrizione = (col.info.description or '').strip()
        unita = str(col.unit).strip() if col.unit else ''
        # Pulisce "dimensionless_unscaled" che astropy usa per grandezze adimensionali
        if unita in ('', 'None', '--', 'dimensionless_unscaled'):
            unita = ''
        ucd = (col.meta.get('ucd') or '').strip()

        return {'descrizione': descrizione, 'unita': unita, 'ucd': ucd}

    except Exception as exc:
        return {'error': str(exc)}


def run(dry_run: bool = False, overwrite: bool = False):
    if not CSV_PATH.exists():
        print(f"ERRORE: CSV non trovato: {CSV_PATH}")
        sys.exit(1)

    # Leggi tutte le righe
    with open(CSV_PATH, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        fieldnames = reader.fieldnames or []
        rows = [dict(row) for row in reader]

    # Assicura che le colonne esistano
    for col in ('descrizione', 'unita', 'ucd'):
        if col not in fieldnames:
            fieldnames.append(col)
            for row in rows:
                row.setdefault(col, '')

    print(f"CSV caricato: {len(rows)} righe, {len(fieldnames)} colonne")
    print(f"Modalità: {'DRY RUN (nessuna modifica)' if dry_run else 'SCRITTURA'}")
    print(f"Sovrascrittura: {'Sì' if overwrite else 'No (solo campi vuoti)'}")
    print()

    updated = 0
    skipped = 0
    errors = 0

    # Raggruppa per (catalogo, attributo) per evitare query duplicate
    seen: dict = {}  # (catalog_id, attr) -> metadata

    for i, row in enumerate(rows, start=1):
        catalog_id = row.get('catalogo', '').strip()
        attr = row.get('attributi', '').strip()

        if not catalog_id or not attr:
            continue

        needs_descrizione = overwrite or not row.get('descrizione', '').strip()
        needs_unita = overwrite or not row.get('unita', '').strip()

        if not needs_descrizione and not needs_unita:
            skipped += 1
            continue

        key = (catalog_id, attr)
        if key not in seen:
            print(f"[{i:3d}/{len(rows)}] Query Vizier: {catalog_id} / {attr} ...", end=' ', flush=True)
            meta = fetch_column_metadata(catalog_id, attr)
            seen[key] = meta
            time.sleep(DELAY_SECONDS)
        else:
            meta = seen[key]

        if meta is None:
            print("❌ nessuna risposta")
            errors += 1
            continue

        if 'error' in meta:
            print(f"❌ {meta['error']}")
            errors += 1
            continue

        changes = []
        if needs_descrizione and meta['descrizione']:
            if not dry_run:
                row['descrizione'] = meta['descrizione']
            changes.append(f"descrizione='{meta['descrizione']}'")

        if needs_unita and meta['unita']:
            if not dry_run:
                row['unita'] = meta['unita']
            changes.append(f"unita='{meta['unita']}'")

        # Salva UCD anche se non era nella lista originale
        if meta.get('ucd') and not row.get('ucd', '').strip():
            if not dry_run:
                row['ucd'] = meta['ucd']
            changes.append(f"ucd='{meta['ucd']}'")

        if changes:
            print(f"✅ {', '.join(changes)}")
            updated += 1
        else:
            print("— nessun nuovo dato")
            skipped += 1

    print()
    print(f"Riepilogo: {updated} righe aggiornate, {skipped} saltate, {errors} errori")

    if not dry_run and updated > 0:
        # Scrivi il CSV aggiornato
        with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';',
                                    quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ CSV salvato: {CSV_PATH}")
    elif dry_run:
        print("(Dry run: nessuna modifica apportata)")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Arricchisce cataloghi_gvt.csv con metadati Vizier')
    parser.add_argument('--dry-run', action='store_true',
                        help='Mostra cosa verrebbe modificato senza scrivere il CSV')
    parser.add_argument('--overwrite', action='store_true',
                        help='Sovrascrive anche i campi già valorizzati a mano')
    args = parser.parse_args()

    run(dry_run=args.dry_run, overwrite=args.overwrite)
