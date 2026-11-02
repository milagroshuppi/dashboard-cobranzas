import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analisis import cargar_consultas, calcular_kpis, ejecutar, hallazgos  # noqa: E402
from generar_datos import ESQUEMA, generar  # noqa: E402

CONSULTAS = cargar_consultas(Path(__file__).resolve().parents[1] / "sql" / "consultas.sql")
HOY = "2026-10-31"


@pytest.fixture
def con():
    """Base chica con datos conocidos para verificar los cálculos."""
    c = sqlite3.connect(":memory:")
    c.executescript(ESQUEMA)
    c.executemany("INSERT INTO clientes VALUES (?,?,?,?)", [
        (1, "A", "Pyme", "Córdoba"),
        (2, "B", "Corporativo", "Córdoba"),
    ])
    c.executemany("INSERT INTO facturas VALUES (?,?,?,?,?)", [
        (1, 1, "2026-08-01", "2026-08-31", 1000),  # pagada en término
        (2, 1, "2026-09-01", "2026-10-01", 1000),  # pago parcial, vencida 30 días
        (3, 2, "2026-05-01", "2026-05-31", 2000),  # impaga, más de 90 días
        (4, 2, "2026-10-20", "2026-11-19", 500),   # todavía no vence
    ])
    c.executemany("INSERT INTO pagos VALUES (?,?,?,?,?)", [
        (1, 1, "2026-08-25", 1000, "Transferencia"),
        (2, 2, "2026-10-10", 400, "Tarjeta"),
    ])
    return c


def kpis(con):
    return calcular_kpis(ejecutar(con, CONSULTAS, HOY), HOY)


def test_consultas_cargadas():
    assert set(CONSULTAS) == {"saldo_por_factura", "evolucion_mensual", "dias_de_pago", "medios_de_pago", "top_deudores"}


def test_totales(con):
    k = kpis(con)
    assert k["facturado"] == 4500
    assert k["cobrado"] == 1400
    assert k["saldo"] == 3100
    assert k["saldo_vencido"] == 2600  # 600 de la factura 2 + 2000 de la factura 3


def test_aging(con):
    aging = {a["tramo"]: a["saldo"] for a in kpis(con)["aging"]}
    assert aging["Al día"] == 500
    assert aging["1–30 días"] == 600
    assert aging["Más de 90"] == 2000


def test_top_deudores_ordenado(con):
    top = kpis(con)["top_deudores"]
    assert top[0]["nombre"] == "B"
    assert top[0]["saldo_vencido"] == 2000


def test_pagos_en_termino(con):
    # un pago 6 días antes del vencimiento, otro 9 días después
    assert kpis(con)["pct_en_termino"] == 50.0


def test_hallazgos_no_vacios(con):
    assert len(hallazgos(kpis(con))) >= 3


def test_generador(tmp_path):
    r = generar(str(tmp_path / "x.db"), 6, date(2026, 10, 31), semilla=1)
    assert r["clientes"] == 400
    assert r["facturas"] > r["pagos"] > 0
