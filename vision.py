"""Análisis de uniformidad y color del grano (OpenCV).

Estrategias:
  - granos: segmenta cada grano (fondo estimado desde los bordes, watershed para separar
    granos pegados, descarte de bloques enormes/irregulares/cortados) y lo compara con la mediana.
  - pila: si no se pueden separar granos (foto de una pila), evalúa zonas de color.
"""
import cv2
import numpy as np

MAX_LADO = 800
K5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
K3 = np.ones((3, 3), np.uint8)


def _redimensionar(img):
    esc = MAX_LADO / max(img.shape[:2])
    if esc < 1:
        img = cv2.resize(img, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA)
    return img


def _segmentar(img_bgr):
    """Máscara de primer plano: distancia de color al fondo (estimado en los bordes)."""
    lab = cv2.cvtColor(cv2.GaussianBlur(img_bgr, (5, 5), 0), cv2.COLOR_BGR2LAB).astype(np.float32)
    h, w = lab.shape[:2]
    b = max(6, int(0.03 * min(h, w)))
    borde = np.concatenate([lab[:b].reshape(-1, 3), lab[-b:].reshape(-1, 3),
                            lab[:, :b].reshape(-1, 3), lab[:, -b:].reshape(-1, 3)])
    d = lab - np.median(borde, axis=0)
    dist = np.sqrt((0.6 * d[..., 0]) ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)
    if dist.max() < 20:
        return None
    d8 = cv2.normalize(dist, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, fg = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, K5)
    cont, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fg = np.zeros_like(fg)
    cv2.drawContours(fg, cont, -1, 255, -1)          # rellena brillos y huecos
    return fg


def _separar(img_bgr, fg):
    """Watershed sobre la transformada de distancia para separar granos que se tocan."""
    h, w = fg.shape
    dt = cv2.distanceTransform(fg, cv2.DIST_L2, 5)
    n, cc, stats, _ = cv2.connectedComponentsWithStats(fg)
    min_area = max(30, 0.0002 * h * w)
    validos = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    if not validos:
        return None
    maxs = np.zeros(n, np.float32)
    np.maximum.at(maxs, cc.ravel(), dt.ravel())
    r_med = float(np.median(maxs[validos]))            # radio típico de un grano
    sure_fg = (dt >= 0.6 * r_med).astype(np.uint8) * 255
    _, markers = cv2.connectedComponents(sure_fg)
    markers = markers.astype(np.int32) + 1             # fondo = 1, granos >= 2
    sure_bg = cv2.dilate(fg, K5, iterations=2)
    markers[sure_bg == 0] = 1
    markers[(sure_bg > 0) & (sure_fg == 0)] = 0        # zona por decidir
    markers = cv2.watershed(img_bgr, markers)
    markers[fg == 0] = 1
    return markers


def _por_granos(img_bgr):
    h, w = img_bgr.shape[:2]
    fg = _segmentar(img_bgr)
    if fg is None:
        return None
    markers = _separar(img_bgr, fg)
    if markers is None:
        return None
    luz_ch = cv2.cvtColor(cv2.GaussianBlur(img_bgr, (3, 3), 0), cv2.COLOR_BGR2LAB)[..., 0]
    min_area = max(30, 0.0002 * h * w)

    cand = []
    for lab_id in np.unique(markers):
        if lab_id < 2:
            continue
        ys, xs = np.nonzero(markers == lab_id)
        area = len(ys)
        if area < min_area:
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        m[ys - y0, xs - x0] = 255
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cs:
            continue
        c = max(cs, key=cv2.contourArea) + np.array([[[x0, y0]]], dtype=np.int32)
        hull = cv2.contourArea(cv2.convexHull(c))
        solidez = min(1.0, area / hull) if hull > 0 else 0.0
        toca_borde = y0 <= 1 or x0 <= 1 or y1 >= h - 1 or x1 >= w - 1
        rad = max(1, int(0.25 * np.sqrt(area / np.pi)))
        nucleo = cv2.erode(m, K3, iterations=rad)       # núcleo: sin bordes ni sombras
        sel = nucleo > 0 if nucleo.any() else m > 0
        luz = float(np.median(luz_ch[y0:y1, x0:x1][sel]))
        cand.append({"c": c, "area": area, "sol": solidez, "borde": toca_borde, "luz": luz})

    cobertura = float((fg > 0).mean())
    base = [x for x in cand if not x["borde"] and x["sol"] >= 0.80]
    if len(base) < 3:
        return {"granos": 0, "descartados": len(cand), "cobertura": cobertura,
                "markers": markers, "fg": fg, "cand": cand, "buenos": []}
    med_a = float(np.median([x["area"] for x in base]))
    buenos = [x for x in base if x["area"] <= 2.8 * med_a]   # fuera: granos sin separar / manchas
    return {"granos": len(buenos), "descartados": len(cand) - len(buenos), "cobertura": cobertura,
            "markers": markers, "fg": fg, "cand": cand, "buenos": buenos}


def _evaluar_granos(img_bgr, r, tol):
    salida = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    ids = {id(x) for x in r["buenos"]}
    for x in r["cand"]:
        if id(x) not in ids:
            cv2.drawContours(salida, [x["c"]], -1, (255, 200, 0), 1)       # amarillo: descartado
    mascara = cv2.cvtColor(r["fg"], cv2.COLOR_GRAY2RGB)
    mascara[r["markers"] == -1] = (255, 0, 0)
    luz = np.array([x["luz"] for x in r["buenos"]])
    areas = np.array([x["area"] for x in r["buenos"]], dtype=float)
    med_l, med_a = np.median(luz), np.median(areas)
    oscuro = luz < med_l * (1 - tol)
    palido = luz > med_l * (1 + tol)
    roto = areas < 0.45 * med_a
    defecto = oscuro | palido | roto
    for x, d in zip(r["buenos"], defecto):
        cv2.drawContours(salida, [x["c"]], -1, (255, 0, 0) if d else (0, 200, 0), 2)
    unif = float(np.clip(100 - 300 * luz.std() / max(luz.mean(), 1), 0, 100))
    return salida, mascara, {
        "pct": 100.0 * float(defecto.mean()), "unif": unif,
        "oscuros": int(oscuro.sum()), "palidos": int(palido.sum()), "rotos": int(roto.sum())}


def _por_zonas(img_bgr, tol):
    """Modo pila: color por zonas amplias (el promedio local anula las sombras entre granos)."""
    h, w = img_bgr.shape[:2]
    L = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    k = int(0.06 * max(h, w)) | 1
    Ls = cv2.GaussianBlur(L, (k, k), 0)
    med = float(np.median(Ls))
    zona = (Ls < med * (1 - tol)) | (Ls > med * (1 + tol))
    salida = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
    salida[zona] = 0.55 * salida[zona] + 0.45 * np.array([255, 0, 0], np.float32)
    unif = float(np.clip(100 - 300 * Ls.std() / max(Ls.mean(), 1), 0, 100))
    mascara = cv2.cvtColor((zona * 255).astype(np.uint8), cv2.COLOR_GRAY2RGB)
    return salida.astype(np.uint8), mascara, {"pct": 100.0 * float(zona.mean()), "unif": unif}


def analizar_grano(img_bgr, modo="auto", tolerancia=0.30, umbral_defectos=10.0):
    """modo: 'auto' | 'granos' | 'pila'. Devuelve (resultado, imagen_anotada_RGB)."""
    img = _redimensionar(img_bgr)
    aviso = None

    if modo in ("auto", "granos"):
        r = _por_granos(img)
        minimo = 8 if modo == "auto" else 4
        ok = r is not None and r["granos"] >= minimo
        if ok and modo == "auto":
            ok = (0.02 <= r["cobertura"] <= 0.85
                  and r["granos"] >= 0.5 * (r["granos"] + r["descartados"]))
        if ok:
            salida, mascara, m = _evaluar_granos(img, r, tolerancia)
            estado = "Apto" if m["pct"] <= umbral_defectos else "Con Defectos"
            resumen = (f"{r['granos']} granos analizados · {m['pct']:.1f}% con defectos "
                       f"({m['oscuros']} oscuros, {m['palidos']} pálidos, {m['rotos']} rotos/pequeños) · "
                       f"uniformidad {m['unif']:.0f}/100 → **{estado}**")
            if r["descartados"]:
                resumen += (f". Se descartaron {r['descartados']} bloques (muy grandes, irregulares "
                            "o cortados por el borde): salen en amarillo.")
            return {"estado": estado, "modo": "granos", "granos": r["granos"],
                    "pct_defectos": m["pct"], "uniformidad": m["unif"],
                    "descartados": r["descartados"], "aviso": None,
                    "resumen": resumen, "mascara": mascara}, salida
        if modo == "granos":
            salida = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return {"estado": None, "modo": "granos", "granos": r["granos"] if r else 0,
                    "descartados": 0, "aviso": None, "mascara": salida,
                    "resumen": "No se lograron separar suficientes granos. Prueba el modo «Pila de granos», "
                               "un fondo liso o una foto más cercana."}, salida
        aviso = "No se pudieron separar granos individuales; se evaluó por zonas de color (modo pila)."

    salida, mascara, m = _por_zonas(img, tolerancia)
    estado = "Apto" if m["pct"] <= umbral_defectos else "Con Defectos"
    resumen = (f"Modo pila: {m['pct']:.1f}% de la superficie con color fuera de rango · "
               f"uniformidad {m['unif']:.0f}/100 → **{estado}**")
    return {"estado": estado, "modo": "pila", "granos": None, "pct_defectos": m["pct"],
            "uniformidad": m["unif"], "descartados": 0, "aviso": aviso,
            "resumen": resumen, "mascara": mascara}, salida
