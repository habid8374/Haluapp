"""
Generador automático de crucigramas.

`generar_layout` recibe una lista de palabras y las ubica en una cuadrícula
cruzándolas donde comparten letras (algoritmo voraz). El docente NO dibuja nada:
solo escribe palabras + pistas y el sistema arma todo.

Entrada:  [{'id': <pk>, 'respuesta': 'FOTOSINTESIS'}, ...]
Salida:   (placements, filas, columnas)
          placements = [{'id', 'fila', 'columna', 'direccion' ('H'|'V'), 'numero'}]
          Toda palabra recibe posición; si no logra cruzar, se ubica en una
          fila propia (aislada) pero igual queda en el crucigrama.
"""
import unicodedata


def normalizar(texto):
    """Mayúsculas, sin tildes, solo letras A–Z y Ñ."""
    texto = (texto or '').strip().upper()
    # Conserva la Ñ; quita tildes del resto.
    salida = []
    for ch in texto:
        if ch == 'Ñ':
            salida.append('Ñ')
            continue
        desc = unicodedata.normalize('NFD', ch)
        base = ''.join(c for c in desc if unicodedata.category(c) != 'Mn')
        if base.isalpha():
            salida.append(base)
    return ''.join(salida)


def _cabe(grid, celdas, letra_por_celda, direccion):
    """Valida que una palabra quepa en `celdas` sin romper reglas de crucigrama.

    Devuelve (ok, num_cruces) — num_cruces = casillas que se apoyan en letras ya
    puestas (deben coincidir). Reglas: las casillas nuevas no pueden tener vecinos
    perpendiculares ocupados, y los extremos de la palabra deben quedar libres.
    """
    cruces = 0
    n = len(celdas)
    (r0, c0) = celdas[0]
    (r1, c1) = celdas[-1]
    # Extremos: la casilla anterior al inicio y posterior al fin deben estar libres.
    if direccion == 'H':
        if (r0, c0 - 1) in grid or (r1, c1 + 1) in grid:
            return False, 0
    else:
        if (r0 - 1, c0) in grid or (r1 + 1, c1) in grid:
            return False, 0

    for idx, (r, c) in enumerate(celdas):
        letra = letra_por_celda[idx]
        if (r, c) in grid:
            if grid[(r, c)] != letra:
                return False, 0
            cruces += 1  # cruce válido
        else:
            # Casilla nueva: sus vecinos perpendiculares deben estar vacíos.
            if direccion == 'H':
                if (r - 1, c) in grid or (r + 1, c) in grid:
                    return False, 0
            else:
                if (r, c - 1) in grid or (r, c + 1) in grid:
                    return False, 0
    return True, cruces


def generar_layout(palabras):
    palabras_norm = []
    for p in palabras:
        w = normalizar(p['respuesta'])
        if len(w) >= 2:
            palabras_norm.append({'id': p['id'], 'w': w})
    # Las más largas primero: mejor esqueleto.
    palabras_norm.sort(key=lambda x: len(x['w']), reverse=True)

    grid = {}          # (r, c) -> letra
    colocadas = []     # {'id', 'w', 'r', 'c', 'dir'}

    if not palabras_norm:
        return [], 0, 0

    # Primera palabra: horizontal en (0, 0).
    primera = palabras_norm[0]
    for i, ch in enumerate(primera['w']):
        grid[(0, i)] = ch
    colocadas.append({'id': primera['id'], 'w': primera['w'], 'r': 0, 'c': 0, 'dir': 'H'})

    for p in palabras_norm[1:]:
        w = p['w']
        mejor = None  # (cruces, celdas, direccion, r, c)

        for col in colocadas:
            cw, cr, cc, cdir = col['w'], col['r'], col['c'], col['dir']
            for i, ch in enumerate(w):
                for j, ch2 in enumerate(cw):
                    if ch != ch2:
                        continue
                    # La nueva palabra va perpendicular a la existente.
                    if cdir == 'H':
                        # cruce en (cr, cc + j); nueva es vertical
                        r_start, c_start, ndir = cr - i, cc + j, 'V'
                        celdas = [(r_start + k, c_start) for k in range(len(w))]
                    else:
                        r_start, c_start, ndir = cr + j, cc - i, 'H'
                        celdas = [(r_start, c_start + k) for k in range(len(w))]
                    ok, cruces = _cabe(grid, celdas, w, ndir)
                    if ok and cruces >= 1:
                        cand = (cruces, celdas, ndir, r_start, c_start)
                        if mejor is None or cand[0] > mejor[0]:
                            mejor = cand

        if mejor is not None:
            _, celdas, ndir, r_start, c_start = mejor
            for k, (r, c) in enumerate(celdas):
                grid[(r, c)] = w[k]
            colocadas.append({'id': p['id'], 'w': w, 'r': r_start, 'c': c_start, 'dir': ndir})
        else:
            # No cruzó: se ubica horizontal en una fila nueva debajo de todo.
            max_r = max((r for (r, _) in grid), default=0)
            r_start = max_r + 2
            for k, ch in enumerate(w):
                grid[(r_start, k)] = ch
            colocadas.append({'id': p['id'], 'w': w, 'r': r_start, 'c': 0, 'dir': 'H'})

    # Normalizar a origen (0, 0).
    min_r = min(r for (r, _) in grid)
    min_c = min(c for (_, c) in grid)
    grid = {(r - min_r, c - min_c): v for (r, c), v in grid.items()}
    for col in colocadas:
        col['r'] -= min_r
        col['c'] -= min_c
    filas = max(r for (r, _) in grid) + 1
    columnas = max(c for (_, c) in grid) + 1

    # Numeración estándar: barrido por filas; una casilla inicia palabra si a su
    # izquierda/arriba no hay letra y a su derecha/abajo sí.
    numero_de_celda = {}
    contador = 0
    for r in range(filas):
        for c in range(columnas):
            if (r, c) not in grid:
                continue
            inicia_h = (r, c - 1) not in grid and (r, c + 1) in grid
            inicia_v = (r - 1, c) not in grid and (r + 1, c) in grid
            if inicia_h or inicia_v:
                contador += 1
                numero_de_celda[(r, c)] = contador

    placements = []
    for col in colocadas:
        numero = numero_de_celda.get((col['r'], col['c']))
        placements.append({
            'id': col['id'], 'fila': col['r'], 'columna': col['c'],
            'direccion': col['dir'], 'numero': numero,
        })
    return placements, filas, columnas
