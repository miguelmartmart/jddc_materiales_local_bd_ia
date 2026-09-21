# DEVIA FRONTEND CONTEXT
# Chat web UI — conecta con el backend DEVIA en puerto 8001.

```json
{
  "module": "frontend",
  "description": "Interfaz web del chat IA DEVIA. HTML/JS estático servido por FastAPI.",
  "last_updated": "03/07/2026",

  "backend_connection": {
    "url": "http://localhost:8001",
    "endpoints": {
      "chat": "POST /api/chat/send",
      "config": "GET/POST /api/chat/config",
      "health": "GET /health"
    }
  },

  "ai_mode_actual": {
    "mode": "LOCAL_ONLY",
    "ai_local_only": true,
    "model": "Qwen3 VL 30B @ 192.168.0.36",
    "note": "El fallback multi-modelo está DESHABILITADO. Solo usa la IA local LAN."
  },

  "arranque": {
    "script": "ARRANCAR_DEVIA.bat (doble clic en bots/interjddcia/)",
    "url_local": "http://localhost:8001",
    "url_red": "http://192.168.0.38:8001"
  },

  "db_mode_selector": {
    "description": "Selector de modo de BD en la barra del chat. Permite elegir entre BD Real, Simulada o Sin BD sin recargar la página.",
    "element_id": "chat-db-mode",
    "badge_id": "chat-db-mode-badge",
    "options": [
      { "value": "real",      "label": "🔥 BD Real",    "badge_color": "green"  },
      { "value": "simulator", "label": "🎭 Simulada",   "badge_color": "amber"  },
      { "value": "no_db",     "label": "💬 Sin BD",     "badge_color": "slate"  }
    ],
    "wire_js": "frontend/assets/js/modules/chat.js — sendMessage() lee #chat-db-mode y envía db_mode en el body del POST /api/chat/send",
    "backend_field": "db_mode en ChatRequest → service.py resuelve la cadena de fallback",
    "commit": "b7b9635 (03/07/2026)"
  },

  "responsive_ux": {
    "description": "Chat completamente responsivo con sidebar colapsable y modo pantalla completa.",
    "fullscreen_button": "⛶ — toggle position:fixed; inset:0. ESC para salir.",
    "sidebar_toggle": "btn-toggle-history — añade/quita clase .collapsed en #chat-history-sidebar",
    "mobile_breakpoint": "@media (max-width:640px) — sidebar oculto, labels ocultos, toolbar compacto",
    "layout": "#chat-outer llena viewport height; #chat-main ocupa espacio restante con flex",
    "commit": "b7b9635 (03/07/2026)"
  },

  "changelog": [
    {
      "date": "03/07/2026",
      "commit": "b7b9635",
      "changes": [
        "Selector #chat-db-mode (Real/Simulada/Sin BD) con badge de color en tiempo real",
        "Layout responsivo: #chat-outer flex-col, sidebar colapsable, toolbar wrappable",
        "Botón ⛶ fullscreen (position:fixed; inset:0) + ESC para salir",
        "Mobile breakpoint 640px: sidebar y labels ocultos automáticamente"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "51d0234",
      "changes": [
        "Fix error 400 chat IA: max_tokens clamp en jddcia_provider.py",
        "config.json: lan_model_max_tokens=2048, lan_model_context_limit=4096",
        "Router /api/database/tables devuelve 200+warning en vez de 500 cuando Firebird no disponible"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "d08370b",
      "changes": [
        "metadata_builder: /tables devuelve 200 con lista vacía cuando Firebird no alcanzable",
        "metadata_builder.js: toast de advertencia en vez de error bloqueante"
      ]
    },
    {
      "date": "03/07/2026",
      "commit": "2d1db83",
      "changes": [
        "marked.min.js: CDN → local (bloqueado por Tracking Prevention del navegador)",
        "database_config.js: degradación graceful cuando /tables devuelve vacío"
      ]
    }
  ],

  "related_devia": [
    "bots/interjddcia/DEVIA.MD (documentación principal)",
    "frontend/assets/js/modules/DEVIA.MD (módulos JS)",
    "backend/modules/chat/DEVIA.MD (chat service)"
  ]
}
```

### Verificación HTTP y caché — 17/09/2026
El servidor 8001 ya carga el endpoint proyectos-buscar y la respuesta actividad. Verificado por HTTP: proyecto 10 devuelve 6 recursos y 2507 líneas MO; 45215 devuelve 26 recursos y 6490 líneas MO. Queda superada la nota anterior de backend pendiente de reinicio. Se actualiza en frontend/index.html la versión de api_clone.js a 20260917-activity-2 para descargar el renderizador nuevo al recargar. HTML y JS servidos comprobados por HTTP; no se ha inspeccionado la pestaña del usuario. No confundir líneas (incluidas previsiones) con imputaciones reales certificadas.


## Informe TXT y distribución — 21/09/2026
Botón permanente en cabecera API Clone: «Comprobar y exportar informe TXT», más acceso a checks y ayudas. GET /api/api-clone/utilidades/informe-fiabilidad.txt ejecuta los 13 checks globales y devuelve TXT UTF-8 sin caché con SQL, poblaciones, incidencias, estados, ayudas, pendientes y JSON completo con SHA-256. La huella no certifica veracidad. Errores de consulta aparecen como no verificables, no como éxitos. No ejecuta pytest ni compara cada endpoint con el ERP, ni certifica estados/bloqueos o pertenencia de negocio al 100 %. Las consultas no comparten una instantánea.
Retirados del Probador los badges históricos de garantía absoluta; revisada la afirmación de equivalencia con mPYME. Versión visible 2026-09-21.1 y versión de JS actualizada.
Validación: 72 passed, 11 xfailed (defectos pendientes de auditoría), 8 tests Node correctos y sintaxis JS válida. Contrato HTTP comprobado con TestClient, sin acceso a la VM.
La carpeta utilidades y la integración estaban sin registrar/confirmar en Git local: un pull en otra máquina no transporta estos cambios. Parche de entrega: docs/api_clone_utilidades_20260921.patch. No se ha publicado ni aplicado en la VM.


## Publicación y evidencia ampliada — 21/09/2026
Informe TXT ampliado a 27 checks en seis grupos y catálogo real de PK/FK/UNIQUE en cinco tablas. Se comprueban nulos/duplicados de claves completas, relación cabecera-línea, proyecto y previsión discrepantes, recursos sin identificar y ambigüedad de CODIGO sin CODCAB. El inventario incluye segmentos ordenados y destino de las FKs; no infiere relaciones declaradas cuando no existen.
Ejecución desde este PC, Firebird en transacción de solo lectura: 16 correctos, 8 revisar, 3 no verificables; 944001 líneas y 1216 proyectos en esta ejecución. No hay instantánea común garantizada. Evidencia íntegra: docs/informe_fiabilidad_2026_09_21.txt. OBRALIN tiene PK (CODCAB,CODIGO); 6401 grupos de CODIGO repetidos entre cabeceras. Las incidencias necesitan interpretación de negocio; no se modificaron datos.
Pruebas: 147 passed + 11 xfailed, 8 Node. Auditoría con --runxfail: 20 passed y 11 failed. Los 11 fallos se documentan como defectos abiertos, nunca como éxitos; no se certifica el 100 %. Logs en docs/tests_api_clone_2026_09_21.txt y docs/fallos_api_clone_2026_09_21.txt. Reproducir lectura real con .venv\Scripts\python.exe scripts/verificar_informe_fiabilidad.py.
Despliegue: tras incorporar el commit en la VM, reiniciar backend y Ctrl+F5. La cabecera debe mostrar versión 2026-09-21.2 y el botón TXT. Los párrafos anteriores sobre cambios sin publicar describen el estado anterior a esta publicación.


## Refuerzo ante errores humanos — 21/09/2026, versión de interfaz 2026-09-21.3
Diez casos antes xfail pasan como regresiones ordinarias: filtros no soportados rechazados (incluido offset), valores vacíos/estructurados rechazados, límites validados, read de OBRALIN exige CODCAB:CODIGO, read ambiguo falla, cuerpos HTTP no ignoran extras, ESPREVISION=0/1 separa clases, FINOBRA se devuelve, ranking incluye ajustes negativos. Los totales ausentes/incorrectos fallan y las listas indican truncamiento. Rechazar FINOBRA/offset no implementa esos filtros: evita ignorarlos silenciosamente.
El Probador permite escribir la clave compuesta para read de líneas. Cambio incompatible intencional: el CODIGO aislado ya no sirve para leer OBRALIN. La clave identifica una fila, no certifica la obra elegida por una persona. Browse/read marcan fiabilidad_negocio=no_verificada; no se corrigen ni reasignan datos del ERP.
213 pruebas Python aprobadas, 1 xfail pendiente y 9 Node aprobadas. Incluye 20 semillas reproducibles de datos mezclados, entradas malformadas, NULL, límites, duplicados, claves sobredimensionadas y error humano de proyecto con verificación de que no cambia la BD. SQLite valida lógica; no sustituye Firebird.
Pendiente AUD-05: líneas sin CODPROYECTO pero relacionadas mediante cabecera. No se infiere pertenencia automáticamente; la cobertura declarada es la referencia explícita. La prueba pendiente ahora compara solo ESPREVISION=0, pues previsiones se consultan por separado. Los informes históricos con 11 fallos describen el estado anterior.
Lectura real de solo lectura en este PC: proyecto 45215 tiene 702 líneas no previstas y 8168 previstas; cinco de cada grupo contrastadas por PK completa con read. Muestra limitada, no certificación global. Evidencia: docs/lecturas_api_clone_2026_09_21.json. Reproducción: scripts/verificar_lecturas_api_clone.py. Resultados de tests: docs/tests_api_clone_refuerzo_2026_09_21.txt. No se han probado todos los estados ni permisos del ERP, ni se demuestra fiabilidad absoluta.


## Integridad ampliada, solo consultas — 21/09/2026, versión 2026-09-21.4
Inventario PK/FK/UNIQUE en las 15 tablas de las 17 clases más OBRACAB (incluida en esas 15). Nuevos contrastes dinámicos por restricción: componentes nulos, grupos duplicados por clave completa, huérfanos no nulos y multiplicación de destinos de JOIN. No se unen entidades por nombres ni se reasignan registros. PK ausente, metadatos incompletos y errores de consulta quedan no verificables. NULL en UNIQUE/FK se informa separadamente; no se declara huérfano por un componente NULL.
Se añaden CHK-028/029/030 para proyecto solo en cabecera, solo en línea o ausente en ambas. La relación heredada sigue pendiente de regla de negocio; no se inventa una asignación.
El endpoint TXT abre una conexión Firebird READ COMMITTED READ ONLY, solo permite SELECT único, hace rollback y cierra incluso ante error. No es una instantánea común: cambios concurrentes siguen siendo una limitación declarada. Fallo de conexión devuelve 503, nunca un archivo de éxito aparente.
Browse acepta offset superior (no dentro de params), con orden estable para proyectos, recursos, proordutil y proordprev; otras clases rechazan offset positivo hasta validar orden completo. El Probador incluye posición inicial; cambiar clase, filtro o límite vuelve a cero. Páginas separadas no aseguran instantánea común.
Evidencia real: docs/informe_integridad_ampliada_2026_09_21.txt. Treinta checks de negocio: 18 correctos, 9 revisar, 3 no verificables. Estructura: 60 correctos, 19 informativos, 14 PK inventariadas, 20 no aplica y 1 no verificable (PK de PRESUPROYE); 21 checks de multiplicación de JOIN incluidos. Sin escrituras al ERP. El informe incluye SQL, conteos y ayudas; no certifica verdad del hecho ni comparación independiente con partes/ERP.
Pruebas nuevas ejecutan SQL real de los checks sobre SQLite sintético, comprueban ausencia de escrituras durante los checks, fallos y limpieza de conexión, mutación de segmento FK, destino duplicado y recorrido completo de páginas. Las tablas sintéticas de tests se crean solo en memoria. Se conserva un xfail de cobertura heredada desde cabecera, y siguen pendientes reglas de unidades/importes, fuentes independientes y paginación de otras clases.
