# Schema Database AGATA - Documentazione di Riferimento

Questo documento descrive tutte le tabelle del database utilizzate dal progetto Flask AGATA.

**Database**: `catalogo` (MariaDB/MySQL)
**Generato**: 2026-01-31
**Aggiornato**: 2026-02-13 (convertiti campi support analysis da Float a String(100) per preservare origine catalogo)

---

## Indice

1. [Tabelle AGATA - Core](#tabelle-agata---core)
2. [Tabelle AGATA - Autenticazione e Sessioni](#tabelle-agata---autenticazione-e-sessioni)
3. [Tabelle AGATA - Progetti e Workflow](#tabelle-agata---progetti-e-workflow)
4. [Tabelle AGATA - Integrazione Slack](#tabelle-agata---integrazione-slack)
5. [Tabelle AGATA - Cataloghi e Importazioni](#tabelle-agata---cataloghi-e-importazioni)
6. [Tabelle AGATA - Sistema e Audit](#tabelle-agata---sistema-e-audit)
7. [Tabelle AGATA - Knowledge Base](#tabelle-agata---knowledge-base)
8. [Tabelle Legacy (Non AGATA)](#tabelle-legacy-non-agata)

---

## Tabelle AGATA - Core

### `agata_users`

Utenti del sistema AGATA con autenticazione OAuth 2.0.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | varchar(36) | NO | PRI | - | UUID utente |
| `email` | varchar(255) | NO | UNI | - | Email univoca utente |
| `name` | varchar(255) | YES | - | NULL | Nome |
| `surname` | varchar(255) | YES | - | NULL | Cognome |
| `avatar_url` | varchar(500) | YES | - | NULL | URL immagine profilo (da OAuth provider) |
| `provider` | varchar(50) | YES | MUL | NULL | Provider OAuth: google, slack, github |
| `provider_user_id` | varchar(255) | YES | - | NULL | ID utente nel provider OAuth |
| `is_internal` | tinyint(1) | YES | - | 0 | TRUE se email @astrogen.it |
| `association_id` | int(11) | YES | MUL | NULL | FK → agata_associations (NULL per superuser) |
| `role` | enum | YES | MUL | analyst | superuser, admin, reviewer, analyst, viewer |
| `is_active` | tinyint(1) | YES | MUL | 1 | Account attivo |
| `email_verified` | tinyint(1) | YES | - | 0 | Email verificata |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `last_login` | timestamp | YES | - | NULL | Ultimo accesso |
| `last_login_ip` | varchar(45) | YES | - | NULL | IP ultimo accesso |

**Relationships:**
- FK: `association_id` → `agata_associations.id`
- Inverse: `agata_oauth_tokens.user_id`, `agata_projects.assigned_to`, `agata_projects.reviewed_by`

**File Model:** [agata/auth_models/user.py](../agata/auth_models/user.py)

---

### `agata_associations`

Enti/Organizzazioni che utilizzano AGATA (AstroGen APS, partner, scuole, etc.).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID associazione |
| `name` | varchar(255) | NO | UNI | - | Nome completo associazione |
| `slug` | varchar(100) | NO | UNI | - | Identificatore URL-safe per namespace Slack |
| `type` | enum | YES | MUL | partner | internal, partner, school, individual |
| `is_active` | tinyint(1) | YES | MUL | 1 | Ente attivo nel sistema |
| `referente_email` | varchar(255) | YES | - | NULL | Email referente ente |
| `referente_name` | varchar(255) | YES | - | NULL | Nome referente ente |
| `slack_namespace` | varchar(50) | YES | - | NULL | Namespace per canali Slack (es: gvt → ag-gvt-coord) |
| `slack_enabled` | tinyint(1) | NO | - | 1 | Se False, disabilita integrazione Slack |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data aggiornamento |
| `settings` | longtext | YES | - | NULL | Configurazioni specifiche ente (JSON) |

**Relationships:**
- Inverse: `agata_users.association_id`, `agata_projects.association_id`, `agata_slack_channels.association_id`, `agata_star_assignments.association_id`

**File Model:** [agata/auth_models/association.py](../agata/auth_models/association.py)

---

## Tabelle AGATA - Autenticazione e Sessioni

### `agata_oauth_tokens`

Token OAuth 2.0 per integrazione con servizi esterni (Google, Slack, GitHub).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID token |
| `user_id` | varchar(36) | NO | MUL | - | FK → agata_users |
| `provider` | varchar(50) | NO | - | - | Provider OAuth (google, slack, github) |
| `access_token` | text | NO | - | - | Access token per API calls |
| `refresh_token` | text | YES | - | NULL | Refresh token per rinnovo |
| `token_type` | varchar(50) | YES | - | Bearer | Tipo token |
| `expires_at` | timestamp | YES | MUL | NULL | Scadenza access token |
| `scope` | text | YES | - | NULL | Scope autorizzati (spazio-separati) |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data aggiornamento |

**Relationships:**
- FK: `user_id` → `agata_users.id`

**File Model:** [agata/auth_models/oauth_token.py](../agata/auth_models/oauth_token.py)

---

### `agata_magic_link_tokens`

Token per autenticazione via Magic Link (link via email monouso con scadenza).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID token |
| `token` | varchar(100) | NO | UNI | - | Token URL-safe (43 caratteri) |
| `email` | varchar(255) | NO | MUL | - | Email destinatario |
| `user_id` | varchar(36) | YES | MUL | NULL | FK → agata_users (NULL per nuovi utenti) |
| `is_used` | tinyint(1) | YES | - | 0 | TRUE se già utilizzato |
| `created_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data creazione |
| `expires_at` | datetime | NO | - | - | Scadenza token |
| `used_at` | datetime | YES | - | NULL | Quando è stato utilizzato |
| `created_ip` | varchar(45) | YES | - | NULL | IP richiesta creazione |
| `used_ip` | varchar(45) | YES | - | NULL | IP utilizzo token |

**Relationships:**
- FK: `user_id` → `agata_users.id`

**File Model:** [agata/auth_models/magic_link_token.py](../agata/auth_models/magic_link_token.py)

---

### `agata_user_sessions`

Sessioni utente attive (gestione login/logout).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | varchar(64) | NO | PRI | - | Session ID |
| `user_id` | varchar(36) | NO | MUL | - | FK → agata_users |
| `session_data` | text | YES | - | NULL | Dati sessione serializzati |
| `ip_address` | varchar(45) | YES | - | NULL | IP utente |
| `user_agent` | text | YES | - | NULL | User agent browser |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `last_activity` | timestamp | YES | MUL | CURRENT_TIMESTAMP | Ultima attività |
| `expires_at` | timestamp | NO | MUL | - | Scadenza sessione |

**Relationships:**
- FK: `user_id` → `agata_users.id`

**File Model:** [agata/auth_models/user_session.py](../agata/auth_models/user_session.py)

---

## Tabelle AGATA - Progetti e Workflow

### `agata_projects`

Progetti AGATA - workflow analisi stelle variabili.

Stati workflow: `incoming` → `available` → `assigned` → `in_review` → `submitted_aavso` → `accepted_aavso`/`rejected_aavso` (o `cancelled` in qualsiasi momento)

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID progetto |
| `project_code` | varchar(50) | NO | UNI | - | Codice progetto univoco (es: AGATA-2024-001) |
| `gaia_id` | varchar(50) | NO | MUL | - | Gaia DR3 source ID |
| `tic_id` | int(11) | YES | - | NULL | TESS Input Catalog ID (cache da Gaia→TIC conversion) |
| `association_id` | int(11) | NO | MUL | - | FK → agata_associations |
| `title` | varchar(500) | YES | - | NULL | Descrizione breve stella/analisi |
| `source` | varchar(100) | YES | MUL | NULL | Fonte dati: ZTF, TESS, QLP, ASAS, etc. |
| `ra` | double | YES | - | NULL | Right Ascension (gradi) |
| `dec_deg` | double | YES | - | NULL | Declination (gradi) |
| `magnitude` | float | YES | - | NULL | Magnitudine media |
| `tic_magnitude` | float | YES | - | NULL | TESS magnitude (Tmag) da TIC |
| `spectral_class` | varchar(50) | YES | - | NULL | Classe spettrale (es: G2V, M3III) |
| `teff` | varchar(100) | YES | - | NULL | Temperatura effettiva (K) - salva anche origine catalogo, es: "5778 (Gaia DR3)" |
| `distance` | varchar(100) | YES | - | NULL | Distanza (pc) - salva anche origine catalogo, es: "10.5 (Gaia DR3)" |
| `luminosity` | varchar(100) | YES | - | NULL | Luminosità (L☉) o Magnitudine - salva anche origine catalogo, es: "1.0 (Gaia)" o "10.5 (Gaia mag)" |
| `radius` | varchar(100) | YES | - | NULL | Raggio (R☉) - salva anche origine catalogo, es: "1.0 (Gaia)" |
| `mass` | varchar(100) | YES | - | NULL | Massa (M☉) - salva anche origine catalogo, es: "1.0 (Gaia)" |
| `color_bv` | varchar(100) | YES | - | NULL | Indice di colore B-V - salva anche origine catalogo, es: "0.656 (Gaia)" |
| `color_bprp` | varchar(100) | YES | - | NULL | Indice di colore Gaia BP-RP - salva anche origine catalogo, es: "1.234 (Gaia)" |
| `variable_type` | varchar(100) | YES | - | NULL | Tipo di variabile proposto (es: RR Lyrae, Cepheid, EA, etc.) |
| `catalog_identifiers` | text | YES | - | NULL | Identificatori altri cataloghi (multi-riga): VSX, ASASSN, TYC, etc. |
| `variability_amplitude` | varchar(100) | YES | - | NULL | Ampiezza variabilità (mag) - salva anche origine catalogo, es: "0.5 (Gaia)" |
| `passband` | varchar(50) | YES | - | NULL | Passband fotometrico (es: V, G, R) |
| `period` | double | YES | - | NULL | Periodo variabilità (giorni) - per variabili periodiche |
| `epoch` | double | YES | - | NULL | Epoca massimo/minimo (JD) - per stelle periodiche |
| `state` | enum | NO | MUL | incoming | incoming, available, assigned, in_review, submitted_aavso, accepted_aavso, rejected_aavso, cancelled |
| `assigned_to` | varchar(36) | YES | MUL | NULL | FK → agata_users (analyst assegnato) |
| `assigned_at` | timestamp | YES | - | NULL | Data assegnazione |
| `reviewed_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (reviewer) |
| `reviewed_at` | timestamp | YES | - | NULL | Data revisione |
| `review_notes` | text | YES | - | NULL | Note revisore |
| `submitted_aavso_at` | timestamp | YES | - | NULL | Data invio AAVSO |
| `submitted_aavso_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (chi ha inviato ad AAVSO) |
| `aavso_response` | text | YES | - | NULL | Risposta AAVSO (JSON) |
| `aavso_accepted_at` | timestamp | YES | - | NULL | Data accettazione AAVSO |
| `aavso_rejected_at` | timestamp | YES | - | NULL | Data rifiuto AAVSO |
| `cancelled_at` | timestamp | YES | - | NULL | Data cancellazione |
| `cancelled_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (chi ha cancellato) |
| `cancellation_reason` | text | YES | - | NULL | Motivazione cancellazione |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data aggiornamento |
| `data` | longtext | YES | - | NULL | Dati aggiuntivi progetto (JSON) |
| `notes` | text | YES | - | NULL | Note generali sul progetto |

**Relationships:**
- FK: `association_id` → `agata_associations.id`
- FK: `assigned_to` → `agata_users.id`
- FK: `reviewed_by` → `agata_users.id`
- FK: `submitted_aavso_by` → `agata_users.id`
- FK: `cancelled_by` → `agata_users.id`
- Inverse: `agata_project_outputs.project_id`, `agata_project_science_data.project_id`, `agata_project_slack_threads.project_id`

**File Model:** [agata/auth_models/project.py](../agata/auth_models/project.py)

---

### `agata_project_science_data`

Dati scientifici strutturati per progetti AGATA (relazione 1:1 con Project).

Questi dati NON devono stare solo in Slack, ma in DB per query e reportistica.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID record |
| `project_id` | int(11) | NO | UNI | - | FK → agata_projects (relazione 1:1) |
| `dataset_drive_url` | varchar(500) | YES | - | NULL | Link Google Drive cartella/file dataset principale |
| `dataset_type` | varchar(100) | YES | - | NULL | Tipo dati: lightcurve, spectrum, photometry, timeseries, etc. |
| `dataset_uploaded_at` | timestamp | YES | - | NULL | Data caricamento dataset |
| `dataset_uploaded_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (chi ha caricato dataset) |
| `dataset_notes` | text | YES | - | NULL | Note sul dataset (qualità, problemi, filtri applicati) |
| `classification` | varchar(100) | YES | MUL | NULL | Classificazione variabile (es: RRab, EA, EB, Delta_Sct, DCEP) |
| `period_days` | double | YES | - | NULL | Periodo stimato in giorni |
| `period_uncertainty` | double | YES | - | NULL | Incertezza periodo (±giorni) |
| `epoch_jd` | double | YES | - | NULL | Epoca di riferimento (Julian Date) |
| `amplitude_mag` | float | YES | - | NULL | Ampiezza variazione in magnitudini |
| `confidence_level` | enum | YES | - | NULL | low, medium, high |
| `scientific_notes` | text | YES | - | NULL | Note analista: osservazioni, incertezze, problemi |
| `analysis_method` | text | YES | - | NULL | Metodo analisi (es: Lomb-Scargle periodogram, PDM, etc.) |
| `additional_data` | longtext | YES | - | NULL | Altri parametri scientifici (JSON) |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione record |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data ultimo aggiornamento |
| `updated_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (ultimo aggiornamento) |

**Relationships:**
- FK: `project_id` → `agata_projects.id` (UNIQUE - relazione 1:1)
- FK: `dataset_uploaded_by` → `agata_users.id`
- FK: `updated_by` → `agata_users.id`

**File Model:** [agata/auth_models/project_science_data.py](../agata/auth_models/project_science_data.py)

---

### `agata_project_outputs`

Output scientifici per progetti AGATA con versioning leggero.

Supporta immagini, fit, report, lightcurve, periodogrammi, phase plots.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID output |
| `project_id` | int(11) | NO | MUL | - | FK → agata_projects |
| `output_type` | enum | NO | MUL | - | image, fit, report, lightcurve, periodogram, phase_plot, other |
| `file_name` | varchar(255) | NO | - | - | Nome file originale |
| `file_url` | varchar(500) | NO | - | - | URL completo file (Google Drive, S3, storage interno, etc.) |
| `file_size_bytes` | bigint(20) | YES | - | NULL | Dimensione file in bytes |
| `mime_type` | varchar(100) | YES | - | NULL | MIME type (image/png, application/pdf, text/csv, etc.) |
| `description` | text | YES | - | NULL | Descrizione output (cosa rappresenta, contesto) |
| `tags` | varchar(500) | YES | - | NULL | Tag comma-separated (es: final, draft, v2, test) |
| `version` | int(11) | YES | - | 1 | Versione output (incrementa per modifiche successive) |
| `is_current` | tinyint(1) | YES | - | 1 | TRUE se è la versione corrente/attiva mostrata in UI |
| `replaces_output_id` | int(11) | YES | MUL | NULL | FK → agata_project_outputs (versione sostituita) |
| `uploaded_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (chi ha caricato) |
| `uploaded_at` | timestamp | YES | MUL | CURRENT_TIMESTAMP | Data/ora caricamento |

**Relationships:**
- FK: `project_id` → `agata_projects.id`
- FK: `replaces_output_id` → `agata_project_outputs.id`
- FK: `uploaded_by` → `agata_users.id`

**File Model:** [agata/auth_models/project_output.py](../agata/auth_models/project_output.py)

---

### `agata_star_assignments`

Assegnazione stelle a associazioni (prima che diventino progetti).

Workflow:
1. Superuser carica stelle → dati in agata_star_photometry (bacino centrale)
2. Superuser assegna stella a associazione → record in star_assignments
3. Admin vede stelle assegnate → crea progetto quando decide di lavorarci

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID assegnazione |
| `gaia_id` | varchar(50) | NO | MUL | - | Gaia DR3 source ID |
| `association_id` | int(11) | NO | MUL | - | FK → agata_associations |
| `assigned_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (superuser che ha assegnato) |
| `assigned_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data assegnazione |
| `notes` | text | YES | - | NULL | Note sull'assegnazione |
| `project_id` | int(11) | YES | MUL | NULL | FK → agata_projects (se è stato creato un progetto) |

**Indexes:**
- UNIQUE: `(gaia_id, association_id)` - una stella può essere assegnata una sola volta a un'associazione

**Relationships:**
- FK: `association_id` → `agata_associations.id`
- FK: `assigned_by` → `agata_users.id`
- FK: `project_id` → `agata_projects.id`

**File Model:** [agata/auth_models/star_assignment.py](../agata/auth_models/star_assignment.py)

---

## Tabelle AGATA - Integrazione Slack

### `agata_slack_channels`

Canali Slack workspace AGATA.

Schema AGATA: ogni associazione ha 2-3 canali fissi:
- `ag-{slug}-coord` (coordinamento)
- `ag-{slug}-lavori` (analisi available/assigned)
- `ag-{slug}-review` (revisione scientifica)

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID canale |
| `association_id` | int(11) | NO | MUL | - | FK → agata_associations |
| `channel_id` | varchar(50) | NO | UNI | - | Slack channel ID (es: C01234ABC) |
| `channel_name` | varchar(255) | NO | - | - | Nome canale completo (es: ag-gvt-coord) |
| `team_id` | varchar(50) | YES | - | NULL | Slack workspace ID |
| `channel_type` | enum | NO | MUL | - | coord, lavori, review |
| `created_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (creatore) |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `is_active` | tinyint(1) | YES | - | 1 | Canale attivo |
| `settings` | longtext | YES | - | NULL | Configurazioni canale-specifiche (JSON) |

**Relationships:**
- FK: `association_id` → `agata_associations.id`
- FK: `created_by` → `agata_users.id`

**File Model:** [agata/auth_models/slack_channel.py](../agata/auth_models/slack_channel.py)

---

### `agata_project_slack_threads`

Mapping tra progetti AGATA e contesti Slack (thread o canale dedicato).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID mapping |
| `project_id` | int(11) | NO | MUL | - | FK → agata_projects |
| `channel_id` | varchar(50) | NO | MUL | - | Slack channel ID |
| `thread_ts` | varchar(50) | NO | - | - | Thread timestamp |
| `message_ts` | varchar(50) | NO | - | - | Message timestamp |
| `slack_type` | enum | NO | MUL | thread | thread, channel |
| `last_message_ts` | varchar(50) | YES | - | NULL | Timestamp ultimo messaggio ricevuto |
| `last_message_preview` | text | YES | - | NULL | Preview testuale ultimo messaggio (cache per UI) |
| `current_state` | enum | NO | MUL | - | Stato denormalizzato (sync con agata_projects.state) |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data aggiornamento |
| `is_active` | tinyint(1) | YES | - | 1 | Thread attivo |

**Relationships:**
- FK: `project_id` → `agata_projects.id`

**File Model:** [agata/auth_models/project_slack_thread.py](../agata/auth_models/project_slack_thread.py)

---

## Tabelle AGATA - Cataloghi e Importazioni

### `agata_star_photometry`

Bacino centrale dati fotometrici da cataloghi esterni (TESS, ZTF, ASAS-SN, OGLE, etc.).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `index` | bigint(20) | YES | MUL | NULL | Indice progressivo punto fotometrico |
| `hjd` | double | YES | - | NULL | Heliocentric Julian Date |
| `Vmag` | double | YES | - | NULL | Magnitudine |
| `Source` | bigint(20) | YES | - | NULL | Gaia DR3 source ID |
| `catalogo` | text | YES | - | NULL | Nome catalogo di provenienza (TESS, ZTF, ASASSN, OGLE, etc.) |
| `association_id_owner` | int(11) | YES | MUL | NULL | FK → agata_associations (proprietario dati) |
| `catalog_import_id` | int(11) | YES | MUL | NULL | FK → agata_catalog_imports (sessione importazione) |

**Relationships:**
- FK: `association_id_owner` → `agata_associations.id`
- FK: `catalog_import_id` → `agata_catalog_imports.id`

**Note:** Questa tabella NON ha un model SQLAlchemy dichiarativo. Viene gestita tramite query SQL raw.

---

### `agata_catalog_imports`

Tracciamento sessioni di importazione da cataloghi esterni.

Workflow:
1. Superuser/admin cerca stella (pending → searching)
2. Sistema interroga cataloghi (searching → preview)
3. Preview risultati disponibili
4. Import selettivo (preview → importing → completed)
5. Creazione Project opzionale (link project_id)

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID importazione |
| `search_type` | enum | NO | - | - | coordinates, gaia_id, name, file |
| `search_value` | varchar(255) | NO | - | - | Valore ricerca (coordinate 'ra,dec' o identificativo) |
| `search_radius_arcsec` | float | YES | - | 5.0 | Raggio ricerca in arcsec (per ricerca per coordinate) |
| `resolved_ra` | double | YES | - | NULL | Right Ascension risolta (gradi) |
| `resolved_dec` | double | YES | - | NULL | Declination risolta (gradi) |
| `resolved_gaia_id` | varchar(50) | YES | MUL | NULL | Gaia DR3 source ID risolto |
| `catalogs_queried` | longtext | YES | - | NULL | Risultati per catalogo (JSON): {catalog: {status, count, error, band, time_range}} |
| `total_points_available` | int(11) | YES | - | 0 | Totale punti fotometrici disponibili |
| `total_points_imported` | int(11) | YES | - | 0 | Totale punti importati in agata_star_photometry |
| `selected_catalogs` | longtext | YES | - | NULL | Cataloghi selezionati per import (JSON): ['TESS', 'ZTF', ...] |
| `state` | enum | YES | MUL | pending | pending, searching, preview, importing, completed, failed, cancelled |
| `error_message` | text | YES | - | NULL | Messaggio errore in caso di fallimento |
| `requested_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (chi ha richiesto l'importazione) |
| `project_id` | int(11) | YES | MUL | NULL | FK → agata_projects (Project AGATA creato) |
| `target_association_id` | int(11) | YES | MUL | NULL | FK → agata_associations (associazione target per Project) |
| `created_at` | datetime | YES | - | CURRENT_TIMESTAMP | Data creazione richiesta |
| `completed_at` | datetime | YES | - | NULL | Data completamento importazione |
| `notes` | text | YES | - | NULL | Note sull'importazione |

**Relationships:**
- FK: `requested_by` → `agata_users.id`
- FK: `project_id` → `agata_projects.id`
- FK: `target_association_id` → `agata_associations.id`
- Inverse: `agata_star_photometry.catalog_import_id`

**File Model:** [agata/auth_models/catalog_import.py](../agata/auth_models/catalog_import.py)

---

### `agata_catalog_attributes`

Cache persistente degli attributi di catalogo per ogni stella. Salva i risultati delle query Vizier filtrati per gli attributi configurati nel CSV, evitando query ripetute. Supporta TTL (180 giorni default) per invalidazione automatica.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID record |
| `gaia_id` | varchar(50) | NO | MUL | - | Gaia DR3 source ID (parte della chiave composita) |
| `catalog_id` | varchar(100) | NO | MUL | - | Identificativo catalogo Vizier (es. I/305/out) |
| `attribute_name` | varchar(100) | NO | MUL | - | Nome attributo (es. GSC2.3, Vmag) |
| `contesto` | varchar(100) | YES | - | NULL | Contesto dal CSV (identificativi, magnitudine, etc.) |
| `reference` | text | YES | - | NULL | Riferimento bibliografico dal CSV |
| `value` | varchar(500) | YES | - | NULL | Valore attributo da Vizier |
| `value_type` | varchar(50) | YES | - | NULL | Tipo valore (string, float, int, identifier) |
| `ra_deg` | double | YES | - | NULL | Right Ascension della stella (gradi) |
| `dec_deg` | double | YES | - | NULL | Declination della stella (gradi) |
| `distance_arcsec` | float | YES | - | NULL | Distanza angolare dal match Vizier (qualità match) |
| `fetched_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data/ora query Vizier |
| `expires_at` | datetime | YES | - | NULL | Scadenza cache (NULL = nessuna scadenza) |

**Chiave composita logica:** (`gaia_id`, `catalog_id`, `attribute_name`)

**Relationships:**
- Nessuna FK dichiarata. `gaia_id` corrisponde logicamente a `agata_projects.gaia_id` e `agata_star_photometry.Source`.

**Note:**
- Solo gli attributi configurati nel CSV (`cataloghi_gvt.csv`) vengono salvati, evitando bloat.
- TTL default: 180 giorni. Dopo scadenza, la prossima query riesegue il fetch da Vizier.
- Superuser può forzare refresh con parametro `refresh=true` nella API.
- Cache a 2 livelli: in-memory (per processo) + DB (persistente).

**File Model:** [agata/auth_models/catalog_attribute.py](../agata/auth_models/catalog_attribute.py)
**Repository:** [agata/catalog/repositories/db_cache_repo.py](../agata/catalog/repositories/db_cache_repo.py)

---

## Tabelle AGATA - Sistema e Audit

### `agata_system_config`

Configurazioni di sistema (key-value store).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `config_key` | varchar(100) | NO | PRI | - | Chiave configurazione |
| `config_value` | text | YES | - | NULL | Valore configurazione |
| `config_type` | enum | YES | - | string | string, integer, boolean, json |
| `description` | text | YES | - | NULL | Descrizione configurazione |
| `is_public` | tinyint(1) | YES | MUL | 0 | Visibile agli utenti non-admin |
| `is_editable` | tinyint(1) | YES | - | 1 | Modificabile via UI |
| `created_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data creazione |
| `updated_at` | timestamp | YES | - | CURRENT_TIMESTAMP | Data aggiornamento |
| `updated_by` | varchar(36) | YES | MUL | NULL | FK → agata_users (ultimo aggiornamento) |

**Relationships:**
- FK: `updated_by` → `agata_users.id`

**File Model:** [agata/auth_models/system_config.py](../agata/auth_models/system_config.py)

---

### `agata_audit_log`

Log audit per compliance e debug - traccia tutte le azioni nel sistema.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | bigint(20) | NO | PRI | AUTO_INCREMENT | ID log |
| `user_id` | varchar(36) | YES | MUL | NULL | FK → agata_users |
| `user_email` | varchar(255) | YES | - | NULL | Email utente (denormalizzata per storico) |
| `association_id` | int(11) | YES | MUL | NULL | Associazione utente |
| `action` | varchar(100) | NO | MUL | - | Azione eseguita (es: project_assigned, slack_message_sent) |
| `entity_type` | varchar(50) | YES | MUL | NULL | Tipo entità (project, user, association, channel) |
| `entity_id` | varchar(255) | YES | - | NULL | ID entità modificata |
| `old_value` | text | YES | - | NULL | Stato precedente (JSON) |
| `new_value` | text | YES | - | NULL | Nuovo stato (JSON) |
| `description` | text | YES | - | NULL | Descrizione azione |
| `ip_address` | varchar(45) | YES | - | NULL | IP origine richiesta |
| `user_agent` | text | YES | - | NULL | User agent browser |
| `request_id` | varchar(36) | YES | - | NULL | Request ID per correlazione |
| `slack_payload` | longtext | YES | - | NULL | Payload Slack ridotto (JSON): {channel_id, thread_ts, message_ts, error} |
| `outcome` | enum | YES | MUL | success | success, error, partial |
| `error_message` | text | YES | - | NULL | Messaggio errore dettagliato se outcome != success |
| `created_at` | timestamp | YES | MUL | CURRENT_TIMESTAMP | Timestamp evento |

**Relationships:**
- FK: `user_id` → `agata_users.id`

**File Model:** [agata/auth_models/audit_log.py](../agata/auth_models/audit_log.py)

---

## Tabelle AGATA - Knowledge Base

### `agata_kb_search_history`

Cronologia delle ricerche effettuate nella Knowledge Base per analytics e miglioramento sistema.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | bigint(20) | NO | PRI | AUTO_INCREMENT | ID ricerca |
| `user_id` | varchar(36) | YES | MUL | NULL | FK → agata_users (NULL per ricerche anonime) |
| `query` | text | NO | - | - | Query di ricerca semantica |
| `results_count` | int(11) | NO | - | 0 | Numero risultati restituiti |
| `sources_used` | longtext | YES | - | NULL | Sorgenti usate (JSON array) |
| `clicked_result_id` | varchar(255) | YES | - | NULL | ID risultato cliccato dall'utente |
| `search_duration_ms` | int(11) | YES | - | NULL | Durata ricerca in millisecondi |
| `created_at` | timestamp | NO | MUL | CURRENT_TIMESTAMP | Timestamp ricerca |

**Relationships:**
- FK: `user_id` → `agata_users.id`

**File Model:** [agata/auth_models/kb_search_history.py](../agata/auth_models/kb_search_history.py)

**Utilizzo**: Tracking analytics per migliorare qualità ricerca e capire pattern utenti.

---

### `agata_kb_sync_status`

Stato sincronizzazione sorgenti dati Knowledge Base (email MBOX, documenti, etc.).

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID sync status |
| `source` | varchar(50) | NO | MUL | - | Tipo sorgente (mbox, google_drive, confluence, etc.) |
| `user_id` | varchar(36) | YES | MUL | NULL | FK → agata_users (proprietario sync) |
| `association_id` | int(11) | YES | MUL | NULL | FK → agata_associations (scope associazione) |
| `last_sync_at` | timestamp | YES | MUL | NULL | Timestamp ultima sincronizzazione completata |
| `total_items_indexed` | int(11) | NO | - | 0 | Totale item indicizzati da questa sorgente |
| `items_added_last_sync` | int(11) | NO | - | 0 | Nuovi item nell'ultima sincronizzazione |
| `sync_status` | enum | NO | MUL | never_synced | never_synced, syncing, completed, error |
| `error_message` | text | YES | - | NULL | Messaggio errore dettagliato se sync_status = error |
| `config` | longtext | YES | - | NULL | Configurazione specifica sorgente (JSON): path MBOX, credentials, filters |
| `created_at` | timestamp | NO | - | CURRENT_TIMESTAMP | Data creazione record |
| `updated_at` | timestamp | NO | - | CURRENT_TIMESTAMP | Data aggiornamento (auto-update) |

**Relationships:**
- FK: `user_id` → `agata_users.id`
- FK: `association_id` → `agata_associations.id`

**File Model:** [agata/auth_models/kb_sync_status.py](../agata/auth_models/kb_sync_status.py)

**Utilizzo**: Monitoring e scheduling sincronizzazione dati KB. Permette UI dashboard sync status.

---

## Tabelle AGATA - VAST Automation

### `agata_vast_jobs`

Tracciamento sessioni di elaborazione VAST per analisi automatica di immagini FITS.

Workflow:
1. Superuser crea job (pending)
2. Download immagini da Google Drive (downloading)
3. Validazione WCS con Astropy (validating)
4. Esecuzione VAST per fotometria (vast_analysis)
5. Cross-matching con cataloghi Gaia/Vizier/VSX (crossmatching)
6. Upload risultati a DB (uploading)
7. Completamento (completed) o errore (failed)

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID job |
| `job_code` | varchar(50) | NO | UNI | - | Codice univoco job (es. VAST-2026-0001) |
| `target_name` | varchar(255) | NO | - | - | Nome target astronomico |
| `target_ra` | double | YES | - | NULL | Right Ascension target (gradi) |
| `target_dec` | double | YES | - | NULL | Declination target (gradi) |
| `source_type` | enum | NO | - | - | drive_folder, local_path, url |
| `source_location` | text | NO | - | - | Google Drive folder ID, local path, o URL |
| `processing_params` | json | YES | - | NULL | Parametri VAST: {threshold, field_size, ...} |
| `state` | enum | NO | MUL | pending | pending, downloading, validating, vast_analysis, crossmatching, uploading, completed, failed, cancelled |
| `progress_pct` | int(11) | NO | - | 0 | Percentuale completamento (0-100) |
| `current_step` | varchar(255) | YES | - | NULL | Descrizione step attuale |
| `images_downloaded` | int(11) | NO | - | 0 | Numero immagini scaricate |
| `images_solved` | int(11) | NO | - | 0 | Numero immagini con WCS validato |
| `candidates_found` | int(11) | NO | - | 0 | Numero candidati variabili trovati |
| `stars_uploaded` | int(11) | NO | - | 0 | Numero stelle caricate nel database |
| `downloaded_files` | json | YES | - | NULL | Lista file scaricati: {paths: [...]} |
| `output_files` | json | YES | - | NULL | File output generati: {plots: [...], data: [...]} |
| `error_message` | text | YES | - | NULL | Messaggio errore in caso di fallimento |
| `retry_count` | int(11) | NO | - | 0 | Numero tentativi riavvio |
| `requested_by` | varchar(36) | NO | MUL | - | FK → agata_users (chi ha richiesto) |
| `project_id` | int(11) | YES | MUL | NULL | FK → agata_projects (Project creato) |
| `created_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data creazione job |
| `started_at` | datetime | YES | - | NULL | Data inizio elaborazione |
| `completed_at` | datetime | YES | - | NULL | Data completamento job |

**Relationships:**
- FK: `requested_by` → `agata_users.id` (CASCADE)
- FK: `project_id` → `agata_projects.id` (SET NULL)
- Inverse: `agata_vast_results.job_id`

**File Model:** [agata/auth_models/vast_job.py](../agata/auth_models/vast_job.py)

---

### `agata_vast_results`

Risultati individuali di candidati stelle variabili identificati da VAST.

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID risultato |
| `job_id` | int(11) | NO | MUL | - | FK → agata_vast_jobs (job padre) |
| `vast_id` | varchar(50) | YES | - | NULL | Identificativo VAST (es. out12345) |
| `gaia_source_id` | bigint(20) | YES | - | NULL | Gaia DR3 source ID (19 cifre) |
| `ra` | double | NO | - | - | Right Ascension (gradi) |
| `decl` | double | NO | - | - | Declination (gradi) |
| `mean_mag` | float | YES | - | NULL | Magnitudine media |
| `mag_err` | float | YES | - | NULL | Errore magnitudine |
| `std_dev` | float | YES | - | NULL | Deviazione standard magnitudini |
| `num_observations` | int(11) | YES | - | NULL | Numero osservazioni |
| `variability_index` | float | YES | - | NULL | Indice variabilità |
| `chi_squared` | float | YES | - | NULL | Chi-quadrato fit |
| `period` | float | YES | - | NULL | Periodo rilevato (giorni) |
| `variability_indices` | json | YES | - | NULL | Tutti i 31 indici VAST come JSON dict |
| `x_pix` | float | YES | - | NULL | Coordinata X pixel nel reference frame |
| `y_pix` | float | YES | - | NULL | Coordinata Y pixel nel reference frame |
| `is_valid` | tinyint(1) | NO | - | 1 | False per FRACTION_OF_FAINTEST/BRIGHTEST |
| `is_known_variable` | tinyint(1) | NO | - | 0 | True se match in VSX o Gaia variability |
| `variable_type` | varchar(100) | YES | - | NULL | Tipo variabile da VSX/Gaia |
| `catalog_matches` | varchar(255) | YES | - | NULL | Cataloghi con match (Gaia,AAVSO,Atlas) |
| `vmag` | float | YES | - | NULL | V magnitude calcolata da Gaia Gmag+BP-RP |
| `candidate_flag` | text | YES | - | NULL | Dettagli candidato da vast_autocandidates_details.log |
| `gaia_match` | json | YES | - | NULL | Match Gaia: {source_id, parallax, magnitude, ...} |
| `vsx_match` | json | YES | - | NULL | Match VSX: {type, period, amplitude, ...} |
| `atlas_match` | json | YES | - | NULL | Match ATLAS: {mag, error, ...} |
| `project_id` | int(11) | YES | MUL | NULL | FK → agata_projects (Project associato) |
| `created_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data creazione risultato |

**Relationships:**
- FK: `job_id` → `agata_vast_jobs.id` (CASCADE)
- FK: `project_id` → `agata_projects.id` (SET NULL)

**File Model:** [agata/auth_models/vast_job.py](../agata/auth_models/vast_job.py) (classe VastResult)

---

## Tabelle Legacy (Non AGATA)

Le seguenti tabelle esistono nel database ma NON fanno parte del sistema AGATA. Sono utilizzate da altri moduli o sono legacy.

### Tabelle Identificate

1. **`Cataloghi_Tess`** - Dati TESS (legacy/esterno)
2. **`agata_star_photometryapp`** - Backup o app esterna
3. **`TCE_ridotta`**, **`TCE_ridotta_1`**, **`TCE_ridotta_cost`** - TESS Candidate Events
4. **`TIC_con_LC`** - TESS Input Catalog con lightcurve
5. **`TPF_log_modifiche_target`**, **`TPF_modificati`** - Log modifiche Target Pixel Files
6. **`VSX_info`** - Informazioni VSX (Variable Star Index)
7. **`anagrafica_cataloghi_vizier`** - Anagrafica cataloghi Vizier
8. **`analisi_TESS_CTL`**, **`analisi_anagrafica_stelle`**, **`analisi_elenco`**, **`analisi_info_complement`**, **`analisi_soci`** - Modulo analisi
9. **`app_dati_Gaia`** - Dati Gaia (app esterna)
10. **`c_dati_stelle`**, **`c_dati_stelle_backup`** - Dati stelle (legacy)
11. **`curvaluce`** - Curve di luce (legacy)
12. **`datiDome`** - Dati Dome
13. **`dati_immagini`**, **`dati_scatti_immagini`** - Gestione immagini
14. **`dati_sessione`**, **`dati_sessione_campo`**, **`dati_sessioni_candidate`** - Sessioni osservative
15. **`dati_stelle`**, **`dati_stelle_proseXvast`** - Dati stelle
16. **`dati_tess_da_qlp`** - Dati TESS da QLP
17. **`dr2todr3`** - Mapping Gaia DR2 → DR3
18. **`info_per_template`** - Template info
19. **`prose_indicatori_stelle`**, **`prose_sessione`** - Modulo PROSE
20. **`vsx`** - VSX catalog

### Viste Database

21. **`agata_view_active_projects`** - Vista progetti attivi
22. **`agata_view_association_stats`** - Vista statistiche associazioni
23. **`agata_view_project_detail`** - Vista dettaglio progetti

**Note:** Per lo schema completo di queste tabelle legacy, consultare direttamente il database o la documentazione specifica di ciascun modulo.

---

## Note Tecniche

### Convenzioni Naming

- **Tabelle AGATA**: prefisso `agata_*`
- **Enum Types**: suffisso `_type` o `_state`
- **Foreign Keys**: suffisso `_id` per singole FK, `*_by` per audit (chi ha fatto l'azione)
- **Timestamps**: `created_at`, `updated_at`, `*_at` per timestamp specifici

### Tipi ENUM Definiti

1. **`user_role`**: superuser, admin, reviewer, analyst, viewer
2. **`association_type`**: internal, partner, school, individual
3. **`project_state`**: incoming, available, assigned, in_review, submitted_aavso, accepted_aavso, rejected_aavso, cancelled
4. **`catalog_search_type`**: coordinates, gaia_id, name, file
5. **`catalog_import_state`**: pending, searching, preview, importing, completed, failed, cancelled
6. **`project_output_type`**: image, fit, report, lightcurve, periodogram, phase_plot, other
7. **`confidence_level`**: low, medium, high
8. **`slack_context_type`**: thread, channel
9. **`slack_channel_type`**: coord, lavori, review
10. **`config_type`**: string, integer, boolean, json
11. **`vast_source_type`**: drive_folder, local_path, url
12. **`vast_job_state`**: pending, downloading, validating, vast_analysis, crossmatching, uploading, completed, failed, cancelled
11. **`audit_outcome`**: success, error, partial

### Indici e Performance

Per una lista completa degli indici definiti, eseguire:

```sql
SHOW INDEXES FROM agata_users;
SHOW INDEXES FROM agata_projects;
-- etc.
```

### Backup e Manutenzione

- **Backup automatico**: configurato via cron (se presente)
- **Retention policy**: consultare documentazione amministrativa
- **Migrazione schema**: gestita tramite Alembic (se configurato)

---

## Tabelle AGATA - TESS Bulk Import

### `agata_tess_curl_scripts`

Metadati persistenti di script MAST `.sh` caricati una volta e riutilizzati per più job batch senza re-upload.
Ogni script viene archiviato su disco; le entry sono lette on-demand dal file durante la creazione del job (non persistite in DB).

**Formati supportati per upload:**
- `.sh`, `.txt` — script di testo semplici (salvati come-is)
- `.sh.gz`, `.txt.gz` — file compressi gzip (salvati compressi su disco, decompressione streaming)
- `.zip` — archivi (estratti automaticamente, salvati compressi come .sh.gz)
- `.7z` — archivi 7-Zip (estratti automaticamente, salvati compressi come .sh.gz)

| Campo | Tipo | Null | Chiave | Default | Descrizione |
|-------|------|------|--------|---------|-------------|
| `id` | int(11) | NO | PRI | AUTO_INCREMENT | ID script |
| `script_code` | varchar(50) | NO | UNI | - | Codice univoco (TESSCURL-YYYY-NNNNN) |
| `original_filename` | varchar(500) | NO | - | - | Nome file original upload (es. mast_download.sh) |
| `stored_filename` | varchar(500) | NO | - | - | Nome file su disco (TESSCURL-2026-00001_mast_download.sh) |
| `association_id` | int(11) | YES | MUL | NULL | FK → agata_associations (proprietario script) |
| `parse_state` | enum | NO | MUL | uploading | uploading, parsing, ready, failed |
| `parse_error` | text | YES | - | NULL | Messaggio errore se parse_state=failed |
| `total_entries` | int(11) | NO | - | 0 | Numero righe curl nel file (conteggio, non righe DB) |
| `entries_processed` | int(11) | NO | - | 0 | Offset: indice della prossima entry non-elaborata |
| `created_by` | varchar(36) | NO | MUL | - | FK → agata_users (UUID) |
| `created_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data creazione script |
| `updated_at` | datetime | NO | - | CURRENT_TIMESTAMP | Data aggiornamento |

**Relationships:**
- FK: `created_by` → `agata_users.id`
- Inverse: `agata_tess_import_jobs.curl_script_id`

**File Model:** [agata/auth_models/tess_curl_script.py](../agata/auth_models/tess_curl_script.py) (classe TessCurlScript)

**File Storage:**
- Directory: `/var/www/astrogen/uploads/tess_curl_scripts/`
- Config: `TESS_CURL_SCRIPTS_DIR` env var
- Naming: `{script_code}_{original_filename}`

**Elaborazione:**
- File semplici (`.sh`, `.txt`): salvati come-is
- File compressi (`.gz`): salvati compressi su disco
- Archivi (`.zip`, `.7z`): estratti e salvati come `{script_code}_extracted.sh.gz`
- Parsing: background thread legge il file, conta le righe curl, salva `total_entries`. NO insert in tabella.
- Batching: al momento della creazione del job, `get_batch_from_file()` legge lo script dal disco saltando le prime `entries_processed` righe, estraendo il batch successivo
- Compression ratio: ~98% per script MAST di testo (~600MB → 12MB)

---

### Alterazioni a `agata_tess_import_jobs`

Aggiunte colonne per supporto script library (backward-compatible, legacy jobs hanno valori NULL/0):

| Campo | Tipo | Nuovo | Descrizione |
|-------|------|-------|-------------|
| `curl_script_id` | int(11) | Sì | FK → agata_tess_curl_scripts (NULL per job legacy) |
| `script_offset` | int(11) | Sì | Zero-based offset nel file curl (indice della prima riga letta dal batch). Default 0 per legacy jobs. |

**Relationship aggiunga:**
- FK: `curl_script_id` → `agata_tess_curl_scripts.id` (ON DELETE SET NULL)
- Inverse: `agata_tess_curl_scripts.jobs`

**Backward Compatibility:** Job creati via legacy path (multipart upload) hanno `curl_script_id=NULL, script_offset=0` e continuano a funzionare come prima. Job creati via script library hanno `curl_script_id=ID, script_offset=entries_processed at creation time`.

---

## Tabelle AGATA - ZTF Survey Pipeline

### `agata_ztf_survey_jobs`

Job di survey fotometrico ZTF su area di cielo. Ogni job interroga `ztf_objects_dr24` via IRSA TAP.

| Campo | Tipo | Null | Default | Descrizione |
|-------|------|------|---------|-------------|
| `id` | int(11) | NO | AUTO | PK |
| `job_code` | varchar(20) | NO | - | Codice univoco (es. ZTF-20260320-001) |
| `association_id` | int(11) | YES | NULL | FK → agata_associations |
| `user_id` | int(11) | YES | NULL | FK → agata_users |
| `target_name` | varchar(255) | NO | - | Nome descrittivo del campo |
| `ra_center` | double | NO | - | RA centro campo (gradi J2000) |
| `dec_center` | double | NO | - | Dec centro campo (gradi J2000) |
| `radius_deg` | double | NO | - | Raggio ricerca (gradi) |
| `ztf_filter` | varchar(1) | NO | r | Filtro ZTF: g, r, i |
| `mag_min` | double | YES | NULL | Limite magnitudine brillante |
| `mag_max` | double | YES | NULL | Limite magnitudine debole |
| `min_observations` | int(11) | NO | 20 | Min punti fotometrici per sorgente |
| `state` | varchar(50) | NO | pending | pending, downloading, analyzing, crossmatching, completed, failed |
| `progress_pct` | int(11) | NO | 0 | Percentuale completamento 0-100 |
| `current_step` | text | YES | NULL | Descrizione step corrente |
| `error_message` | text | YES | NULL | Messaggio errore se state=failed |
| `total_sources` | int(11) | NO | 0 | Sorgenti ZTF trovate nel campo |
| `candidates_found` | int(11) | NO | 0 | Candidati variabili identificati |
| `known_variables_found` | int(11) | NO | 0 | Variabili note da VSX |
| `promoted_count` | int(11) | NO | 0 | Stelle promosse in agata_star_photometry |
| `output_data` | JSON | YES | NULL | Dati aggiuntivi (promozione, ecc.) |
| `started_at` | datetime | YES | NULL | Timestamp avvio pipeline |
| `completed_at` | datetime | YES | NULL | Timestamp completamento |
| `created_at` | datetime | NO | NOW() | Timestamp creazione job |

### `agata_ztf_survey_results`

Risultati per sorgente del job ZTF Survey. Una riga per ogni sorgente ZTF trovata.

| Campo | Tipo | Null | Default | Descrizione |
|-------|------|------|---------|-------------|
| `id` | int(11) | NO | AUTO | PK |
| `job_id` | int(11) | NO | - | FK → agata_ztf_survey_jobs |
| `ztf_object_id` | bigint(20) | YES | NULL | ZTF DR object ID (OID) |
| `ra` | double | NO | - | RA sorgente (gradi J2000) |
| `decl` | double | NO | - | Dec sorgente (gradi J2000) |
| `n_points` | int(11) | NO | 0 | Osservazioni totali |
| `n_points_used` | int(11) | NO | 0 | Osservazioni valide (catflags==0) |
| `mean_mag` | double | YES | NULL | Magnitudine mediana ZTF |
| `std_dev` | double | YES | NULL | RMS magnitudini |
| `mag_err_median` | double | YES | NULL | Errore fotometrico mediano |
| `stetson_j` | double | YES | NULL | Indice Stetson J (non disponibile da DR24) |
| `stetson_k` | double | YES | NULL | Indice Stetson K (non disponibile da DR24) |
| `chi_squared` | double | YES | NULL | Chi-quadrato ridotto vs media |
| `mad` | double | YES | NULL | Median Absolute Deviation |
| `iqr` | double | YES | NULL | Interquartile Range (non disponibile da DR24) |
| `is_candidate` | tinyint(1) | NO | 0 | True se chi2 o MAD superano soglie variabilità |
| `is_known_variable` | tinyint(1) | NO | 0 | True se matchata in VSX (AAVSO) |
| `is_valid` | tinyint(1) | NO | 1 | False se match Gaia ambiguo/assente o is_duplicate |
| `is_ambiguous` | tinyint(1) | NO | 0 | True se match Gaia usa fallback 100 arcsec |
| `is_rejected` | tinyint(1) | NO | 0 | True se utente ha rifiutato manualmente |
| `is_duplicate` | tinyint(1) | NO | 0 | True se OID ZTF con più osservazioni mappa allo stesso gaia_source_id |
| `gaia_source_id` | bigint(20) | YES | NULL | Gaia DR3 source_id da cross-match posizionale |
| `vsx_match` | JSON | YES | NULL | Match VSX: {oid, name, type} |
| `catalog_matches` | varchar(255) | YES | NULL | CSV cataloghi matchati: Gaia, AAVSO |
| `variable_type` | varchar(100) | YES | NULL | Tipo variabile da VSX |
| `project_id` | int(11) | YES | NULL | FK → agata_projects (dopo promozione) |
| `created_at` | datetime | NO | NOW() | Timestamp creazione risultato |

**Note**:
- `is_duplicate`: quando più OID ZTF matchano lo stesso `gaia_source_id`, il vincitore (max `n_points_used`, tie-break `chi_squared` minore) mantiene `is_valid=True`; gli altri ottengono `is_duplicate=True, is_valid=False`. Introdotto con migration 008.
- Migrazioni: `002_create_ztf_survey_tables.sql`, `006_ztf_survey_is_rejected.sql`, `008_ztf_survey_is_duplicate.sql`

---

## Riferimenti

- **File Models**: `/var/www/astrogen/agata/auth_models/`
- **File Routes**: `/var/www/astrogen/agata/admin/routes/`
- **Database**: MariaDB/MySQL `catalogo` (localhost:3306)
- **ORM**: SQLAlchemy 2.x con `mapped_column` e `Mapped` type hints

---

**Ultima revisione**: 2026-03-20
**Autore**: Claude Code (auto-generato)
