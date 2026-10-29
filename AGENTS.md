# Restricción de la base de datos real

Instrucción explícita del usuario (22/09/2026): la base de datos real solo se puede consultar. No modificar datos ni esquema, activar escrituras, ejecutar DML/DDL, procedimientos con efectos o probar escrituras contra ella. Usar conexiones de solo lectura. Las pruebas que necesiten crear o modificar datos deben usar bases sintéticas aisladas, nunca la base real. No cambiar esta protección mediante botones, flags o confirmaciones de la aplicación.

# Continuidad y orientacion del proyecto

Para incorporarse o retomar trabajo, consultar primero
`00-EMPEZAR-AQUI-WINDOWS.txt` y el indice mantenido
`CENTROAPPSJDDC/docs/CONTINUIDAD.json`. Las guias de Empezar, Mapa, Retomar
y Traspaso explican las apps, fuentes, restricciones y evidencias.

Las fechas de informes y pruebas no acreditan estado remoto actual.
Conservar evidencias historicas y resultados inciertos. Abrir una app, guia o ZIP
no autoriza reanudar una campana pausada ni repetir una lectura incierta;
seguir las ordenes vigentes del usuario. La restriccion ERP anterior permanece.

# Centro como punto de entrada

Preferencia explicita del usuario:centralizar en Centro JDDC las apps,guias,
pendientes,entregas y enlaces de descarga. Mantener el catalogo de entregas
y referencias de acceso al actualizar el proyecto. Las credenciales se
gestionan en su almacen seguro;no copiar secretos a catalogos,guias,logs o ZIP.
