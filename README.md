# Dashboard de Cobranzas

Análisis de cobranzas y morosidad de una empresa con **SQL y Python**, publicado como un **dashboard web**.

**Ver el dashboard:** https://milagroshuppi.github.io/dashboard-cobranzas/

Responde las preguntas que se hace un área de finanzas o de cobranzas: ¿cuánto de lo facturado se cobra?, ¿cuánta deuda está vencida y hace cuánto?, ¿qué tipo de clientes paga más tarde?, ¿a quién hay que llamar primero?

## Indicadores

- **Efectividad de cobro:** cobrado sobre facturado.
- **Morosidad:** saldo vencido sobre facturado, total y por segmento de cliente.
- **DSO (Days Sales Outstanding):** días promedio que tarda la empresa en cobrar.
- **Aging:** saldo pendiente separado por antigüedad (al día, 1–30, 31–60, 61–90 y más de 90 días).
- **Pagos en término**, días promedio de pago por segmento y medios de pago.
- **Ranking de clientes** con mayor saldo vencido.

El dashboard también genera automáticamente un resumen de **hallazgos** en texto a partir de los números.

## Cómo funciona

| Archivo | Qué hace |
| --- | --- |
| generar_datos.py | Crea una base SQLite con 400 clientes y 12 meses de facturas y pagos simulados |
| sql/consultas.sql | Consultas SQL del análisis (saldos, evolución mensual, días de pago, deudores) |
| analisis.py | Ejecuta las consultas, calcula los indicadores con pandas y genera el dashboard |
| plantilla.html | Diseño del dashboard (Chart.js) |
| docs/index.html | Dashboard final, publicado con GitHub Pages |
| tests/ | Tests con una base chica de resultados conocidos |

## Cómo correrlo

```bash
pip install -r requirements.txt
python generar_datos.py
python analisis.py
```

Después abrí docs/index.html en el navegador.

## Tests

```bash
pytest
```

Verifican los totales, el aging, el ranking de deudores y el porcentaje de pagos en término con datos cargados a mano.

## Tecnologías

Python · SQL (SQLite) · pandas · Chart.js · HTML/CSS · pytest · GitHub Pages

Los datos son simulados con fines de demostración.
