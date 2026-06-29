# PENDIENTE — Datos necesarios cuando se conecte la BD real

> Documento creado el 2026-06-29.
> Propósito: listar qué datos faltan en el simulador que impiden respuestas de ultra calidad,
> y qué verificar/importar cuando se disponga de conexión con la BD Firebird real.

---

## 1. Tipos de documento ausentes en el simulador

El simulador tiene **220 registros** en DOCCAB con exactamente estos TIPO:

| TIPO | Descripción | Registros simulados | Importetotal |
|------|-------------|---------------------|--------------|
| 13 | Factura proveedor | 85 | 353.866 € |
| 0 | Presupuesto cliente | 66 | 276.937 € |
| 11 | Pedido proveedor | 30 | 121.512 € |
| 2 | Albarán cliente | 22 | 65.610 € |
| 12 | Albarán proveedor | 17 | 82.832 € |

### ❌ Tipos ausentes (prioritarios)

| TIPO | Descripción | Por qué es crítico |
|------|-------------|-------------------|
| **3** | **Factura cliente** | Principal KPI de ingresos. Sin él, cualquier consulta de "facturación", "ventas", "top clientes por facturación" usa datos proxy (TIPO=2) o devuelve 0. |
| **1** | Pedido cliente | Sin él no se puede calcular tasa de conversión presupuesto→pedido→factura |
| **10** | Presupuesto proveedor | Útil para análisis de comparativas compra |
| **21** | Movimiento de almacén | Necesario para análisis de rotación de stock |

### Acción cuando se conecte la BD real
- Verificar que la importación incluye TIPO=3 y TIPO=1
- Si la exportación al simulador usa snapshot, confirmar que el script de snapshot no filtra por TIPO
- Ver: `backend/modules/db_simulator/snapshot_service.py` → `build_from_snapshot()`

---

## 2. Rango de fechas en el simulador vs BD real

El simulador tiene registros del **2026-04-23** al **2026-06-24** (2 meses escasos).

Esto provoca:
- Queries de "mes actual" (mes 4 o 5) devuelven 0-1 filas → el AI no puede analizar tendencias mensuales
- Queries de "evolución anual" devuelven solo 1 año → sin comparativa histórica
- Queries de "año anterior" devuelven 0 → no hay benchmark

### Acción cuando se conecte la BD real
- El snapshot debería incluir al menos **3 años de datos** para análisis de tendencia
- Verificar que `FECHA` y `FECHAEMISION` se importan correctamente (no NULL)
- Script de migración sugerido: `SELECT * FROM DOCCAB WHERE FECHA >= DATEADD(-3 YEAR TO CURRENT_DATE)`

---

## 3. Tabla CLIENTE — datos incompletos

El simulador tiene 51 clientes con `NOMBRECOMERCIAL` y `RAZONSOCIAL` poblados. Sin embargo:

- Solo 22 documentos TIPO=2 (albarán cliente) tienen `CODCLIENTE` enlazado a CLIENTE
- Los documentos TIPO=13 (factura proveedor) van a `PROVEED`, no a CLIENTE → no aplica para análisis de cartera de clientes
- Sin TIPO=3 (factura cliente), la "concentración de cartera por cliente" usa TIPO=2+0 como proxy

### Acción cuando se conecte la BD real
- Verificar que `DOCCAB.CODCLIENTE` está poblado en registros TIPO=3
- Verificar join: `DOCCAB.CODCLIENTE = CLIENTE.CODIGO` devuelve resultados
- La columna de nombre de cliente en el simulador es `NOMBRECOMERCIAL` (no `NOMBRE`)

---

## 4. Tabla DOCVAR — no existe en simulador

El sistema detectó un error histórico: `[SIM] Error en query: no such table: DOCVAR`.

`DOCVAR` existe en la BD Firebird real (variables de documento — campos extra por tipo).

### Acción cuando se conecte la BD real
- Evaluar si DOCVAR es necesaria para las consultas del chat
- Si sí: añadir a `backend/modules/db_simulator/schema.py` → `_SIMULATOR_TABLES` y crear la tabla en `schema.py`
- Si no: añadir alias `DOCVAR → None` en `helpers.py` → `_FIREBIRD_TABLE_ALIASES` para que el error sea claro

---

## 5. Columnas de DOCCAB relevantes para análisis de riesgo cliente

Para el análisis de "Concentración en Pocos Clientes" (Pareto/top-5), la query correcta necesita:

```sql
-- En BD real Firebird:
SELECT FIRST 10
  d.CODCLIENTE,
  c.NOMBRECOMERCIAL,
  COUNT(*) AS N_FACTURAS,
  CAST(SUM(d.IMPORTETOTAL) AS NUMERIC(15,2)) AS TOTAL_EUR,
  CAST(SUM(d.IMPORTETOTAL) * 100.0 /
    NULLIF((SELECT SUM(IMPORTETOTAL) FROM DOCCAB WHERE TIPO = 3), 0)
  AS NUMERIC(8,2)) AS PCT_DEL_TOTAL
FROM DOCCAB d
LEFT JOIN CLIENTE c ON d.CODCLIENTE = c.CODIGO
WHERE d.TIPO = 3  -- factura cliente
GROUP BY d.CODCLIENTE, c.NOMBRECOMERCIAL
ORDER BY TOTAL_EUR DESC
```

Esta query devuelve 0 en el simulador porque TIPO=3 no existe.
En el simulador se usa el proxy: TIPO IN (0, 2) (presupuestos + albaranes cliente).

---

## 6. Análisis de fiabilidad del simulador actual

| Consulta | Simulador | BD Real esperado |
|----------|-----------|-----------------|
| Total documentos | 220 | Miles |
| Top 5 clientes por facturación (TIPO=3) | ❌ 0 filas | ✅ Datos reales |
| Top 5 clientes por albaranes (TIPO=2) | ✅ 22 registros (proxy) | ✅ Datos reales |
| Distribución anual | ✅ Solo 2026 | ✅ 3+ años |
| Tendencia mensual | ⚠️ Solo abr-jun 2026 | ✅ Histórico |
| Tasa éxito presupuestos (TIPO=0→3) | ❌ TIPO=3 ausente | ✅ Dato real |

---

## 7. Prioridad de importación

Orden recomendado al conectar BD real:

1. **TIPO=3** (facturas cliente) — bloquea la mayoría de KPIs de ventas
2. **TIPO=1** (pedidos cliente) — bloquea análisis de conversión
3. **Histórico 3 años** — bloquea análisis de tendencia y estacionalidad
4. **DOCVAR** (si se necesita) — para campos extra de documento
5. **TIPO=21** (movimientos almacén) — para análisis de rotación de stock

---

*Documento de referencia — actualizar cuando se conecte la BD real o cuando el simulador se enriquezca.*
