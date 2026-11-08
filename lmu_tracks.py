# lmu_tracks.py

MAPA_CIRCUITOS = {
    "silverstone (wec)": "Silverstonewec",
    "silverstone nat": "Silverstone_National",
    "silverstone int": "Silverstone_International",
    "silverstone": "Silverstone",
    "fuji cl": "Fuji_Cl",
    "fuji": "Fuji",
    "spa end": "Spa_Endce",
    "spa": "Spa",
    "algarve": "Portimao",
    "barcelona": "Circuit De Barcelona",
    "daytona": "Daytonarc",
    "imola": "Imola",
    "laguna seca": "Lagunaseca",
    "long beach": "Longbeach",
    "monza": "Monza",
    "road atlanta": "Road Atlanta",
    "bahrain": "Bahrain",
    "cota": "Circuit Of The Americas",
    "interlagos": "Interlagos",
    "le mans": "Lemans",
    "lusail": "Qatar",
    "paul ricard": "Paulricard",
    "sebring": "Sebring"
}

def obtener_carpeta_circuito(texto_pista):
    """Detecta de qué circuito es el setup leyendo el mensaje de Telegram."""
    pista_raw = texto_pista.strip().replace(":", "").lower()
    for clave_bot, carpeta_juego in MAPA_CIRCUITOS.items():
        if clave_bot in pista_raw:
            return carpeta_juego
    return ""