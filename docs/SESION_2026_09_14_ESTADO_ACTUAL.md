# Estado para retomar — 14/09/2026 (v4.0.0)

> **LEER ESTO PRIMERO antes de tocar nada.**

## Repo y commits

- **Repo:** bots/interjddcia rama main — commit **df9687a**
- **En VM:** `cd bots/interjddcia && git pull && restart DEVIA && Ctrl+F5`

```
df9687a  feat(super-diagnostico): Centro de Diagnostico Inteligente
b488beb  feat(diagnostico): Test BD new+cancel, seccion 9 diagnostico critico
e2ea2a3  fix(mapa-firebird): tipostrabajo→TIPO + datos reales muestras PROYECTOS
```

## NOVEDAD v4.0: 🎯 Centro de Diagnóstico Inteligente

Botón **🎯 Diagnóstico completo** (gradiente rojo-púrpura) en la barra del Probador.

### 4 fases automáticas (todas solo lectura)

| Fase | Qué hace | Resultado |
|---|---|---|
| F1 Firebird | Conexión directa + COUNT tablas | ✅/❌ |
| F2 IDs BD | Pool IDs reales todas clases (1 conexión) | N tablas con IDs |
| F3 Browse | 18 variantes base + IDs Firebird = ~38 var/clase × 17 clases | ✅/❌ por clase |
| F4 new+cancel | BD mPYME accesible? Sin persistir nada | ✅/❌ BD accesible |

### Lógica de conclusión automática

```
F4 new() = OK  → BD mPYME accesible → browse falla por formato params → enviar pregunta a Distrito K
F4 new() = KO  → BD mPYME NO accesible → reiniciar SQL Obras + PymeMobileServer.exe
Firebird KO    → Verificar .env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)
```

### Resultado visual
- **✅ verde** API FUNCIONAL — hay clases con datos reales
- **⚠️ ámbar** PARCIALMENTE FUNCIONAL — BD accesible pero browse en algunos falla
- **❌ rojo** REQUIERE INTERVENCIÓN — BD no accesible

### Paneles generados
1. 4 celdas semáforo de fases
2. Conclusiones en lenguaje natural
3. Tabla por clase: permiso/info/browse/IDs/variantes/registros/estado + muestra datos
4. F4 new+cancel con interpretación
5. 📧 Pregunta lista para Distrito K con botón 📋 Copiar
6. Botones: 📄 TXT · 💾 JSON · 🔄 Repetir

## Ficheros clave

| Fichero | Líneas | Sección |
|---|---|---|
| `backend/modules/api_explorer/router.py` | ~1845 | L1601: /super-diagnostico |
| `frontend/assets/js/modules/api_explorer.js` | ~3884 | L575: botón · L3188: doCentroDiagnostico() · L3662: _renderCentroDiag() |

## Problema pendiente: browse siempre code=6

Confirmado en sesiones anteriores:
- 17 clases → browse code=6 incluso con IDs reales de Firebird (64+ variantes)
- El super-diagnóstico prueba ahora hasta ~646 variantes automáticas
- **F4 new+cancel determina si es problema de BD o de formato de parámetros**

## Protocolo API mPYME

```
URL base: http://192.168.0.254:8081/ — POST form-urlencoded
Códigos: 0=OK, 1=sinLic, 2=sinPerm, 5=config/params/crash, 6=necesitaParam
```

## Endpoints del módulo

| Endpoint | Método | Descripción |
|---|---|---|
| `/super-diagnostico` | POST | **NUEVO** 4 fases exhaustivas |
| `/auto-probar` | POST | Clase+op, 60 intentos, info() auto |
| `/probar-todo-catalogo` | POST | Todas las clases, pool 1 conexión |
| `/valores-param` | POST | IDs reales para autocompletar |
| `/diagnostico-firebird` | GET | Estado BD + conteos tablas |
| `/test-new-cancel` | POST | Verifica BD mPYME |

## Pasos siguientes EN LA VM

1. `git pull` + reiniciar DEVIA + `Ctrl+F5`
2. Probador Visual → **🎯 Diagnóstico completo** (esperar 60-120 seg)
3. Ver si F4 da ✅ o ❌
4. Si ✅: copiar pregunta generada → enviar a Distrito K
5. Si ❌: reiniciar SQL Obras + PymeMobileServer.exe en servidor
