"""Análisis de uniformidad y color del grano (heurística didáctica con OpenCV)."""
import cv2
import numpy as np


def analizar_grano(img_bgr, fondo_claro=True, umbral_defectos=10.0):
    h, w = img_bgr.shape[:2]
    esc = 900 / max(h, w)
    if esc < 1:
        img_bgr = cv2.resize(img_bgr, None, fx=esc, fy=esc, interpolation=cv2.INTER_AREA)
        h, w = img_bgr.shape[:2]

    gray = cv2.GaussianBlur(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    modo = cv2.THRESH_BINARY_INV if fondo_claro else cv2.THRESH_BINARY
    _, mask = cv2.threshold(gray, 0, 255, modo + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area_img = h * w
    granos = [c for c in contornos if 0.0004 * area_img < cv2.contourArea(c) < 0.15 * area_img]

    salida = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    if len(granos) < 3:
        return {"estado": None, "granos": len(granos),
                "resumen": "No se detectaron suficientes granos. Mejora la luz o cambia el tipo de fondo."}, salida

    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    luz, areas = [], []
    for c in granos:
        m = np.zeros((h, w), np.uint8)
        cv2.drawContours(m, [c], -1, 255, -1)
        luz.append(cv2.mean(lab, mask=m)[0])
        areas.append(cv2.contourArea(c))
    luz, areas = np.array(luz), np.array(areas)
    med_l, med_a = np.median(luz), np.median(areas)

    oscuro = luz < 0.75 * med_l          # quemado / sobrefermentado
    palido = luz > 1.30 * med_l          # inmaduro / pálido
    roto = areas < 0.5 * med_a           # quebrado / vano
    defecto = oscuro | palido | roto

    for c, d in zip(granos, defecto):
        cv2.drawContours(salida, [c], -1, (255, 0, 0) if d else (0, 200, 0), 2)

    pct = 100.0 * defecto.sum() / len(granos)
    uniformidad = float(np.clip(100 - 300 * luz.std() / max(luz.mean(), 1), 0, 100))
    estado = "Apto" if pct <= umbral_defectos else "Con Defectos"
    resumen = (
        f"{len(granos)} granos analizados · {pct:.1f}% con defectos "
        f"({int(oscuro.sum())} oscuros, {int(palido.sum())} pálidos, {int(roto.sum())} rotos/pequeños) · "
        f"uniformidad de color {uniformidad:.0f}/100 → **{estado}**"
    )
    return {"estado": estado, "granos": len(granos), "pct_defectos": pct,
            "uniformidad": uniformidad, "resumen": resumen}, salida
