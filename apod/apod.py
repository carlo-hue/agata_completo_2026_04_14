# apod.py
# In cima al tuo file apod/routes.py
import requests
import random
from datetime import datetime
from flask import render_template, request
from . import apod_bp

# Assicurati che queste costanti siano definite e accessibili
# Puoi usare la tua chiave o 'DEMO_KEY' per i test
NASA_API_KEY = "Ssk16iPDheJX9oAXYaUA4keF7SQzZCRgrIoYTqDZ"
NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"


@apod_bp.route("/", methods=["GET", "POST"])
def apodbirthday():
    image_data = None
    error = None
    fallback_message = None

    if request.method == "POST":
        date_str = request.form.get("birthdate")
        
        if not date_str:
            error = "Per favore, inserisci una data valida."
            return render_template("apodbirthday.html", error=error)

        try:
            original_date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            r = requests.get(NASA_APOD_URL, params={
                "api_key": NASA_API_KEY,
                "date": original_date_obj.isoformat()
            })

            # CASO 1: Successo al primo tentativo (codice 200)
            if r.status_code == 200:
                data = r.json()
                image_data = {
                    "title": data.get("title"),
                    "url": data.get("url"),
                    "explanation": data.get("explanation"),
                    "media_type": data.get("media_type"),
                    "date": original_date_obj.strftime("%d %B %Y")
                }

            # ======================= MODIFICA CHIAVE QUI =======================
            # CASO 2: Attiva il fallback se l'APOD non è trovato (404) O se la data è troppo vecchia (400)
            elif r.status_code == 404 or (r.status_code == 400 and "Date must be between" in r.text):
            # ====================================================================
                
                day = original_date_obj.day
                month = original_date_obj.month
                current_year = datetime.now().year

                search_years = list(range(current_year - 15, current_year))
                random.shuffle(search_years)

                for year in search_years:
                    try:
                        fallback_date = datetime(year, month, day).date()
                    except ValueError:
                        continue
                    
                    fallback_r = requests.get(NASA_APOD_URL, params={
                        "api_key": NASA_API_KEY,
                        "date": fallback_date.isoformat()
                    })

                    if fallback_r.status_code == 200:
                        data = fallback_r.json()
                        image_data = {
                            "title": data.get("title"),
                            "url": data.get("url"),
                            "explanation": data.get("explanation"),
                            "media_type": data.get("media_type"),
                            "date": fallback_date.strftime("%d %B %Y")
                        }
                        fallback_message = f"Nessun APOD trovato per la data originale. Ecco quello del {fallback_date.strftime('%d %B %Y')}!"
                        break

                if not image_data:
                    error = f"Spiacenti, non è stato trovato nessun APOD per il giorno {day}/{month} negli ultimi 15 anni."

            # CASO 3: Altri errori API non gestiti
            else:
                error = f"Errore nella risposta da parte della NASA: {r.status_code} - {r.text}"

        except Exception as e:
            error = f"Si è verificato un errore: {str(e)}"

    return render_template("apodbirthday.html", image=image_data, error=error, fallback=fallback_message)




