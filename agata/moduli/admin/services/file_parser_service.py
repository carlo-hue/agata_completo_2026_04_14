# agata/admin/services/file_parser_service.py
"""
File Parser Service

Funzioni pure per parsing file fotometrici CSV/TXT.
Supporta auto-detection colonne e vari formati temporali.

Estratto da routes/catalogs/file_upload.py per correggere
dipendenza invertita (catalog_import_service importava da routes).
"""
import io
import logging
import pandas as pd
from typing import Optional, Tuple, List

from agata.moduli.admin.services.catalog_common_service import normalize_time

logger = logging.getLogger(__name__)

# Nomi colonne comuni per auto-detection
TIME_COLUMN_ALIASES = ['hjd', 'jd', 'mjd', 'bjd', 'time', 'date', 't', 'epoch', 'btjd']
MAG_COLUMN_ALIASES = ['mag', 'magnitude', 'brightness', 'flux', 'm', 'vmag', 'rmag', 'gmag',
                      'mag_original', 'mag_detrended', 'imag', 'bmag']
ERR_COLUMN_ALIASES = ['mag_err', 'magerr', 'err', 'error', 'e_mag', 'sigma', 'uncertainty',
                      'mag_error', 'e_vmag', 'e_rmag']


def _detect_delimiter(sample_line: str) -> str:
    """
    Auto-detect delimiter da una linea di esempio.

    Args:
        sample_line: Linea di esempio dal file

    Returns:
        Carattere delimitatore
    """
    delimiters = [',', '\t', ';', ' ']
    counts = {d: sample_line.count(d) for d in delimiters}
    best = max(counts.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else ','


def _find_column(columns: List[str], aliases: List[str]) -> Optional[str]:
    """
    Trova colonna corrispondente agli alias.

    Args:
        columns: Lista nomi colonne nel file
        aliases: Lista alias da cercare

    Returns:
        Nome colonna trovata o None
    """
    columns_lower = [c.lower() for c in columns]
    for alias in aliases:
        if alias.lower() in columns_lower:
            idx = columns_lower.index(alias.lower())
            return columns[idx]
    return None


def _parse_file_content(
    content: str,
    time_col: Optional[str] = None,
    mag_col: Optional[str] = None,
    err_col: Optional[str] = None,
    time_format: str = 'hjd',
    delimiter: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Parse contenuto file in DataFrame standard.

    Args:
        content: Contenuto del file
        time_col: Nome colonna tempo (auto-detect se None)
        mag_col: Nome colonna magnitudine (auto-detect se None)
        err_col: Nome colonna errore (auto-detect se None)
        time_format: Formato tempo input
        delimiter: Delimitatore (auto-detect se None)

    Returns:
        Tuple (DataFrame con colonne [hjd, mag, mag_err], error_message)
    """
    try:
        # Rimuovi righe di commento
        lines = content.split('\n')
        clean_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
                clean_lines.append(line)

        if not clean_lines:
            return None, "Nessun dato valido nel file"

        cleaned_content = '\n'.join(clean_lines)

        # Auto-detect delimiter
        if delimiter is None:
            delimiter = _detect_delimiter(clean_lines[0] if clean_lines else "")

        # Parse CSV
        df = pd.read_csv(
            io.StringIO(cleaned_content),
            delimiter=delimiter,
            skipinitialspace=True
        )

        if df.empty:
            return None, "File vuoto"

        # Normalizza nomi colonne
        df.columns = [str(c).lower().strip() for c in df.columns]

        # Auto-detect colonne se non specificate
        if time_col is None:
            time_col = _find_column(df.columns, TIME_COLUMN_ALIASES)
            if time_col is None:
                return None, f"Colonna tempo non trovata. Colonne disponibili: {list(df.columns)}"
        else:
            time_col = time_col.lower().strip()

        if mag_col is None:
            mag_col = _find_column(df.columns, MAG_COLUMN_ALIASES)
            if mag_col is None:
                return None, f"Colonna magnitudine non trovata. Colonne disponibili: {list(df.columns)}"
        else:
            mag_col = mag_col.lower().strip()

        if err_col is None:
            err_col = _find_column(df.columns, ERR_COLUMN_ALIASES)
        elif err_col:
            err_col = err_col.lower().strip()

        # Verifica esistenza colonne
        if time_col not in df.columns:
            return None, f"Colonna tempo '{time_col}' non trovata"
        if mag_col not in df.columns:
            return None, f"Colonna magnitudine '{mag_col}' non trovata"

        # Costruisci DataFrame standard
        result_df = pd.DataFrame({
            'hjd': normalize_time(pd.to_numeric(df[time_col], errors='coerce'), time_format),
            'mag': pd.to_numeric(df[mag_col], errors='coerce'),
        })

        # Aggiungi errore se disponibile
        if err_col and err_col in df.columns:
            result_df['mag_err'] = pd.to_numeric(df[err_col], errors='coerce')

        # Rimuovi righe con valori non validi
        result_df = result_df.dropna(subset=['hjd', 'mag'])

        if result_df.empty:
            return None, "Nessun dato valido dopo il parsing"

        # Ordina per tempo
        result_df = result_df.sort_values('hjd').reset_index(drop=True)

        logger.info(f"File parsing: {len(result_df)} punti validi")

        return result_df, None

    except pd.errors.EmptyDataError:
        return None, "File vuoto o senza dati"
    except pd.errors.ParserError as e:
        return None, f"Errore parsing CSV: {str(e)}"
    except Exception as e:
        logger.error(f"Errore parsing file: {e}", exc_info=True)
        return None, str(e)
