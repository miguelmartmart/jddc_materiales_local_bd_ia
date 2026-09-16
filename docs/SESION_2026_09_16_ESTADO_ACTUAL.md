# Estado sesion 16/09/2026 — v9.0.0 Informe Maestro

> Fichero de estado actual. Fecha: 16/09/2026. Reemplaza versiones anteriores.

---

## Resumen de lo implementado en esta sesion

### Nuevo: boton INFORME MAESTRO

Boton azul oscuro en el Probador Visual: **Informe maestro**

Llama al endpoint GET /informe-maestro que:
1. Conecta a Firebird directamente (SELECT COUNT(*), SELECT FIRST) — datos BD reales
2. Llama a la API mPYME (permiso+browse por cada clase) — respuestas API reales
3. Cruza ambas fuentes: por cada clase API -> registros reales en BD -> estado API real
4. Genera 5 niveles de texto copiable + panel visual con graficos y tabla cruzada

### 5 pestanas del informe maestro

| Pestana | Contenido | Para quien |
|---|---|---|
| Visual | KPIs reales BD + tabla cruzada BD+API + top tecnicos | Ver rapido |
| Ejecutivo | 10 lineas. Modulos, disponibilidad, estado API | Gerente |
| Por modulo | Lista por modulo con BD+API | Responsable area |
| Datos reales | Tabla por clase: BD + API + estado + accion | Decision compra |
| Tecnico | Peticion HTTP exacta por clase | IT/Desarrollador |
| Distrito K | Correo listo para enviar: problemas + licencias + preguntas | Enviar a DK |

### Datos que obtiene del Firebird (100% reales, SELECT)

- CLIENTE: n clientes
- PROVEED: n proveedores
- ARTICULO: n articulos
- RECURSO: n tecnicos + muestra real + top por horas
- PROYECTOS: n proyectos + activos
- PREUTILLIN: n imputaciones reales de horas en proyectos + muestra + top tecnicos
- PREPREVLIN: n previsiones de horas en proyectos
- REPARA: n partes SAT + abiertos + muestra
- RABUTILLIN: n horas de tecnico en partes SAT + muestra + top tecnicos
- REPOBJETO: n objetos de cliente
- REPINSTALACION: n instalaciones
- DOCCAB: distribucion por tipo, albaranes vinculados a proyectos

### Datos que obtiene de la API mPYME (100% reales, llamadas HTTP)

Por cada clase API:
- permiso(): code + msg
- browse(): code + msg (captura el mensaje exacto del servidor)

### Logica de cruce

Por cada clase API calcula:
- bd_estado: datos_reales | tabla_vacia | fb_no_accesible | error
- api_estado: funciona | mantenimiento | sin_licencia | error_params | sin_sesion
- recomendacion: disponible_sin_licencia_extra | comprar_licencia_vale_la_pena | estudiar_antes_de_comprar | tabla_vacia_cambiar_flujo

### Bug corregido en esta sesion

_renderCatalogoDatos y _renderValidarBD estaban dentro del addEventListener
(scope privado) -> ReferenceError al llamarlas desde doCatalogoDatos.
Fix: insertar }); correcto tras _ejecutarPlanPruebaInspector (linea 4121),
eliminar el viejo }); del final del archivo.

---

## Estado actual de la API mPYME (JDDC)

| Problema | Evidencia | Accion |
|---|---|---|
| Modo mantenimiento activo | browse()=code=6, msg="No es posible acceder a la BD" | Contactar DK o desactivar en SQL Obras |
| Modulo Proyectos sin licencia | new(proyectos)=code=5 "No dispone de licencia" | Contratar con DK |
| Reparaciones: probar con mant OFF | permiso=0 en repobjetos, tipostrabajo | Con mant OFF probar browse |

## Commits recientes

- 2161f2c feat(informe-maestro): endpoint + render visual + 5 niveles texto
- 7c8b31e fix(scope): _renderCatalogoDatos fuera del addEventListener
- 1d6dab8 feat(validar-bd): endpoint /validar-datos-bd
- e574723 feat(catalogo): 5 niveles exportacion
- 82c8040 feat(catalogo): catalogo 100 datos API mPYME

## Para retomar en nueva sesion

1. git pull origin main en la VM
2. Reiniciar DEVIA + Ctrl+F5
3. Conectarse en pestana Conexion
4. Pulsar Informe maestro
5. Ver pestana Visual -> confirmar top tecnicos reales
6. Ver pestana Distrito K -> copiar correo y enviar
7. Una vez DK desactive mantenimiento -> repetir Diagnostico completo
