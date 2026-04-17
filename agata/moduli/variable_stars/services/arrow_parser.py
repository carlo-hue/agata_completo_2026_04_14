"""
arrow_parser.py - Utility per parsing Apache Arrow IPC stream

Funzioni helper per conversione:
- bytes raw → Arrow Table
- Python data → Arrow Table → IPC stream
- Lista sessioni standard → IPC stream (usato da data_routes e preview_routes)
"""

import numpy as np
import pyarrow as pa
import pyarrow.ipc as ipc

MAX_ARROW_STREAM_BYTES = 10 * 1024 * 1024  # 10 MB


def read_arrow_table(raw: bytes) -> pa.Table:
    """
    Legge tabella Arrow da bytes raw (IPC stream).

    Args:
        raw: Bytes del body della richiesta POST

    Returns:
        pa.Table: Tabella Arrow deserializzata

    Raises:
        ValueError: Se body vuoto, troppo grande, o formato non valido
    """
    if not raw:
        raise ValueError("Body richiesta vuoto")

    if len(raw) > MAX_ARROW_STREAM_BYTES:
        raise ValueError(
            f"Arrow stream troppo grande: {len(raw)} bytes (max {MAX_ARROW_STREAM_BYTES})"
        )

    # Deserializza Arrow IPC stream
    reader = ipc.open_stream(pa.BufferReader(raw))
    return reader.read_all()


def sessions_to_arrow_response(sessions: list) -> bytes:
    """
    Converte la lista sessioni standard dell'editor in un Arrow IPC stream.

    Formato sessioni in ingresso:
        [{"session_id": int, "session_name": str, "jd": ndarray, "mag": ndarray}, ...]

    Schema Arrow in uscita (invariato):
        - point_id:    int32
        - session_id:  int32
        - session_name: string
        - jd:          float64
        - mag:         float32

    Gestisce correttamente sessions=[] (ritorna tabella vuota con schema valido).
    """
    if sessions:
        jd_all, mag_all, sid_all, sname_all = [], [], [], []
        for s in sessions:
            n = len(s["jd"])
            jd_all.append(s["jd"])
            mag_all.append(s["mag"].astype(np.float32))
            sid_all.append(np.full(n, s["session_id"], dtype=np.int32))
            session_name_val = s.get("session_name", f"S{s['session_id']}")
            sname_all.append(np.full(n, session_name_val, dtype=object))

        jd = np.concatenate(jd_all).astype(np.float64)
        mag = np.concatenate(mag_all).astype(np.float32)
        session_id = np.concatenate(sid_all).astype(np.int32)
        session_name = np.concatenate(sname_all)
    else:
        jd = np.array([], dtype=np.float64)
        mag = np.array([], dtype=np.float32)
        session_id = np.array([], dtype=np.int32)
        session_name = np.array([], dtype=object)

    point_id = np.arange(jd.size, dtype=np.int32)

    table = pa.table({
        "point_id": pa.array(point_id),
        "session_id": pa.array(session_id),
        "session_name": pa.array(session_name),
        "jd": pa.array(jd),
        "mag": pa.array(mag),
    })
    return create_arrow_response(table)


def create_arrow_response(table: pa.Table, mimetype: str = "application/vnd.apache.arrow.stream") -> bytes:
    """
    Crea response Arrow IPC stream da tabella PyArrow.

    Args:
        table: Tabella PyArrow da serializzare
        mimetype: MIME type per response (default: Arrow stream)

    Returns:
        bytes: Buffer serializzato pronto per Response Flask
    """
    sink = pa.BufferOutputStream()
    with ipc.new_stream(sink, table.schema) as writer:
        writer.write_table(table)
    buf = sink.getvalue()
    return buf.to_pybytes()
