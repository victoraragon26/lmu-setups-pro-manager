# lmu_parser.py
import re

def extraer_version_archivo(filename, creador):
    """Extrae la versión numérica (ej: 1.4.1) del nombre de un archivo .svm según su creador."""
    v_tuple = None
    if creador in ["HYMO", "HYMO2"]:
        m = re.search(rf'{creador}\s+v?(\d+(?:\.\d+)*)', filename, re.IGNORECASE)
        if m: v_tuple = tuple(map(int, m.group(1).split('.')))
    elif creador == "GO":
        m = re.search(r'GO\s+v?(\d+(?:\.\d+)*)', filename, re.IGNORECASE)
        if m: v_tuple = tuple(map(int, m.group(1).split('.')))
    elif creador == "Bober":
        m = re.search(r'Bober\s+v?(\d+(?:\.\d+)*)(?:.*v(\d+))?', filename, re.IGNORECASE)
        if m:
            base = list(map(int, m.group(1).split('.')))
            sub = [int(m.group(2))] if m.group(2) else [0]
            v_tuple = tuple(base + sub)
    elif creador == "P1Doks":
        m = re.search(r'(?:_|\s)v?(\d+(?:\.\d+)*)(?:_?v(\d+))?(?:\.svm|\.json)?\s*$', filename, re.IGNORECASE)
        if m:
            base = list(map(int, m.group(1).split('.')))
            sub = [int(m.group(2))] if m.group(2) else [0]
            v_tuple = tuple(base + sub)
    return v_tuple

def extraer_creador_fallback(filename):
    """Adivina el creador del setup si el archivo se metió a mano en la carpeta."""
    if filename.startswith("P1Doks"): return "P1Doks"
    if filename.startswith("CDA"): return "CDA"
    if filename.startswith("Bober"): return "Bober"
    if filename.startswith("GO"): return "GO"
    if filename.startswith("HYMO2"): return "HYMO2"
    if filename.startswith("HYMO"): return "HYMO"
    return "Otros"