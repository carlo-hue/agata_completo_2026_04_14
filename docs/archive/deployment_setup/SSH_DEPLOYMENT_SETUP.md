# 🔐 SSH + Deployment Automation Setup

**Data**: 2026-02-16
**Server Sviluppo**: astrogen01 (user: astrogen01)
**Server Produzione**: astrogen03 (IP: 10.1.0.6, user: azureuser)

---

## 🚀 Opzione 1: Setup Automatico (Consigliato)

Se vuoi che il setup SSH sia il più semplice possibile, usa lo script automatico.

### Su astrogen01:

```bash
cd /var/www/astrogen

# Step 1: Setup SSH (ti guiderà passo-passo)
./setup_ssh_deployment.sh --setup-ssh

# Step 2: Verifica SSH
./setup_ssh_deployment.sh --test-ssh

# Step 3: Deploy completo (automatico!)
./setup_ssh_deployment.sh --deploy-with-ssh
```

**Vantaggi**:
- ✅ Automatico
- ✅ No comandi manuali
- ✅ Trasferimento schema via SCP automatico
- ✅ Database backup automatico
- ✅ Migrazioni applicate automaticamente

---

## 📋 Opzione 2: Setup Manuale

Se preferisci fare i passaggi manualmente o il setup automatico fallisce.

### Passo 1: Su astrogen03 - Aggiungi Chiave Pubblica

**Chiave pubblica da aggiungere:**
```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOSPC9gwlDjI4x4G16hqZd5S5oZGmw18C14Lsp72ZsS7  giorgio.mazzacurati@astrogen.it
```

**Esegui su astrogen03:**

```bash
# Accedi
ssh azureuser@10.1.0.6

# Crea directory SSH
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Crea/aggiorna authorized_keys
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# Aggiungi chiave pubblica (incolla sopra)
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOSPC9gwlDjI4x4G16hqZd5S5oZGmw18C14Lsp72ZsS7  giorgio.mazzacurati@astrogen.it" >> ~/.ssh/authorized_keys

# Verifica
cat ~/.ssh/authorized_keys
```

### Passo 2: Su astrogen03 - Abilita SSH

```bash
# Verifica SSH service
sudo systemctl status ssh

# Se non attivo, avvia
sudo systemctl start ssh
sudo systemctl enable ssh

# Verifica
sudo systemctl status ssh
```

### Passo 3: Su astrogen01 - Testa Connessione

```bash
ssh azureuser@10.1.0.6 "echo 'SSH WORKS!' && hostname"
```

**Atteso output:**
```
SSH WORKS!
astrogen03
```

Se fallisce, verifica:
- Chiave esatta in `~/.ssh/authorized_keys` su astrogen03
- Permessi: `chmod 600 ~/.ssh/authorized_keys`
- SSH service attivo: `sudo systemctl status ssh`

### Passo 4: Su astrogen01 - Deploy con SSH

Una volta SSH funzionante, esegui:

```bash
cd /var/www/astrogen

# Trasferisci schema via SCP
scp /tmp/agata_schema_latest.sql azureuser@10.1.0.6:/tmp/

# Esegui deployment
./setup_ssh_deployment.sh --deploy-with-ssh
```

---

## 🔄 Workflow Completo Dopo Setup SSH

Una volta SSH configurato, il workflow è questo:

### Su astrogen01 (Sviluppo)

```bash
cd /var/www/astrogen

# 1. Sviluppa, testa, committa
git add .
git commit -m "Nuova feature"

# 2. Genera schema DB e script di deploy
./deploy_to_production.sh
# ← Questo genera:
#   - v1.19.0-production tag
#   - /tmp/agata_schema_latest.sql
#   - Output pronto per astrogen03

# 3. Deploy con SSH (automatico!)
./setup_ssh_deployment.sh --deploy-with-ssh
# ← Questo:
#   - Verifica SSH
#   - Backup DB su astrogen03
#   - Trasferisce schema via SCP
#   - Pull codice su astrogen03
#   - Applica migrazioni DB
#   - Verifica tabelle create
```

### Su astrogen03 (Produzione) - Manual Finish

Dopo lo script di deploy, esegui manualmente:

```bash
ssh azureuser@10.1.0.6

# 1. Aggiorna dipendenze Python
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 2. Verifica database
mysql -u aaaat01 -p catalogo -e "SELECT COUNT(*) FROM agata_projects;"

# 3. Restart servizi
sudo systemctl restart agata.service
sudo systemctl restart nginx

# 4. Verifica deployment
curl http://localhost:5000/agata/admin/
```

---

## 📁 Script Disponibili

| Script | Descrizione |
|--------|-------------|
| `deploy_to_production.sh` | Genera schema DB, crea tag, prepara deployment |
| `setup_ssh_deployment.sh` | Setup SSH + deployment completo automatico |

---

## 🛠️ Comandi Utili con SSH

Una volta SSH configurato, puoi usare questi comandi:

```bash
# Test semplice
ssh azureuser@10.1.0.6 "echo OK"

# Copia file da astrogen01 a astrogen03
scp /tmp/agata_schema_latest.sql azureuser@10.1.0.6:/tmp/

# Copia file da astrogen03 a astrogen01
scp azureuser@10.1.0.6:/tmp/backup.sql ~/

# Esegui comando remoto
ssh azureuser@10.1.0.6 "cd /var/www/astrogen && git log -1 --oneline"

# Accedi shell remota
ssh azureuser@10.1.0.6
# Adesso sei su astrogen03 come azureuser
```

---

## ❌ Troubleshooting

### Problema: "Permission denied (publickey)"

**Causa**: Chiave SSH non accettata

**Soluzione**:
```bash
# Su astrogen01, verifica chiave privata
cat ~/.ssh/id_ed25519.pub

# Su astrogen03, verifica authorized_keys
cat ~/.ssh/authorized_keys

# Deve essere identico!

# Se non è identico, aggiungi di nuovo:
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOSPC9gwlDjI4x4G16hqZd5S5oZGmw18C14Lsp72ZsS7  giorgio.mazzacurati@astrogen.it" >> ~/.ssh/authorized_keys

# Verifica permessi
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### Problema: "Connection refused"

**Causa**: SSH service non attivo su astrogen03

**Soluzione** (su astrogen03):
```bash
sudo systemctl start ssh
sudo systemctl enable ssh
sudo systemctl status ssh

# Verifica che sia in listening
sudo ss -tlnp | grep ssh
```

### Problema: "Could not resolve hostname 10.1.0.6"

**Causa**: Network non raggiungibile

**Soluzione**:
```bash
# Testa connessione network
ping 10.1.0.6

# Se fallisce, verifica:
# - IP corretto?
# - Stessi network/subnet?
# - Firewall bloccato?
```

### Problema: SCP fallisce con "File not found"

**Causa**: Percorso file sbagliato

**Soluzione**:
```bash
# Verifica file esiste
ls -lh /tmp/agata_schema_latest.sql

# Se non esiste, crea con:
cd /var/www/astrogen
./deploy_to_production.sh
```

### Problema: Script dice "SSH non funzionante"

**Soluzione**:
```bash
# Testa manualmente SSH
ssh -vvv azureuser@10.1.0.6 "echo OK"

# Se fallisce, segui istruzioni debug output

# Se funziona ma script fallisce, riesegui:
./setup_ssh_deployment.sh --test-ssh
```

---

## 📊 Processo Visualizzato

### Prima Setup SSH (Manuale):
```
astrogen01                          astrogen03
  |                                    |
  |---> Genera schema.sql ---> /tmp    |
  |                                    |
  |     Deve copiar                     |
  |     manualmente!              mkdir /tmp
  |     ↓                              ↓
  |---> SCP non funziona ❌             |
  |                                    |
  |---> Copia file manualmente         |
  |     (email, USB, ecc)              |
  |                                    |
  |                          mysql < schema.sql
  |                                    |
  |---> Git pull via HTTPS             |
  |                          git pull origin/main
```

### Dopo Setup SSH (Automatico):
```
astrogen01                          astrogen03
  |                                    |
  |---> Genera schema.sql ---> /tmp    |
  |                                    |
  |---> SCP SSH ────────────────────> /tmp ✅
  |                                    |
  |---> SSH Backup                  mysql dump ✅
  |                                    |
  |---> SSH Pull                    git pull ✅
  |                                    |
  |---> SSH Apply Schema            mysql < ✅
  |                                    |
  |                          (manual) pip install
  |                          (manual) systemctl restart
```

---

## 📝 Prossimi Step

1. **Scegli approccio**:
   - ✅ Automatico: `./setup_ssh_deployment.sh --setup-ssh`
   - 📋 Manuale: Segui "Opzione 2" sopra

2. **Testa SSH**:
   ```bash
   ssh azureuser@10.1.0.6 "echo OK"
   ```

3. **Esegui deployment**:
   ```bash
   ./setup_ssh_deployment.sh --deploy-with-ssh
   ```

4. **Finisci su astrogen03**:
   ```bash
   pip install -r requirements.txt --upgrade
   sudo systemctl restart agata.service
   sudo systemctl restart nginx
   ```

---

**Status**: ✅ Pronto per SSH setup
**Ultima modifica**: 2026-02-16
**Versione AGATA**: v1.19.0-production
