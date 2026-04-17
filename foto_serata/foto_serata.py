from flask import render_template, current_app
from flask import session, redirect, url_for, flash
from urllib.parse import quote
import requests
import re
from datetime import datetime, timedelta
from msal import ConfidentialClientApplication
import config
import os
from . import foto_serata_bp

GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
FOLDER_ID = "01B7LYLXUC33PKCAGGJVFLTUBIYW5K5LA2"  # <-- inserisci il tuo folder_id reale
SITE_ID = 'associazioneastrogen.sharepoint.com,582928ba-113a-4c12-9472-2ad1ecf3abb8,dedbfd84-76d2-43e9-9630-7d278b4c73eb'
folder_path = "/80 immagini astronomiche/80.10 serate pubbliche"
encoded_path = quote(folder_path)
SCOPE = ["https://graph.microsoft.com/.default"]


def get_app_token():
    app = ConfidentialClientApplication(
        config.CLIENT_ID,
        authority=config.AUTHORITY,
        client_credential=config.CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" in result:
        return result["access_token"]
    else:
        raise Exception(f"Cannot obtain token: {result.get('error_description')}")


@foto_serata_bp.route("/")
def index():
    foto_dir = os.path.join(current_app.static_folder, 'foto_serata', 'immagini')
    six_days_ago = datetime.now() - timedelta(days=6)

    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")  # cerca data nel nome tipo '2025-07-09'

    try:
        foto_list = []
        for f in os.listdir(foto_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                match = pattern.search(f)
                if match:
                    file_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                    if file_date >= six_days_ago:
                        foto_list.append(url_for('static', filename=f'foto_serata/immagini/{f}'))
    except FileNotFoundError:
        foto_list = []

    return render_template("foto_serata.html", foto_list=sorted(foto_list))


@foto_serata_bp.route("/upload")
def upload():
    try:
        token = get_app_token()
    except Exception as e:
        flash(f"Errore di autenticazione: {e}")
        return render_template("foto_serata.html", foto_links=[])

    headers = {
        "Authorization": f"Bearer {token}"
    }
 
    # Cartella di destinazione locale
    local_folder = os.path.join(current_app.static_folder, "foto_serata", "immagini")

    url = f"{GRAPH_API_BASE}/sites/{SITE_ID}/drive/root:{encoded_path}:/children"

    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        flash(f"Errore durante il recupero delle immagini: {resp.status_code} {resp.text}")
        return render_template("foto_serata.html", foto_links=[])

    items = resp.json().get("value", [])
    
    foto_links = []
    errore = ""
    for item in items:
        # Filtra solo le immagini
        if item.get("file", {}).get("mimeType", "").startswith("image/"):
            download_url = item["@microsoft.graph.downloadUrl"]
            # Data di oggi in formato YYYY-MM-DD
            oggi_str = datetime.now().strftime("%Y-%m-%d")

            # Costruisci il nuovo nome file con prefisso data
            original_name = item["name"]
            nome_file = f"{oggi_str}_{original_name}"

            file_path = os.path.join(local_folder, nome_file)
            # Scarica l'immagine
            img_resp = requests.get(download_url)
            if img_resp.status_code == 200:
                try:
                    if os.path.exists(file_path):
                        errore = errore + f"Il file {nome_file} esiste già, salto il download."
                        continue    
                    with open(file_path, "wb") as f:
                        f.write(img_resp.content)
                    foto_links.append(nome_file)

                    # ✅ Solo ora che il file è stato salvato correttamente, cancellalo da SharePoint
                    file_id = item["id"]
                    delete_url = f"{GRAPH_API_BASE}/drives/{item['parentReference']['driveId']}/items/{file_id}"
                    del_resp = requests.delete(delete_url, headers=headers)
                    if del_resp.status_code not in (200, 204):
                        errore = errore + f"Immagine {nome_file} salvata ma non cancellata da SharePoint: {del_resp.status_code}"
                except Exception as e:
                    errore = errore + f"Errore nel salvataggio del file {nome_file}: {e}"
            else:
                errore = errore + f"Errore durante il download dell'immagine {nome_file}"


    return render_template("foto_serata_upload.html", foto_links=foto_links, errore=errore)
