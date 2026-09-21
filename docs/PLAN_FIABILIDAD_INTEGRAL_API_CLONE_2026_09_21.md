# Fiabilidad integral de API Clone: análisis y criterios de aceptación

Fecha: 21/09/2026. Análisis del código y evidencias existentes, sin nueva ejecución contra Firebird ni cambios de datos.

## Qué se puede demostrar

Separar fidelidad de extracción (respuesta igual a las filas seleccionadas), integridad relacional (identidades y vínculos válidos), coherencia de negocio (reglas contrastadas) y verdad del hecho (el trabajo ocurrió en esa obra). Cada nivel necesita evidencias distintas. Una PK o una FK no prueba que el usuario seleccionara la obra correcta. El objetivo demostrable es cobertura del 100 % de una población y unas reglas explícitas en una instantánea; no certeza absoluta sobre hechos externos.

Estado actual: 17 clases API; inventario de restricciones limitado a PROYECTOS, OBRACAB, OBRALIN, RECURSO y PRESUPROYE. Los 213 tests aprobados y el caso pendiente no cubren toda la semántica de las 17 clases. Rechazar filtros desconocidos evita resultados engañosos, pero no implementa esos filtros. Rechazar offset no permite una auditoría exhaustiva paginada. Las listas limitadas y la muestra real de diez líneas no certifican toda la base.

## Códigos y nombres

1. Identificar entidad, tabla, empresa/base y clave completa. CODIGO no es un identificador universal entre tablas.
2. Comprobar unicidad, componentes no nulos y restricciones realmente declaradas.
3. Resolver el nombre por la clave, nunca la clave por parecido del nombre.
4. Distinguir descripción libre, nombre actual y nombre histórico guardado en documentos. No asumir que OBRALIN.NOMBRE significa el nombre de proyecto o de técnico.
5. Si existe un nombre redundante con significado validado, comparar conservando el original y una versión normalizada. Mayúsculas y espacios pueden ser variaciones; eliminar acentos o usar similitud solo genera candidatos de revisión.
6. Coincidir no es evidencia independiente si ambos valores vienen del mismo maestro. Diferir puede ser legítimo por cambio de razón social, renombrado o descripción histórica.
7. Nunca reasignar una línea, fusionar personas ni cambiar una FK automáticamente por coincidencia de nombres.

## Contrastes por área

| Área | Contraste propuesto | Condición o límite |
|---|---|---|
| Obras | OBRALIN.CODPROYECTO frente a OBRALIN.CODCAB → OBRACAB.CODPROYECTO | Dos rutas coincidentes corroboran estructura, no el hecho real; nulos y contradicciones se clasifican por separado. |
| Recursos | Línea → RECURSO; comprobar identidad, tipo de recurso y vigencia a fecha del trabajo | Un recurso válido no demuestra persona asignada ni trabajo realizado. Contrastar parte, asignación o control horario si existen y su significado está validado. |
| Artículos | Referencia de línea → ARTICULO; unidad, conversión, fecha y movimientos de almacén relacionados | Una descripción puede diferir; stock o compra no equivale automáticamente a consumo de una obra. Validar documentos de origen. |
| Compras | DOCCAB, sus líneas y reparto por DOCLINIMPUTACION | Confirmar claves y fórmula real del reparto. Un documento puede financiar varias obras: no repetir su importe íntegro por proyecto. |
| Presupuestos | PRESUPROYE → documento y proyecto | Validar que la clase «partidas» representa realmente partidas; un enlace a presupuesto no lo demuestra. |
| Reparaciones | REPARA, proyecto/equipo/instalación, estados y líneas reales | REPCAR contiene características; investigar REPLIN antes de afirmar que se sirven materiales u horas. No sustituir tablas sin prueba de negocio. |
| Tipos | TIPO con discriminador de familia y clave completa | La auditoría documenta (TIPO,CODIGO); filtrar la familia correcta antes de llamarlo «tipo de trabajo». |
| Fabricación | FABCAB con clave completa y previsión | La auditoría documenta (CODMAESTRO,ESPREVISION,CODIGO); comprobar relaciones de sus líneas y consumos. |
| Maestros | Clientes/proveedores/equipos/instalaciones y referencias desde documentos | Cliente compartido, nombre o dirección compartidos no prueban pertenencia a proyecto. |

Las rutas no implementadas son propuestas a validar con metadatos, ejemplos del ERP y reglas de negocio. No se consideran evidencia obtenida.

## Matriz de pertenencia línea/cabecera

- Ambos proyectos presentes e iguales: coherente estructuralmente, pendiente de verdad de negocio.
- Ambos presentes y distintos: discrepancia; no elegir uno silenciosamente.
- Línea nula y cabecera informada: candidato a relación heredada, no confirmado sin regla del ERP.
- Línea informada y cabecera nula: referencia explícita con corroboración incompleta.
- Ambos nulos: proyecto no determinable con estas fuentes.
- Código informado sin maestro: referencia huérfana.
- Clave incompleta o varias coincidencias: identidad ambigua, rechazar lectura individual.

Aplicar el mismo análisis a real/previsto, unidades y fechas; no resolver contradicciones con COALESCE sin una regla documentada.

## Conciliación y pruebas que faltan

- Conjuntos: comparar claves completas y campos, no solo COUNT o SUM. Misma suma puede esconder omisiones y duplicados compensados.
- Cardinalidad: un JOIN a maestro no debe multiplicar una línea. En relaciones muchos-a-muchos validar el reparto y la conservación de cantidades/importes.
- Totales: separar previsto/real, anulaciones, devoluciones, descuentos, impuestos, moneda y redondeo. Confirmar si COSTE es importe o precio unitario; no inventar fórmulas.
- Fechas: distinguir creación, trabajo, documento, contabilización y cierre. Proyecto cerrado hoy no invalida un trabajo histórico. Usar reglas temporales contrastadas y tolerancias explícitas.
- Cobertura: recorrer todas las páginas con orden único por clave completa, detectar huecos/repeticiones y comprobar primera/última página, filtros y límites. Implementar paginación antes de certificar el conjunto mediante API.
- Consistencia temporal: comparar sobre copia o instantánea consistente. Consultas READ COMMITTED separadas pueden observar cambios normales. Mantener evidencia de las transacciones y de la versión/configuración de reglas.
- Referencia independiente: comparar con SQL Obras, partes y documentos de origen. Si dos informes reutilizan la misma consulta defectuosa, su acuerdo es circular.
- Propiedades: añadir filas de otra obra no altera la respuesta de A; permutar inserciones no altera el conjunto; browse/read conservan la clave; real y previsto no se solapan; ajustes negativos se conservan.
- Mutaciones: retirar deliberadamente un filtro o un segmento de clave y verificar que el test falla. Medir qué defectos detecta la batería, no solo porcentaje de líneas ejecutadas.
- Errores operativos: desconexión, timeout, respuesta parcial, contador nulo, esquema cambiado y reintentos deben producir fallo/desconocido explícito; nunca cero o éxito por defecto.
- Todos los endpoints/clases: matriz de claves, filtros, esquema de salida, límites, estados y errores. Validar también que el contrato rechaza lo no soportado.

## Tratamiento de errores humanos

No borrar ni arreglar silenciosamente. Conservar valor original, fuente, claves, discrepancia, regla, fecha y estado de revisión. Separar error técnico, referencia ausente, contradicción de negocio, excepción legítima y dato no verificable. Un negativo puede ser devolución; una obra cerrada puede tener histórico; una discrepancia de nombre puede ser un cambio legítimo.

La elegibilidad para nuevas operaciones es una regla distinta de la consulta histórica. La resolución humana debe registrar responsable, motivo, evidencia y fecha; el resultado original de la auditoría debe seguir disponible. Evitar que una excepción manual suprima futuros casos distintos.

## Informe completo y criterio de cierre

Por clase/regla: versión, SQL/parámetros, PK completa, población esperada/evaluada/excluida, nulos, incidencias, ejemplos por clave, campos discordantes, severidad, estado y acción. Hash del artefacto para integridad del archivo, sin llamarlo prueba de veracidad. No exponer credenciales ni datos personales innecesarios en exportaciones.

Mostrar por separado cobertura, integridad y conciliación. «100 % de 944001 filas evaluadas; 8 reglas con incidencias; 3 no verificables» es honesto. «99,9 % fiable» por sumar checks no lo es: un único fallo de pertenencia puede ser crítico.

Cierre técnico: todas las clases inventariadas; claves y semántica validadas; todas las filas/páginas comprobadas en el alcance; cero diferencias inexplicadas en identidad/pertenencia/conjuntos; reglas pendientes visibles; errores operativos controlados; comparación independiente y revisión de excepciones. Si falta una condición, no certificar ese alcance.

Prioridad: (1) mapa completo de entidades/claves/familias y contratos; (2) política explícita línea/cabecera y pruebas de cardinalidad; (3) paginación e instantánea; (4) reparto y conciliación de compras/costes; (5) estados temporales y fuentes independientes; (6) discrepancias descriptivas como evidencia auxiliar. Comparar nombres antes de validar la entidad puede reforzar una asociación equivocada.
