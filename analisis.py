"""
Calcula los indicadores de cobranzas y genera el dashboard web.

Lee la base SQLite, ejecuta las consultas de sql/consultas.sql, calcula los
KPIs con pandas y escribe docs/index.html (publicable en GitHub Pages) con
los gráficos y un resumen de hallazgos.

Uso:
    python analisis.py
    python analisis.py --hoy 2026-10-31
"""

import argparse
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).parent
TRAMOS = [  # tramos de antigüedad de deuda (aging)
    ("Al día", -10_000, 0),
    ("1–30 días", 1, 30),
    ("31–60 días", 31, 60),
    ("61–90 días", 61, 90),
    ("Más de 90", 91, 100_000),
]


def cargar_consultas(ruta: Path) -> dict[str, str]:
    texto = ruta.read_text(encoding="utf-8")
    partes = re.split(r"^-- name: (\w+)\s*$", texto, flags=re.M)
    return {partes[i]: partes[i + 1].strip() for i in range(1, len(partes), 2)}


def ejecutar(con: sqlite3.Connection, consultas: dict, hoy: str) -> dict[str, pd.DataFrame]:
    return {nombre: pd.read_sql_query(sql, con, params={"hoy": hoy}) for nombre, sql in consultas.items()}


def calcular_kpis(datos: dict[str, pd.DataFrame], hoy: str) -> dict:
    f = datos["saldo_por_factura"].copy()
    f["vencimiento"] = pd.to_datetime(f["vencimiento"])
    corte = pd.Timestamp(hoy)
    f["dias_vencida"] = (corte - f["vencimiento"]).dt.days
    con_saldo = f[f["saldo"] > 0.01]
    vencidas = con_saldo[con_saldo["dias_vencida"] > 0]

    facturado = f["monto"].sum()
    cobrado = f["cobrado"].sum()
    saldo = con_saldo["saldo"].sum()
    saldo_vencido = vencidas["saldo"].sum()

    # DSO: días de venta pendientes de cobro, sobre los últimos 90 días de facturación
    ult90 = f[pd.to_datetime(f["emision"]) > corte - pd.Timedelta(days=90)]["monto"].sum()
    dso = round(saldo / ult90 * 90, 1) if ult90 else 0.0

    # Aging: saldo pendiente por antigüedad
    aging = []
    for nombre, desde, hasta in TRAMOS:
        mask = (con_saldo["dias_vencida"] >= desde) & (con_saldo["dias_vencida"] <= hasta)
        aging.append({"tramo": nombre, "saldo": round(con_saldo.loc[mask, "saldo"].sum(), 2)})

    # Morosidad por segmento: saldo vencido / facturado vencido
    seg = []
    for segmento, g in f[f["dias_vencida"] > 0].groupby("segmento"):
        venc_g = g[g["saldo"] > 0.01]["saldo"].sum()
        seg.append({
            "segmento": segmento,
            "morosidad": round(venc_g / g["monto"].sum() * 100, 1),
            "saldo_vencido": round(venc_g, 2),
        })
    seg.sort(key=lambda s: -s["morosidad"])

    dias = datos["dias_de_pago"]
    dias_seg = (dias.groupby("segmento")["dias"].mean().round(1).sort_values(ascending=False)
                .reset_index().to_dict("records"))
    pct_en_termino = round((dias["dias"] <= 0).mean() * 100, 1) if len(dias) else 0.0

    evol = datos["evolucion_mensual"].copy()
    # solo meses cuyas facturas ya vencieron (emitidas hace más de 30 días), para no distorsionar la efectividad
    limite = (corte - pd.Timedelta(days=31)).strftime("%Y-%m")
    evol = evol[evol["mes"] < limite]
    evol["efectividad"] = (evol["cobrado"] / evol["facturado"] * 100).round(1)

    return {
        "hoy": hoy,
        "facturado": round(facturado, 2),
        "cobrado": round(cobrado, 2),
        "efectividad": round(cobrado / facturado * 100, 1) if facturado else 0.0,
        "saldo": round(saldo, 2),
        "saldo_vencido": round(saldo_vencido, 2),
        "morosidad": round(saldo_vencido / facturado * 100, 1) if facturado else 0.0,
        "dso": dso,
        "pct_en_termino": pct_en_termino,
        "aging": aging,
        "segmentos": seg,
        "dias_por_segmento": dias_seg,
        "evolucion": evol.to_dict("records"),
        "medios": datos["medios_de_pago"].to_dict("records"),
        "top_deudores": datos["top_deudores"].to_dict("records"),
    }


def hallazgos(k: dict) -> list[str]:
    """Conclusiones en texto a partir de los números."""
    h = []
    peor = k["segmentos"][0] if k["segmentos"] else None
    if peor:
        h.append(f"El segmento {peor['segmento']} tiene la mayor morosidad ({peor['morosidad']}%).")
    mas90 = next(a for a in k["aging"] if a["tramo"] == "Más de 90")
    if k["saldo"]:
        pct90 = mas90["saldo"] / k["saldo"] * 100
        h.append(f"El {pct90:.0f}% del saldo pendiente tiene más de 90 días de atraso: es la deuda más difícil de recuperar.")
    if k["evolucion"]:
        peor_mes = min(k["evolucion"], key=lambda e: e["efectividad"])
        if peor_mes:
            h.append(f"El mes con menor efectividad de cobro fue {peor_mes['mes']} ({peor_mes['efectividad']}%).")
    h.append(f"El {k['pct_en_termino']}% de los pagos se hizo en término o antes del vencimiento.")
    return h


def generar_html(k: dict, destino: Path) -> None:
    plantilla = (RAIZ / "plantilla.html").read_text(encoding="utf-8")
    datos = dict(k, hallazgos=hallazgos(k))
    html = plantilla.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False))
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cobranzas.db")
    parser.add_argument("--hoy", default=date.today().isoformat())
    parser.add_argument("--salida", default="docs/index.html")
    args = parser.parse_args()

    consultas = cargar_consultas(RAIZ / "sql" / "consultas.sql")
    with sqlite3.connect(args.db) as con:
        datos = ejecutar(con, consultas, args.hoy)
    k = calcular_kpis(datos, args.hoy)
    generar_html(k, Path(args.salida))

    print(f"Efectividad de cobro: {k['efectividad']}% | Morosidad: {k['morosidad']}% | DSO: {k['dso']} días")
    for linea in hallazgos(k):
        print(" -", linea)
    print(f"Dashboard: {args.salida}")


if __name__ == "__main__":
    main()
