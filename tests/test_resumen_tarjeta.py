"""Lector de los resúmenes AMEX/VISA (Fase D, paso 5).

El lector se prueba sobre **listas de palabras con posición**, como las da
pdfplumber, armadas a mano (nombres y comercios inventados). Contra los PDF
reales de Franco: que los 9 se lean, que su cuenta cierre, y los tres ejemplos
del diseño (se saltean si `data/extractos/` no está).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from places.finanzas.core.resumen_tarjeta import (
    Consumo,
    Palabra,
    ResumenInvalido,
    leer_resumen,
)

PESOS_X1, DOLARES_X1 = 494.0, 580.0


class Hoja:
    """Arma las palabras de un resumen renglón por renglón."""

    def __init__(self):
        self.palabras: list[Palabra] = []
        self.alto = 100.0
        self.pagina = 1

    def renglon(self, *textos, pesos=None, dolares=None, x=23.0):
        for t in textos:
            ancho = 5.0 * len(t)
            self.palabras.append(Palabra(self.pagina, self.alto, x, x + ancho, t))
            x += ancho + 3
        if pesos is not None:
            self.palabras.append(Palabra(self.pagina, self.alto, PESOS_X1 - 40, PESOS_X1, pesos))
        if dolares is not None:
            self.palabras.append(Palabra(self.pagina, self.alto, DOLARES_X1 - 30, DOLARES_X1,
                                         dolares))
        self.alto += 17
        return self

    def pagina_nueva(self):
        self.pagina += 1
        self.alto = 100.0
        return self


def _base(tarjeta="VISA") -> Hoja:
    h = Hoja()
    h.renglon("Resumen", "Nº", "VI000")
    h.renglon("Tarjeta", "Crédito", *(["AMERICAN", "EXPRESS"] if tarjeta == "AMEX" else ["VISA"]))
    h.renglon("JUANA", "INVENTADA", "CUIT", "Banco:", "30-0-5")
    h.renglon("27-Ago-26", "04-Sep-26", "01-Oct-26", "09-Oct-26", "29-Oct-26", "11-Nov-26")
    h.palabras.append(Palabra(1, h.alto, 39, 99, "CONSOLIDADO"))
    h.palabras.append(Palabra(1, h.alto, 467, PESOS_X1, "PESOS"))
    h.palabras.append(Palabra(1, h.alto, 542, DOLARES_X1, "DÓLARES"))
    h.alto += 17
    return h


def _detalle(h: Hoja) -> Hoja:
    h.palabras += [Palabra(h.pagina, h.alto, 23, 50, "FECHA"),
                   Palabra(h.pagina, h.alto, 88, 138, "REFERENCIA"),
                   Palabra(h.pagina, h.alto, 320, 350, "CUOTA"),
                   Palabra(h.pagina, h.alto, 364, 428, "COMPROBANTE"),
                   Palabra(h.pagina, h.alto, 467, PESOS_X1, "PESOS"),
                   Palabra(h.pagina, h.alto, 542, DOLARES_X1, "DÓLARES")]
    h.alto += 17
    return h


def _consumo(h: Hoja, fecha, ref, *, pesos=None, dolares=None, cuota=None, comprobante="000123"):
    h.palabras.append(Palabra(h.pagina, h.alto, 23, 60, fecha))
    h.palabras.append(Palabra(h.pagina, h.alto, 74, 78, "*"))
    x = 86.0
    for t in ref.split():
        h.palabras.append(Palabra(h.pagina, h.alto, x, x + 5 * len(t), t))
        x += 5 * len(t) + 3
    if cuota:
        h.palabras.append(Palabra(h.pagina, h.alto, 325, 350, cuota))
    h.palabras.append(Palabra(h.pagina, h.alto, 366, 394, comprobante))
    if pesos:
        h.palabras.append(Palabra(h.pagina, h.alto, PESOS_X1 - 40, PESOS_X1, pesos))
    if dolares:
        h.palabras.append(Palabra(h.pagina, h.alto, DOLARES_X1 - 30, DOLARES_X1, dolares))
    h.alto += 17


def resumen_de_ejemplo(tarjeta="VISA", *, total="69.900,00", usd_total="12,00") -> list[Palabra]:
    h = _base(tarjeta)
    h.renglon("SALDO", "ANTERIOR", pesos="50.000,00", dolares="5,00", x=86)
    h.renglon("04-09-26", "SU", "PAGO", "EN", "PESOS", pesos="-50.000,00")
    h.renglon("04-09-26", "SU", "PAGO", "EN", "USD", dolares="-5,00")
    h.renglon("04-09-26", "DEV.IMP.", "RG", "5617", "30%(", "10000,00)", pesos="-3.000,00")
    h.renglon("DETALLE", "DEL", "CONSUMO", x=86)
    _detalle(h)
    _consumo(h, "15-04-26", "TIENDA INVENTADA", pesos="40.000,00", cuota="06/06")
    _consumo(h, "20-09-26", "AIRBNB * HM5YBSHC9H USD 12,00", dolares="12,00", comprobante="791072")
    h.renglon("TARJETA", "3017", "Total", "Consumos", "de", "JUANA", "INVENTADA",
              pesos="40.000,00", dolares="12,00", x=86)
    _consumo(h, "29-09-26", "CLUB INVENTADO", pesos="20.000,00")
    h.renglon("TARJETA", "5694", "Total", "Consumos", "de", "JUANA", "INVENTADA",
              pesos="20.000,00", dolares="0,00", x=86)
    h.renglon("01-10-26", "IIBB", "PERCEP-CABA", "2,00%(", "1000,00)", pesos="400,00")
    h.renglon("01-10-26", "IVA", "RG", "4240", "21%(", "2000,00)", pesos="2.500,00")
    h.renglon("01-10-26", "DB.RG", "5617", "30%", "(", "33333,33", ")", pesos="10.000,00")
    h.pagina_nueva()
    h.renglon("Resumen", "Nº", "VI000")
    h.renglon("JUANA", "INVENTADA", "CALLE", "FALSA", "123")
    h.renglon("TOTAL", "A", "PAGAR", pesos=total, dolares=usd_total)
    h.renglon("Cuotas", "a", "vencer:")
    h.renglon("01-11-26", "algo", "que", "no", "va", pesos="999,00")
    return h.palabras


def test_lee_el_resumen():
    r = leer_resumen(resumen_de_ejemplo())
    assert r.tarjeta == "VISA"
    assert (r.cierre, r.vencimiento) == (date(2026, 10, 1), date(2026, 10, 9))
    assert (r.cierre_proximo, r.vencimiento_proximo) == (date(2026, 10, 29), date(2026, 11, 11))
    assert r.saldo_anterior == (5000000, 500) and r.total == (6990000, 1200)
    assert r.pagado_en_pesos == 5000000
    assert [(c.referencia, c.pesos, c.dolares, c.cuota, c.plastico) for c in r.consumos] == [
        ("TIENDA INVENTADA", 4000000, 0, "06/06", "3017"),
        ("AIRBNB * HM5YBSHC9H USD 12,00", 0, 1200, None, "3017"),
        ("CLUB INVENTADO", 2000000, 0, None, "5694"),
    ]
    assert [c.pesos for c in r.cargos] == [40000, 250000]           # IIBB e IVA
    assert [p.pesos for p in r.percepciones] == [1000000]           # DB.RG 5617
    assert [d.pesos for d in r.devoluciones] == [-300000]           # DEV.IMP. RG 5617
    assert r.gastos_reales == 4000000 + 2000000 + 40000 + 250000


def test_amex():
    assert leer_resumen(resumen_de_ejemplo("AMEX")).tarjeta == "AMEX"


def test_el_numero_de_la_referencia_no_es_un_monto():
    """``USD 12,00`` adentro de la referencia no está en ninguna columna: no cuenta."""
    r = leer_resumen(resumen_de_ejemplo())
    assert r.consumos[1].dolares == 1200 and r.consumos[1].pesos == 0


def test_el_comercio_sin_codigos():
    assert Consumo(date(2026, 9, 20), "AIRBNB * HM5YBSHC9H USD 12,00", 0, 1200).comercio == "AIRBNB"
    assert Consumo(date(2026, 9, 6), "ANTHROPIC* CLAUD in1UGK8DBUSD", 0, 2000).comercio == \
        "ANTHROPIC* CLAUD"
    assert Consumo(date(2026, 9, 6), "SPORT CLUB 12345678", 7450000, 0).comercio == "SPORT CLUB"


def test_si_la_cuenta_no_cierra_no_adivina():
    with pytest.raises(ResumenInvalido, match="no cierra"):
        leer_resumen(resumen_de_ejemplo(total="69.900,01"))


def test_un_subtotal_que_no_coincide():
    palabras = resumen_de_ejemplo()
    subtotal = max(p.alto for p in palabras if p.texto == "20.000,00")   # el del plástico
    roto = [Palabra(p.pagina, p.alto, p.x0, p.x1, "21.000,00")
            if p.texto == "20.000,00" and p.alto == subtotal else p for p in palabras]
    with pytest.raises(ResumenInvalido, match="subtotal"):
        leer_resumen(roto)


def test_no_lee_el_encabezado():
    """Nada de antes de CONSOLIDADO (nombre, dirección, CUIT) queda en el resumen."""
    r = leer_resumen(resumen_de_ejemplo())
    assert "INVENTADA" not in " ".join(c.referencia for c in r.consumos if "JUANA" in c.referencia)
    assert "CALLE" not in repr(r) and "30-0-5" not in repr(r)


def test_algo_que_no_es_un_resumen():
    with pytest.raises(ResumenInvalido, match="AMEX o VISA"):
        leer_resumen([Palabra(1, 10, 10, 50, "hola")])


# ---------------------------------------------------------------- los PDF reales

_REAL = Path(__file__).resolve().parents[1] / "data" / "extractos"
_PDFS = sorted(_REAL.glob("RESUMEN_*.pdf")) if _REAL.is_dir() else []


@pytest.mark.skipif(len(_PDFS) < 9, reason="sin los resúmenes de Franco (data/extractos)")
def test_los_9_resumenes_reales_se_leen_y_cierran():
    from places.finanzas.core.resumen_tarjeta import palabras_del_pdf

    leidos = [leer_resumen(palabras_del_pdf(p.read_bytes())) for p in _PDFS]
    assert sorted(r.tarjeta for r in leidos).count("AMEX") == 4
    assert sorted(r.tarjeta for r in leidos).count("VISA") == 5


@pytest.mark.skipif(len(_PDFS) < 9 or not list(_REAL.glob("galicia-*.xlsx")),
                    reason="sin los archivos de Franco (data/extractos)")
def test_los_tres_ejemplos_del_diseno():
    """VISA 13/07 da 0; AMEX 07/08 (dos filas) +233.852,65; AMEX 09/10 −250.798,41."""
    from places.finanzas.core.extracto_galicia import leer_extracto
    from places.finanzas.core.resumen_tarjeta import palabras_del_pdf

    caja = leer_extracto(next(_REAL.glob("galicia-*.xlsx")).read_bytes())
    pagos = [f for f in caja.filas if f.tipo.startswith("PAGO TARJETA")]

    def diferencia(nombre):
        r = leer_resumen(palabras_del_pdf((_REAL / nombre).read_bytes()))
        suyos = [f for f in pagos if r.tarjeta in f.tipo
                 and r.cierre < f.fecha <= r.vencimiento + timedelta(days=5)]
        return len(suyos), -sum(f.monto for f in suyos) - r.gastos_reales

    assert diferencia("RESUMEN_VISA2_7_2026pdf.pdf") == (1, 0)
    assert diferencia("RESUMEN_AMEX30_7_2026pdf.pdf") == (2, 23385265)
    assert diferencia("RESUMEN_AMEX1_10_2026pdf.pdf") == (1, -25079841)


def test_el_deploy_instala_pdfplumber():
    """El Dockerfile instala desde `requirements.lock` si existe: si pdfplumber no
    está ahí, en producción el Secretario no puede leer los resúmenes."""
    raiz = Path(__file__).resolve().parents[1]
    lock = (raiz / "requirements.lock").read_text(encoding="utf-8").splitlines()
    assert "pdfplumber==0.11.7" in lock and "pdfminer.six==20250506" in lock
    assert "pdfplumber==0.11.7" in (raiz / "requirements.txt").read_text(encoding="utf-8")
    assert "pillow==12.3.0" in lock          # pdfplumber no subió Pillow (Streamlit pide <13)
