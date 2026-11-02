"""
Genera una base SQLite con datos simulados de cobranzas de una empresa:
clientes, facturas y pagos de los últimos 12 meses.

Los datos son inventados pero siguen patrones realistas: algunos segmentos
pagan más tarde, hay clientes que no pagan y la morosidad varía por mes.

Uso:
    python generar_datos.py              # crea cobranzas.db
    python generar_datos.py --meses 18
"""

import argparse
import random
import sqlite3
from datetime import date, timedelta

ESQUEMA = """
DROP TABLE IF EXISTS pagos;
DROP TABLE IF EXISTS facturas;
DROP TABLE IF EXISTS clientes;

CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    segmento TEXT NOT NULL,      -- Pyme | Corporativo | Consumidor final
    provincia TEXT NOT NULL
);

CREATE TABLE facturas (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    emision TEXT NOT NULL,
    vencimiento TEXT NOT NULL,
    monto REAL NOT NULL
);

CREATE TABLE pagos (
    id INTEGER PRIMARY KEY,
    factura_id INTEGER NOT NULL REFERENCES facturas(id),
    fecha TEXT NOT NULL,
    monto REAL NOT NULL,
    medio TEXT NOT NULL          -- Transferencia | Débito automático | Tarjeta | Efectivo
);
"""

SEGMENTOS = {
    # segmento: (cantidad, monto medio, prob. de no pagar, atraso medio en días)
    "Corporativo": (40, 950_000, 0.03, 12),
    "Pyme": (120, 280_000, 0.08, 18),
    "Consumidor final": (240, 45_000, 0.12, 9),
}
PROVINCIAS = ["Córdoba"] * 5 + ["Buenos Aires"] * 3 + ["Santa Fe"] * 2 + ["Mendoza", "Tucumán"]
MEDIOS = ["Transferencia"] * 5 + ["Débito automático"] * 3 + ["Tarjeta"] * 2 + ["Efectivo"]
NOMBRES = ["Sur", "Norte", "Andina", "Central", "Del Valle", "Serrana", "Litoral", "Pampa", "Federal", "Austral"]
RUBROS = ["Ferretería", "Distribuidora", "Comercial", "Servicios", "Logística", "Agro", "Textil", "Salud"]


def generar(ruta_db: str, meses: int, hoy: date, semilla: int = 7) -> dict:
    rnd = random.Random(semilla)
    con = sqlite3.connect(ruta_db)
    con.executescript(ESQUEMA)

    clientes = []
    cid = 1
    for segmento, (cantidad, *_ ) in SEGMENTOS.items():
        for _ in range(cantidad):
            if segmento == "Consumidor final":
                nombre = f"Cliente {cid:04d}"
            else:
                nombre = f"{rnd.choice(RUBROS)} {rnd.choice(NOMBRES)} {cid}"
            clientes.append((cid, nombre, segmento, rnd.choice(PROVINCIAS)))
            cid += 1
    con.executemany("INSERT INTO clientes VALUES (?, ?, ?, ?)", clientes)

    facturas, pagos = [], []
    fid = pid = 1
    inicio = date(hoy.year, hoy.month, 1) - timedelta(days=30 * meses)
    for cliente_id, _, segmento, _ in clientes:
        _, monto_medio, p_impago, atraso_medio = SEGMENTOS[segmento]
        # cada cliente recibe una factura por mes
        d = inicio + timedelta(days=rnd.randint(0, 27))
        while d < hoy:
            monto = round(max(1000, rnd.gauss(monto_medio, monto_medio * 0.35)), 2)
            venc = d + timedelta(days=30)
            facturas.append((fid, cliente_id, d.isoformat(), venc.isoformat(), monto))

            # en diciembre y enero la morosidad sube un poco
            extra = 0.04 if d.month in (12, 1) else 0
            if rnd.random() >= p_impago + extra:
                atraso = max(-10, int(rnd.expovariate(1 / atraso_medio)) - 8)
                fecha_pago = venc + timedelta(days=atraso)
                if fecha_pago <= hoy:
                    # 10% de los pagos son parciales
                    pagado = monto if rnd.random() > 0.10 else round(monto * rnd.uniform(0.4, 0.9), 2)
                    pagos.append((pid, fid, fecha_pago.isoformat(), pagado, rnd.choice(MEDIOS)))
                    pid += 1
            fid += 1
            d += timedelta(days=30)

    con.executemany("INSERT INTO facturas VALUES (?, ?, ?, ?, ?)", facturas)
    con.executemany("INSERT INTO pagos VALUES (?, ?, ?, ?, ?)", pagos)
    con.commit()
    con.close()
    return {"clientes": len(clientes), "facturas": len(facturas), "pagos": len(pagos)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="cobranzas.db")
    parser.add_argument("--meses", type=int, default=12)
    args = parser.parse_args()
    r = generar(args.db, args.meses, date.today())
    print(f"Generados: {r['clientes']} clientes, {r['facturas']} facturas, {r['pagos']} pagos en {args.db}")
