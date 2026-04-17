# AGATA – Nuovo Modello DB + Migration

**Argomenti:** `$ARGUMENTS` = `<nome_entita> "<descrizione tabella>"`

Esempio: `/agata-new-model SpectralObservation "Osservazioni spettroscopiche per analisi stellare"`

---

## Contesto Progetto

**Sistema:** AGATA | SQLAlchemy ORM + MySQL/MariaDB | Prefisso tabelle: `agata_`

**Schema autoritativo:** SEMPRE leggere `docs/DATABASE_SCHEMA.md` prima di creare nuovi modelli

**Modelli esistenti:** leggi `agata/auth_models/__init__.py` per vedere cosa esiste già

**Pattern modello:** leggi `agata/auth_models/ztf_survey_job.py` (modello completo con indici)

**Pattern migration:** leggi `docs/migrations/001_create_vast_tables.sql`

---

## File da Creare/Modificare

### 1. Nuovo modello: `agata/auth_models/<nome_snake_case>.py`

Struttura obbligatoria:

```python
"""
<NomeEntita> model - <Descrizione una riga>

<Descrizione più dettagliata del workflow/scopo>
"""
from sqlalchemy import String, Integer, Float, Double, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from agata.models import Base


class <NomeEntita>(Base):
    """
    <Docstring con workflow e scopo>
    """
    __tablename__ = "agata_<nome_snake_case>s"  # o plurale appropriato
    __table_args__ = (
        Index('idx_<nome>_association', 'association_id'),  # sempre se multi-tenant
        # altri indici per query frequenti
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    association_id: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="Multi-tenant scope")
    # ... altri campi con comment= obbligatorio

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, comment="Timestamp creazione")
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 2. Export: `agata/auth_models/__init__.py`

Aggiungi:
- Import: `from .<nome_snake_case> import <NomeEntita>`
- In `__all__`: `'<NomeEntita>'`

### 3. Migration: `docs/migrations/NNN_<modulo>_<descrizione>.sql`

- Numerazione: prossimo intero dopo l'ultimo file in `docs/migrations/`
- Idempotente: `CREATE TABLE IF NOT EXISTS`
- Ogni colonna con `COMMENT`
- Indici separati con `CREATE INDEX IF NOT EXISTS`
- Prefisso tabella: `agata_`
- Foreign keys esplicite se applicabile

### 4. Aggiornare: `docs/DATABASE_SCHEMA.md`

Aggiungi sezione con:
- Nome tabella, scopo, colonne principali, relazioni

---

## Regole Non Negoziabili

- Tabella con prefisso `agata_` (mai senza)
- `comment=` su ogni colonna non ovvia
- `association_id` presente su ogni entità tenantizzata (anche se nullable per superuser)
- `created_at` e `updated_at` su ogni tabella
- Migration idempotente (`IF NOT EXISTS`)
- `__all__` in `auth_models/__init__.py` aggiornato
- `DATABASE_SCHEMA.md` aggiornato nella stessa sessione

---

## Output Atteso

1. File modello SQLAlchemy completo
2. Modifica a `auth_models/__init__.py`
3. File SQL migration completo e idempotente
4. Sezione da aggiungere a `DATABASE_SCHEMA.md`
5. Checklist:
   - [ ] Prefisso `agata_` sulla tabella
   - [ ] Indice su `association_id` se presente
   - [ ] Migration idempotente
   - [ ] `auth_models/__init__.py` aggiornato
   - [ ] `DATABASE_SCHEMA.md` aggiornato
   - [ ] Timestamp fields `created_at` e `updated_at`
