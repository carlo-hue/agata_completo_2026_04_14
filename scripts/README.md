# AGATA Deployment Scripts

## `deploy.sh` ⭐

Deploy da astrogen01 → astrogen03 via GitHub.

**Steps automatici** (8):
1. Verifica prerequisiti (git clean, SSH)
2. Conferma deploy
3. Backup DB produzione
4. Push codice su GitHub
5. Pull codice su produzione
6. SQL migrations (opzionale, `--db-migrate`)
7. `pip install -r requirements.txt`
8. Restart Apache + health check

**Utilizzo:**
```bash
./scripts/deploy.sh --yes                        # Deploy HEAD di main
./scripts/deploy.sh --yes --tag v2.14.1          # Deploy tag specifico
./scripts/deploy.sh --yes --db-migrate           # Deploy + applica SQL in docs/migrations/
./scripts/deploy.sh --dry-run                    # Preview senza modifiche
```

**Migrazioni DB**: metti i file SQL in `docs/migrations/NNN_*.sql` (ordinati numericamente) e usa `--db-migrate`. I file sono idempotenti (`CREATE TABLE IF NOT EXISTS`).

---

## `setup_ssh_deployment.sh`

Configura SSH key-based auth tra astrogen01 e astrogen03. Da eseguire una volta sola.

```bash
./scripts/setup_ssh_deployment.sh --setup-ssh   # Setup iniziale
./scripts/setup_ssh_deployment.sh --test-ssh    # Verifica connessione
```

---

## Configurazione

**`.env`** (git-ignored, nella root del progetto):
```bash
DATABASE_URL=mysql+pymysql://aaaat01:PASSWORD@localhost:3306/catalogo
```
