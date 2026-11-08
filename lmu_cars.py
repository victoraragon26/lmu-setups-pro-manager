# lmu_cars.py

# Diccionario de palabras clave asociadas a cada coche oficial
MAPEO_COCHES = {
    # --- HYPERCAR ---
    "Alpine A424": ["alpine", "a424"],
    "Aston Martin Valkyrie": ["valkyrie"],
    "BMW M Hybrid V8": ["hybrid v8", "bmw v8"],
    "Cadillac V-Series.R": ["cadillac", "v-series", "caddy"],
    "Ferrari 499P": ["499p"],
    "Genesis GMR-001": ["genesis", "gmr"],
    "Isotta Fraschini Tipo 6-C": ["isotta", "tipo 6"],
    "Lamborghini SC63": ["sc63"],
    "Peugeot 9X8 Evo": ["9x8 evo"],
    "Peugeot 9X8 (2023)": ["9x8"],
    "Porsche 963": ["963"],
    "Toyota GR010 Hybrid": ["gr010", "toyota"],
    "Glickenhaus SCG 007 LMH": ["glickenhaus", "scg"],
    "Vanwall Vandervell 680": ["vanwall", "vandervell"],

    # --- LMP2 ---
    "Oreca 07 (ELMS)": ["elms"],
    "Oreca 07 (Le Mans)": ["oreca 07 (le mans)", "oreca 07 le mans"],
    "Oreca 07 LMP2": ["oreca", "07", "lmp2"], # Fallback genérico

    # --- LMP3 ---
    "ADESS AD25": ["adess", "ad25"],
    "Duqueine D-09": ["duqueine", "d-09"],
    "Ginetta G61-LT-P3 Evo": ["ginetta", "g61"],
    "Ligier JS P325": ["ligier", "p325"],

    # --- LMGT3 ---
    "Aston Martin Vantage GT3 Evo": ["aston", "vantage", "amr"],
    "BMW M4 GT3": ["m4", "bmw m4"],
    "Corvette Z06 GT3.R": ["corvette", "z06", "c8"],
    "Ferrari 296 GT3": ["296"],
    "Ford Mustang GT3": ["mustang", "mus"],
    "Lamborghini Huracán GT3 Evo2": ["huracan", "lambo"],
    "Lexus RC F GT3": ["lexus", "rc f", "rcf"],
    "McLaren 720S GT3 Evo": ["mclaren", "720", "720s"],
    "Mercedes-AMG GT3 Evo": ["amg", "mercedes"],
    "Porsche 911 GT3 R (992)": ["992", "porsche 911 gt3"],

    # --- GTE (Antiguos) ---
    "Ferrari 488 GTE Evo": ["488"],
    "Porsche 911 RSR-19": ["rsr"]
}

def normalizar_coche_texto(nombre_sucio):
    """
    Recibe un string sucio (del archivo o del bot) y devuelve el nombre oficial del coche.
    """
    if not nombre_sucio:
        return "Otros"

    n = str(nombre_sucio).strip().lower().replace("_", " ")

    for nombre_oficial, palabras_clave in MAPEO_COCHES.items():
        if any(clave in n for clave in palabras_clave):
            return nombre_oficial

    return str(nombre_sucio).strip().title()