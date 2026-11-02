-- Consultas del dashboard de cobranzas.
-- Cada bloque empieza con "-- name: <nombre>" para que analisis.py lo encuentre.
-- :hoy es la fecha de corte del análisis (AAAA-MM-DD).

-- name: saldo_por_factura
-- Base del análisis: cuánto se facturó, cuánto se cobró y cuánto queda por cobrar en cada factura.
WITH cobrado AS (
    SELECT factura_id, SUM(monto) AS cobrado, MAX(fecha) AS ultimo_pago
    FROM pagos
    WHERE fecha <= :hoy
    GROUP BY factura_id
)
SELECT
    f.id,
    f.cliente_id,
    c.segmento,
    c.provincia,
    f.emision,
    f.vencimiento,
    f.monto,
    COALESCE(co.cobrado, 0)            AS cobrado,
    f.monto - COALESCE(co.cobrado, 0)  AS saldo,
    co.ultimo_pago
FROM facturas f
JOIN clientes c ON c.id = f.cliente_id
LEFT JOIN cobrado co ON co.factura_id = f.id
WHERE f.emision <= :hoy;

-- name: evolucion_mensual
-- Facturado vs. cobrado por mes de emisión.
WITH cobrado AS (
    SELECT factura_id, SUM(monto) AS cobrado FROM pagos WHERE fecha <= :hoy GROUP BY factura_id
)
SELECT
    substr(f.emision, 1, 7)               AS mes,
    ROUND(SUM(f.monto), 2)                AS facturado,
    ROUND(SUM(COALESCE(co.cobrado, 0)), 2) AS cobrado
FROM facturas f
LEFT JOIN cobrado co ON co.factura_id = f.id
WHERE f.emision <= :hoy
GROUP BY mes
ORDER BY mes;

-- name: dias_de_pago
-- Días entre vencimiento y pago (negativo = pagó antes de vencer).
SELECT
    c.segmento,
    julianday(p.fecha) - julianday(f.vencimiento) AS dias
FROM pagos p
JOIN facturas f ON f.id = p.factura_id
JOIN clientes c ON c.id = f.cliente_id
WHERE p.fecha <= :hoy;

-- name: medios_de_pago
SELECT medio, COUNT(*) AS cantidad, ROUND(SUM(monto), 2) AS monto
FROM pagos
WHERE fecha <= :hoy
GROUP BY medio
ORDER BY monto DESC;

-- name: top_deudores
-- Clientes con mayor saldo vencido.
WITH cobrado AS (
    SELECT factura_id, SUM(monto) AS cobrado FROM pagos WHERE fecha <= :hoy GROUP BY factura_id
)
SELECT
    c.nombre,
    c.segmento,
    c.provincia,
    COUNT(*)                                          AS facturas_vencidas,
    ROUND(SUM(f.monto - COALESCE(co.cobrado, 0)), 2)  AS saldo_vencido,
    CAST(MAX(julianday(:hoy) - julianday(f.vencimiento)) AS INTEGER) AS dias_max_atraso
FROM facturas f
JOIN clientes c ON c.id = f.cliente_id
LEFT JOIN cobrado co ON co.factura_id = f.id
WHERE f.vencimiento < :hoy
  AND f.monto - COALESCE(co.cobrado, 0) > 0.01
GROUP BY c.id
ORDER BY saldo_vencido DESC
LIMIT 10;
