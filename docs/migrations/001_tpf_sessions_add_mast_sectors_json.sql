-- Aggiunge colonna mast_sectors_json ad agata_tpf_sessions
-- Salva il risultato della query MAST settori al momento del save sessione
-- per evitare re-query al restore.
ALTER TABLE public.agata_tpf_sessions
    ADD COLUMN IF NOT EXISTS mast_sectors_json JSONB;
