# Implementazione association_id_owner in Cataloghi_esterni

## Sommario
Aggiunto un nuovo campo `association_id_owner` alla tabella `Cataloghi_esterni` per tracciare la proprietà dei dati fotometrici. Questo consente la visibilità selettiva dei dati mantenendo intatta la logica di controllo d'accesso basata su ruoli e `StarAssignment`.

## Semantica

### association_id_owner = NULL
- **Proprietario**: Superuser (bacino centrale)
- **Visibilità**:
  - Superuser: vede sempre
  - Admin/Analyst: vede solo se la stella è assegnata all'associazione tramite `StarAssignment`
- **Caricati da**: `/api/catalogs/qlp/upload` con `current_user.role == 'superuser'`

### association_id_owner = INT
- **Proprietario**: Associazione specifica
- **Visibilità**: Solo la loro associazione
- **Caricati da**:
  - `/api/catalogs/qlp/upload` con `current_user.role != 'superuser'` (admin/analyst della loro associazione)
  - `/api/external-catalogs/<import_id>/import` con `current_user.role != 'superuser'`

## File Modificati

### 1. Migration SQL
**File**: `/var/www/astrogen/migrations/add_association_id_owner_to_cataloghi_esterni.sql`

Aggiunge colonna `association_id_owner` con FK a `agata_associations`:
```sql
ALTER TABLE Cataloghi_esterni
ADD COLUMN association_id_owner INT NULL,
ADD FOREIGN KEY (association_id_owner) REFERENCES agata_associations(id) ON DELETE SET NULL,
ADD INDEX idx_cataloghi_esterni_assoc_owner (association_id_owner);
```

### 2. common.py - insert_catalog_data()
**File**: `/var/www/astrogen/agata/admin/routes/catalogs/common.py`

**Cambio**:
- Aggiunto parametro `association_id_owner: Optional[int] = None`
- Inserito nella query SQL: `association_id_owner`
- Log aggiornato per mostrare il proprietario dei dati

```python
def insert_catalog_data(
    db: Session,
    gaia_id: str,
    catalog_name: str,
    data: pd.DataFrame,
    association_id_owner: Optional[int] = None
) -> int:
```

### 3. file_upload_qlp.py
**File**: `/var/www/astrogen/agata/admin/routes/catalogs/file_upload_qlp.py`

**Cambio** (riga ~205):
- Determina `association_id_owner` in base al ruolo:
  - Superuser: `None` (bacino centrale)
  - Admin/Analyst: `current_user.association_id`
- Passa il parametro a `insert_catalog_data()`

```python
association_id_owner = None
if current_user.role != 'superuser':
    association_id_owner = current_user.association_id

points_imported = insert_catalog_data(
    db, gaia_id, catalog_name, df,
    association_id_owner=association_id_owner
)
```

### 4. catalog_import_service.py
**File**: `/var/www/astrogen/agata/admin/services/catalog_import_service.py`

**Cambiamenti**:
- `import_selected_data()`: aggiunto parametro `association_id_owner`
- `_insert_catalog_data()`: aggiunto parametro `association_id_owner`
- Entrambi inseriscono il campo nella query SQL

### 5. external_catalogs.py
**File**: `/var/www/astrogen/agata/admin/routes/external_catalogs.py`

**Cambio** (API `/api/external-catalogs/<import_id>/import`):
- Determina `association_id_owner`:
  - Superuser: `None`
  - Admin: `current_user.association_id`
- Passa a `import_selected_data()`

### 6. stars_catalog.py - Query di lettura
**File**: `/var/www/astrogen/agata/admin/routes/stars_catalog.py`

**Cambiamenti a tutte le query SELECT da Cataloghi_esterni**:

#### Superuser - Bacino centrale (senza filter_association_id)
```sql
WHERE association_id_owner IS NULL
```
- Vede solo dati centrali (NULL)

#### Superuser - Con filter_association_id
```sql
WHERE Source IN (...)
  AND (association_id_owner IS NULL OR association_id_owner = :filter_assoc_id)
```
- Vede dati centrali OPPURE dati dell'associazione filtrata

#### Admin
```sql
WHERE Source IN (...)
  AND (association_id_owner IS NULL OR association_id_owner = :filter_assoc_id)
```
- Vede dati centrali assegnati a loro + i loro dati specifici

### Query aggiornate:
1. **stars_catalog_page()** - lista stelle (2 query):
   - Query con filter (riga ~105)
   - Query bacino centrale (riga ~126)
   - Query admin (riga ~159)

2. **star_detail()** - dettaglio stella:
   - Check esistenza (riga ~344)
   - Cataloghi per stella (riga ~352)

3. **api_list_stars()** - API lista stelle:
   - Query con search
   - Query senza search

## Logica di Visibilità - MANTENUTA INVARIATA

La logica di controllo d'accesso **NON cambia**:
- Superuser: vede tutto
- Admin: vede stelle assegnate alla sua associazione tramite `StarAssignment`
- Analyst: non accede a `stars_catalog`, solo a progetti assegnati

**Nuovo**: Ora filtra anche su `association_id_owner`:
- Admin vede dati dell'associazione + dati centrali assegnati
- Dati privati (association_id_owner set) restano privati

## Scenario d'Uso

### Superuser carica QLP
```
1. File upload → insert_catalog_data(..., association_id_owner=None)
2. Dati vanno in Cataloghi_esterni con association_id_owner=NULL
3. Superuser assegna stella a associazione_6 via StarAssignment
4. Admin di associazione_6 vede la stella nella loro lista
5. Dati rimangono visibili come "bacino centrale"
```

### Admin carica QLP
```
1. File upload → insert_catalog_data(..., association_id_owner=6)
2. Dati vanno in Cataloghi_esterni con association_id_owner=6
3. Solo associazione_6 può vederli
4. Dati NON richiederanno StarAssignment per essere visibili
```

## Backward Compatibility

- Dati esistenti hanno `association_id_owner = NULL` (dati legacy rimangono centrali)
- Tutte le query includono `OR association_id_owner IS NULL` → dati legacy rimangono visibili a superuser
- La logica di `StarAssignment` rimane invariata

## Test Consigliati

1. **Caricamento dati superuser**:
   - Upload QLP da superuser
   - Verificare `association_id_owner = NULL` in DB
   - Assegnare a associazione_6
   - Admin di associazione_6 vede i dati

2. **Caricamento dati admin**:
   - Upload QLP da admin di associazione_6
   - Verificare `association_id_owner = 6` in DB
   - Admin di associazione_6 vede i dati
   - Admin di altre associazioni NOT vede

3. **Filtraggio query**:
   - Verificare che `WHERE` clause su `association_id_owner` non rompe ordinamenti
   - Testare con grandi dataset
   - Verificare performance dell'indice `idx_cataloghi_esterni_assoc_owner`

## Note Importanti

- **FK on DELETE SET NULL**: Se un'associazione viene cancellata, i suoi dati rimangono (association_id_owner=NULL)
- **Nessun cambio alle API response**: Il campo `association_id_owner` non è esposto agli endpoint
- **Audit logging**: Logs aggiornati per mostrare il proprietario dei dati importati
