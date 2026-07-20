"""
Generador automático de sopas de letras.

`generar_sopa` recibe palabras y las coloca en la cuadrícula en 4 direcciones
(→ horizontal, ↓ vertical, ↘ y ↗ diagonales), permitiendo cruces, y rellena
las casillas vacías con letras al azar.

Entrada:  [{'id': <pk>, 'texto': 'FOTOSINTESIS'}, ...]
Salida:   (grid, placements, tamano)
          grid = ['ABC...', ...]  (una string por fila)
          placements = [{'id','fila','columna','df','dc'}]
"""
import random
import unicodedata

# →, ↓, ↘, ↗  (amigable para escolares: sin palabras al revés)
DIRECCIONES = [(0, 1), (1, 0), (1, 1), (-1, 1)]
ALFABETO = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def normalizar(texto):
    """Mayúsculas, sin tildes, solo A–Z y Ñ."""
    texto = (texto or '').strip().upper()
    salida = []
    for ch in texto:
        if ch == 'Ñ':
            salida.append('Ñ')
            continue
        base = ''.join(c for c in unicodedata.normalize('NFD', ch)
                       if unicodedata.category(c) != 'Mn')
        if base.isalpha():
            salida.append(base)
    return ''.join(salida)


def _rango(size, longitud, delta):
    """Rango [lo, hi] válido de inicio para que la palabra quepa según el delta."""
    if delta == 0:
        return 0, size - 1
    if delta > 0:
        return 0, size - 1 - (longitud - 1)
    return longitud - 1, size - 1


def _intentar(words, size):
    grid = [[None] * size for _ in range(size)]
    placements = []
    for word in words:
        w = word['w']
        L = len(w)
        colocada = False
        for _ in range(300):
            dr, dc = random.choice(DIRECCIONES)
            r_lo, r_hi = _rango(size, L, dr)
            c_lo, c_hi = _rango(size, L, dc)
            if r_hi < r_lo or c_hi < c_lo:
                continue
            r = random.randint(r_lo, r_hi)
            c = random.randint(c_lo, c_hi)
            celdas = [(r + dr * i, c + dc * i) for i in range(L)]
            ok = True
            for (rr, cc), ch in zip(celdas, w):
                cur = grid[rr][cc]
                if cur is not None and cur != ch:
                    ok = False
                    break
            if ok:
                for (rr, cc), ch in zip(celdas, w):
                    grid[rr][cc] = ch
                placements.append({'id': word['id'], 'fila': r, 'columna': c, 'df': dr, 'dc': dc})
                colocada = True
                break
        if not colocada:
            return None
    # Rellenar vacías.
    for r in range(size):
        for c in range(size):
            if grid[r][c] is None:
                grid[r][c] = random.choice(ALFABETO)
    return [''.join(row) for row in grid], placements, size


def generar_sopa(palabras):
    words = []
    for p in palabras:
        w = normalizar(p['texto'])
        if len(w) >= 2:
            words.append({'id': p['id'], 'w': w})
    if not words:
        return [], [], 0
    words.sort(key=lambda x: len(x['w']), reverse=True)
    longest = len(words[0]['w'])
    base = max(10, longest)
    # Crece el tablero si no logra acomodar todas las palabras.
    for size in range(base, base + 10):
        for _ in range(25):  # varios reintentos por tamaño (colocación aleatoria)
            res = _intentar(words, size)
            if res is not None:
                return res
    # Último recurso: tablero grande.
    size = base + 12
    res = _intentar(words, size)
    return res if res is not None else ([], [], 0)
