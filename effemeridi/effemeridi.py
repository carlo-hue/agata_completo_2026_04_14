# effemeridi.py - Versione refactored
from flask import Blueprint, render_template_string
from skyfield.api import load, Topos
from skyfield.almanac import moon_phase, sunrise_sunset, find_discrete, risings_and_settings, meridian_transits
from skyfield import almanac
from skyfield.api import Loader
from math import cos
import pandas as pd
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from . import effemeridi_bp
import config

# Configurazione globale
ROME_LAT = 41.9028
ROME_LON = 12.4964
ROME_TZ = "Europe/Rome"

# Crea un loader che usa una directory specifica
loader = Loader(config.EPH_DATA_DIRECTORY)
# Carica una sola volta all'avvio
eph = loader('de421.bsp')
ts = loader.timescale()
earth = eph['earth']
rome_observer = Topos(latitude_degrees=ROME_LAT, longitude_degrees=ROME_LON)

# Definizione corpi celesti
CELESTIAL_BODIES = {
    'sun': eph['sun'],
    'moon': eph['moon'],
    'jupiter': eph['jupiter barycenter'],
    'saturn': eph['saturn barycenter']
}

PLANET_SYMBOLS = {
    'jupiter': '♃',
    'saturn': '♄'
}

def safe_format_time(skyfield_time, default="--:--"):
    """Formatta un tempo Skyfield in modo sicuro"""
    if skyfield_time is None:
        return default
    dt = skyfield_time.astimezone(ZoneInfo(ROME_TZ))
    return dt.strftime('%H:%M')


def safe_format_altitude(alt_degrees, default="--"):
    """Formatta l'altitudine in modo sicuro"""
    if alt_degrees is None or alt_degrees < -90:
        return default
    return f"{alt_degrees:.1f}°"

def get_rising_setting_events(body_name, day_start, day_end):
    """Ottiene gli eventi di alba/tramonto per un corpo celeste"""
    body = CELESTIAL_BODIES[body_name]
    
    if body_name == 'sun':
        f = sunrise_sunset(eph, rome_observer)
    else:
        f = risings_and_settings(eph, body, rome_observer)
    
    times, events = find_discrete(day_start, day_end, f)
    rise_time = next((times[i] for i, event in enumerate(events) if event == 1), None)
    set_time = next((times[i] for i, event in enumerate(events) if event == 0), None)
    return rise_time, set_time

def calculate_moon_phase(day_start):
    """Calcola la fase lunare"""

    phase_angle = moon_phase(eph, day_start)
    illumination = (1 - cos(phase_angle.radians)) / 2 * 100
    return illumination

def is_visible(rise_str, set_str, obs_start, obs_end):
    """Determina se un corpo celeste è visibile durante la finestra osservativa"""
    if rise_str == "--:--": rise_str = '00:00'
    if set_str == "--:--": set_str = '23:59'

    rise_dt = datetime.strptime(rise_str, '%H:%M')
    rise_time = (rise_dt + timedelta(hours=1)).time()

    set_dt = datetime.strptime(set_str, '%H:%M')
    set_time = (set_dt + timedelta(hours=-1)).time() 
    
    # Caso normale: sorgere e tramonto nello stesso giorno
    if rise_time < set_time:
        return (rise_time <= obs_start.time() <= set_time) or \
                (rise_time <= obs_end.time() <= set_time)
    # Caso in cui il tramonto è il giorno dopo
    else:
        return (obs_start.time() >= rise_time) or (obs_end.time() <= set_time)

def evaluate_observation_quality(day_data):
    """Valuta la qualità della giornata per osservazioni astronomiche"""
    quality_value = 0
    observation_symbols = []
    
    # Calcola l'orario di inizio osservazione (60 minuti dopo il tramonto del sole)
    sunset_time = datetime.strptime(day_data['sun_tramonta'], '%H:%M').time()
    observation_start = datetime.combine(datetime.min, sunset_time) + timedelta(minutes=60)
    observation_end = observation_start + timedelta(hours=2)

    
    
    # Verifica visibilità Luna
    try:
        moon_visible = is_visible(day_data['moon_sorge'], day_data['moon_tramonta'], 
                                observation_start, observation_end)
        
        if moon_visible:
            illumination = int(day_data['moon_illum'].replace('%', ''))
            quality_value += 20 + illumination / 10  # Più peso alla Luna 20 + 0-10 punti
            observation_symbols.append(f"L{illumination:02d}")
    except:
        pass
    
    # Verifica visibilità Giove
    try:
        jupiter_visible = is_visible(day_data['jupiter_sorge'], day_data['jupiter_tramonta'],
                                    observation_start, observation_end)
        
        if jupiter_visible:
            quality_value += 10  # Più punti per Giove
            observation_symbols.append("G")
    except:
        pass
    
    # Verifica visibilità Saturno
    try:
        saturn_visible = is_visible(day_data['saturn_sorge'], day_data['saturn_tramonta'],
                                  observation_start, observation_end)
        
        if saturn_visible:
            quality_value += 10  # Più punti per Saturno
            observation_symbols.append("S")
    except:
        pass
    
    # Costruisci la stringa di simboli (default se nessuno visibile)
    quality_symbol = "".join(observation_symbols) if observation_symbols else "--"
    
    # Normalizza il valore tra 0 e 100
    normalized_value = min(int((quality_value / 50) * 100), 100)
    
    return quality_symbol, normalized_value

def process_single_day(current_date):
    """Processa i dati astronomici per un singolo giorno"""
    # Definisci l'intervallo temporale
    day_start = ts.from_datetime(
        datetime.combine(current_date, time(0, 0)).replace(tzinfo=ZoneInfo(ROME_TZ))
    )
    day_end = ts.from_datetime(
        datetime.combine(current_date, time(23, 59)).replace(tzinfo=ZoneInfo(ROME_TZ))
    )

    moon_illumination = calculate_moon_phase(day_start)
    
    # Dati dei pianeti
    planets_data = {}
    for planet in ['jupiter', 'saturn','moon','sun']:
        planet_sorge, planet_tramonto = get_rising_setting_events(planet, day_start, day_end)
        planets_data[planet] = {
            'sorge': planet_sorge,
            'tramonta': planet_tramonto,
            'visible': False
        }
    
    # Costruisci il risultato
    day_result = {
        'data': current_date.strftime('%d/%m'),
        'moon_illum': f"{moon_illumination:.0f}%"
    }
    
    # Aggiungi dati pianeti
    for planet in ['jupiter', 'saturn','sun','moon']:
        prefix = planet
            
        day_result[f'{prefix}_sorge'] = safe_format_time(planets_data[planet]['sorge'])
        day_result[f'{prefix}_tramonta'] = safe_format_time(planets_data[planet]['tramonta'])
        day_result[f'{prefix}_visible'] = planets_data[planet]['visible']
    
    # Valutazione qualità osservativa
    quality_symbol, quality_value = evaluate_observation_quality(day_result)
    day_result['quality_symbol'] = quality_symbol
    day_result['quality_value'] = quality_value
    
    return day_result

@effemeridi_bp.route('/<int:anno>/<int:mese>')
def mostra_effemeridi(anno, mese):
    """Route principale per mostrare le effemeridi"""

    # Genera le date del mese
    start = pd.Timestamp(datetime(anno, mese, 1))
    end = start + pd.offsets.MonthEnd(1)
    days = pd.date_range(start, end)
    
    # Processa ogni giorno
    results = [process_single_day(day.date()) for day in days]
        
    # Template HTML (invariato)
    html = """
    <style>
    .effemeridi-table {
        border-collapse: collapse;
        width: 100%;
        font-size: 16px;
    }
    .effemeridi-table th, .effemeridi-table td {
        border: 1px solid #ddd;
        padding: 3px;
        text-align: center;
    }
    .effemeridi-table th {
        background-color: #f2f2f2;
        font-weight: bold;
        font-size: 14px;
    }
    .moon-visible {
        background-color: #e0f7ff;
    }
    .good-day {
        background-color: #90EE90;
        font-weight: bold;
    }
    .planet-visible {
        background-color: #fff2e0;
    }
    .sun-col { background-color: #fff8dc; }
    .moon-col { background-color: #f0f8ff; }
    .planet-col { background-color: #f5f5dc; }
    </style>
    
    <h2>Effemeridi dettagliate - {{ mese }}/{{ anno }} - Roma</h2>
    <p><small>Orari in ora locale italiana. Altitudini al transito (culminazione).</small></p>
    
    <table class="effemeridi-table">
        <tr>
            <th rowspan="2">Data</th>
            <th class="planet-col">Qualità</th>
            <th colspan="2" class="sun-col">☀️ SOLE</th>
            <th colspan="3" class="moon-col">🌙 LUNA</th>
            <th colspan="2" class="planet-col">🪐 PIANETI</th>
        </tr>
        <tr>
            <th class="planet-col">Qualità</th>
            <th class="sun-col">Alba</th>
            <th class="sun-col">Tramonto</th>
            <th class="moon-col">Sorge</th>
            <th class="moon-col">Tramonta</th>
            <th class="moon-col">Fase</th>
            <th class="planet-col">♃ Ora</th>
            <th class="planet-col">♄ Ora</th>
        </tr>
        {% for r in results %}
        <tr class="{% if r.good_day %}good-day{% elif r.luna_visibile_sera %}moon-visible{% endif %}">
            <td><strong>{{ r.data }}</strong></td>
            <td class="planet-col" style="background-color: 
                {% if r.quality_value >= 70 %}lightgreen
                {% elif r.quality_value >= 40 %}orange
                {% endif %};">
                {{ r.quality_symbol }} ({{ r.quality_value }}%)
            </td>
            <td class="sun-col">{{ r.sun_sorge }}</td>
            <td class="sun-col">{{ r.sun_tramonta }}</td>
            <td class="moon-col">{{ r.moon_sorge }}</td>
            <td class="moon-col">{{ r.moon_tramonta }}</td>
            <td class="moon-col">{{ r.moon_illum }}</td>
            <td class="planet-col{% if r.jupiter_visible %} planet-visible{% endif %}">{{ r.jupiter_sorge }} - {{ r.jupiter_tramonta }}</td>
            <td class="planet-col{% if r.saturn_visible %} planet-visible{% endif %}">{{ r.saturn_sorge }} - {{ r.saturn_tramonta }}</td>
        </tr>
        {% endfor %}
    </table>
    
    <div style="margin-top: 15px; font-size: 12px;">
        <h3>Legenda:</h3>
        <ul>
            <li><strong>Fase Luna:</strong> Percentuale di illuminazione</li>
            <li><span style="background:#e0f7ff; padding:2px;">Verde</span>: giornata ottima</li>
            <li><span style="background:#90EE90; padding:2px; font-weight:bold;">Arancio</span>: giornata buona</li>
            <li><strong>Simboli:</strong> ♃ Giove, ♄ Saturno</li>
        </ul>
    </div>
    """
    return render_template_string(html, results=results, anno=anno, mese=mese)