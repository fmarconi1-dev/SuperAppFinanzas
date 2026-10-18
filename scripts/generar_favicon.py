"""Genera `assets/favicon.png`: el moño de Secretario, para la pestaña del navegador.

El favicon no puede ser el SVG (`st.set_page_config(page_icon=...)` con un SVG
daba un TypeError de MIME), así que se dibuja un PNG con Pillow, con las mismas
formas y colores de `assets/logo.svg`. Se corre a mano si cambia el logo:

    .venv\Scripts\python.exe scripts\generar_favicon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

LADO = 256            # se dibuja grande y se reduce: bordes suaves
ESCALA = LADO / 64    # el SVG está en una grilla de 64

SUPERFICIE = (24, 24, 27, 255)        # #18181B
BORDE = (39, 39, 42, 255)             # #27272A
ACENTO = (139, 92, 246, 255)          # #8B5CF6
PLIEGUE = (167, 139, 250, 140)        # #A78BFA al 55 %
NUDO = (248, 250, 252, 255)           # #F8FAFC


def _p(*xy: float) -> list[tuple[float, float]]:
    return [(xy[i] * ESCALA, xy[i + 1] * ESCALA) for i in range(0, len(xy), 2)]


def dibujar() -> Image.Image:
    img = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2 * ESCALA, 2 * ESCALA, 62 * ESCALA, 62 * ESCALA], radius=16 * ESCALA,
                        fill=SUPERFICIE, outline=BORDE, width=int(2 * ESCALA))
    # Alas (las curvas de las puntas del SVG se aproximan con un polígono redondeado).
    d.polygon(_p(27, 28.5, 14.5, 21.5, 11.6, 21.2, 11, 23.6, 11, 40.4, 11.6, 42.8, 14.5, 42.5, 27, 35.5), fill=ACENTO)
    d.polygon(_p(37, 28.5, 49.5, 21.5, 52.4, 21.2, 53, 23.6, 53, 40.4, 52.4, 42.8, 49.5, 42.5, 37, 35.5), fill=ACENTO)
    capa = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    dc.polygon(_p(27, 30.5, 17, 26, 17, 38, 27, 33.5), fill=PLIEGUE)
    dc.polygon(_p(37, 30.5, 47, 26, 47, 38, 37, 33.5), fill=PLIEGUE)
    img = Image.alpha_composite(img, capa)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([26 * ESCALA, 26.5 * ESCALA, 38 * ESCALA, 37.5 * ESCALA], radius=3.5 * ESCALA, fill=NUDO)
    return img


def main() -> None:
    destino = Path(__file__).resolve().parents[1] / "assets" / "favicon.png"
    dibujar().resize((128, 128), Image.LANCZOS).save(destino, optimize=True)
    print(f"Listo: {destino}")


if __name__ == "__main__":
    main()
