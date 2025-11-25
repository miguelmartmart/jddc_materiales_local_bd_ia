# 🚀 DEVIA - Sistema Completo de Análisis IA v3

**Documento Técnico de Referencia Rápida**

---

## 📋 ÍNDICE RÁPIDO

1. [Arquitectura](#arquitectura)
2. [Archivos del Sistema](#archivos)
3. [Flujo de Datos](#flujo)
4. [APIs y Endpoints](#apis)
5. [Configuración](#configuracion)
6. [Funciones JavaScript](#funciones)
7. [Estructura de Datos](#datos)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ ARQUITECTURA {#arquitectura}

```
┌─────────────────────────────────────────────────────────────┐
│                    NAVEGADOR (Cliente)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  enrichment-complete-v3.html (Estructura)            │  │
│  │  enrichment-complete-v3.css  (Estilos)               │  │
│  │  enrichment-complete-v3.js   (Lógica)                │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓ HTTP
┌─────────────────────────────────────────────────────────────┐
│                    SERVIDOR WEB                              │
│              python -m http.server 8000                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    API FIREBIRD                              │
│              firebird_api_v3.py :5000                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/normalize/count                                 │  │
│  │  /api/normalize/with-metadata                         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 API ENRIQUECIMIENTO IA                       │
│           start_enrichment_api.py :5001                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/enrichment/analyze                              │  │
│  │  /api/enrichment/test                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  PROVEEDORES IA                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │  Gemini  │  │   Groq   │  │  OpenAI  │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 ARCHIVOS DEL SISTEMA {#archivos}

### **Frontend (Cliente)**

| Archivo | Líneas | Función |
|---------|--------|---------|
| `enrichment-complete-v3.html` | 228 | Estructura HTML, selectores de modelos |
| `enrichment-complete-v3.css` | 245 | Estilos, colores, animaciones |
| `enrichment-complete-v3.js` | 683 | Lógica completa del sistema |

### **Backend (Servidor)**

| Archivo | Puerto | Función |
|---------|--------|---------|
| `firebird_api_v3.py` | 5000 | API para base de datos Firebird |
| `start_enrichment_api.py` | 5001 | API para análisis IA |

### **Configuración**

| Archivo | Ubicación | Contenido |
|---------|-----------|-----------|
| `api_keys.json` | `data_normalizer/config/` | API keys de proveedores |
| `ai_providers.py` | `data_normalizer/config/` | Modelos disponibles |
| `ai_config.py` | `data_normalizer/config/` | Configuración centralizada |

### **Documentación**

| Archivo | Propósito |
|---------|-----------|
| `README_V3_REFACTORIZADO.md` | Guía completa de uso |
| `DEVIA.md` | Este documento técnico |
| `CORRECCIONES_FINALES.md` | Historial de correcciones |

---

## 🔄 FLUJO DE DATOS {#flujo}

### **1. Carga de Datos**

```javascript
loadAllData()
  ↓
fetch('/api/normalize/count')  // Contar registros
  ↓
while (offset < total)
  fetch('/api/normalize/with-metadata')  // Cargar en lotes de 1000
  ↓
allData[] = 11,864 registros
  ↓
renderPage()  // Mostrar primera página (50 registros)
```

### **2. Análisis IA**

```javascript
runBatchAnalysis()
  ↓
for each item in allData
  ↓
  analyzeRow(index)
    ↓
    fetch('/api/enrichment/analyze', {
      nombre_articulo: "TUBO PVC 110MM",
      provider: "groq",
      task: "analisis_completo"
    })
    ↓
    response: {
      material_principal: "PVC",
      categoria: "FONTANERIA",
      familia: "TUBOS",
      marca: "",
      modelo: "",
      atributos: {...}
    }
    ↓
  row.ia_material = response.material_principal
  row.ia_categoria = response.categoria
  // ... etc
  ↓
  renderPage()  // Actualizar vista
```

### **3. Exportación**

```javascript
exportCSV()
  ↓
allData.forEach(row => csv += row.codigo + ";" + row.nombre + "...")
  ↓
Blob(csv) → Download
  ↓
"analisis_completo_2025-11-21.csv"
```

---

## 🌐 APIs Y ENDPOINTS {#apis}

### **API Firebird (Puerto 5000)**

#### `POST /api/normalize/count`
```json
Request:
{
  "host": "HOST1",
  "port": "3050",
  "database": "C:\\...\\2021.fdb",
  "username": "SYSDBA",
  "password": "masterkey",
  "table_name": "ARTICULO",
  "field_name": "NOMBRE"
}

Response:
{
  "success": true,
  "total": 11864
}
```

#### `POST /api/normalize/with-metadata`
```json
Request:
{
  ...connectionParams,
  "table_name": "ARTICULO",
  "field_name": "NOMBRE",
  "pk_field": "CODIGO",
  "limit": 1000,
  "offset": 0
}

Response:
{
  "success": true,
  "results": [
    {
      "codigo": "ABC123",
      "nombre_original": "TUBO PVC 110MM",
      "nombre_normalizado": "TUBO PVC 110MM"
    },
    ...
  ]
}
```

### **API Enriquecimiento IA (Puerto 5001)**

#### `POST /api/enrichment/analyze`
```json
Request:
{
  "nombre_articulo": "TUBO PVC 110MM",
  "provider": "groq",
  "task": "analisis_completo"
}

Response:
{
  "success": true,
  "result": {
    "material_principal": "PVC",
    "categoria": "FONTANERIA",
    "familia": "TUBOS",
    "marca": "",
    "modelo": "",
    "atributos": {
      "diametro": "110mm"
    },
    "urls_verificacion": [],
    "imagen_url": ""
  }
}
```

#### `POST /api/enrichment/test` ⚠️ PENDIENTE
```json
Request:
{
  "provider": "groq",
  "model": "groq/llama-3.3-70b-versatile"
}

Response:
{
  "success": true,
  "message": "Conexión exitosa"
}
```

---

## ⚙️ CONFIGURACIÓN {#configuracion}

### **localStorage Keys**

| Key | Contenido | Ejemplo |
|-----|-----------|---------|
| `ai_config` | Configuración de proveedores | `{gemini: {model, api_key, base_url}, groq: {...}, openai: {...}}` |
| `ai_prompts` | Prompts personalizados | `{system: "...", user: "..."}` |

### **Modelos Disponibles**

#### **Gemini (7 modelos)**
```javascript
- gemini-2.0-flash-exp
- gemini-2.0-flash-thinking-exp-1219
- gemini-exp-1206
- gemini-exp-1121
- gemini-1.5-pro
- gemini-1.5-flash
- gemini-1.5-flash-8b
- custom (personalizado)
```

#### **Groq (5 modelos)**
```javascript
- groq/llama-3.3-70b-versatile
- groq/llama-3.1-70b-versatile
- groq/llama-3.1-8b-instant
- groq/mixtral-8x7b-32768
- groq/gemma2-9b-it
```

#### **OpenAI (5 modelos)**
```javascript
- openai/gpt-4o
- openai/gpt-4o-mini
- openai/gpt-4-turbo
- openai/gpt-4
- openai/gpt-3.5-turbo
```

### **Parámetros de Análisis**

| Parámetro | Valor Predeterminado | Rango | Descripción |
|-----------|---------------------|-------|-------------|
| `batchSize` | 20 | 1-100 | Registros por lote |
| `batchDelay` | 2000 | 0-10000 | Pausa entre lotes (ms) |
| `pageSize` | 50 | - | Registros por página |

---

## 🔧 FUNCIONES JAVASCRIPT {#funciones}

### **Configuración**

```javascript
saveConfig()           // Guardar en localStorage
loadConfig()           // Cargar desde localStorage
testConnection()       // Probar conexión con IA
```

### **Prompts**

```javascript
savePrompt()           // Guardar prompts personalizados
loadPrompt()           // Cargar prompts guardados
resetPrompt()          // Restaurar predeterminados
```

### **Carga de Datos**

```javascript
loadAllData()          // Cargar 11,864 registros
renderPage()           // Renderizar página actual
renderPagination()     // Renderizar controles de paginación
goToPage(page)         // Navegar a página específica
```

### **Análisis IA**

```javascript
analyzeRow(index)              // Analizar un registro
startBatchAnalysis()           // Analizar todos
analyzeUnanalyzed()            // Analizar solo no analizados
runBatchAnalysis(onlyUnanalyzed)  // Lógica principal
pauseAnalysis()                // Pausar/reanudar
stopAnalysis()                 // Detener
```

### **Copiar Datos**

```javascript
copyIAToUser(index)    // Copiar IA → Usuario (una fila)
copyAllIAToUser()      // Copiar IA → Usuario (todas)
```

### **Exportación**

```javascript
exportCSV()            // Exportar a CSV
saveJSON()             // Guardar en JSON
loadJSON()             // Cargar desde JSON
handleJSONFile(event)  // Procesar archivo JSON
```

### **Utilidades**

```javascript
toggleSection(header)  // Expandir/colapsar sección
showStatus(type, msg)  // Mostrar mensaje de estado
toggleRevisado(index)  // Marcar como revisado
```

---

## 📊 ESTRUCTURA DE DATOS {#datos}

### **Objeto Registro (allData[])**

```javascript
{
  // Datos originales
  codigo: "ABC123",
  nombre_original: "TUBO PVC 110MM",
  nombre_normalizado: "TUBO PVC 110MM",
  
  // Resultados IA (8 campos)
  ia_material: "PVC",
  ia_categoria: "FONTANERIA",
  ia_familia: "TUBOS",
  ia_marca: "",
  ia_modelo: "",
  ia_atributos: "diametro: 110mm",
  ia_urls: "https://...",
  ia_imagen_url: "https://...",
  
  // Valores usuario (8 campos)
  user_material: "PVC",
  user_categoria: "FONTANERIA",
  user_familia: "TUBOS",
  user_marca: "",
  user_modelo: "",
  user_atributos: "diametro: 110mm",
  user_urls: "https://...",
  user_imagen_url: "https://...",
  
  // Estado
  analizado: true,
  revisado: false
}
```

### **Tabla HTML (21 columnas)**

| # | Columna | Tipo | Color |
|---|---------|------|-------|
| 1 | # | Número | - |
| 2 | Código | Texto | - |
| 3 | Nombre Original | Texto | - |
| 4-11 | IA: Material, Categoría, Familia, Marca, Modelo, Atributos, URLs, URL Imagen | Editable | #cce5ff |
| 12-19 | Material, Categoría, Familia, Marca, Modelo, Atributos, URLs, URL Imagen | Editable | #c3e6cb |
| 20 | ✓ Revisado | Checkbox | - |
| 21 | Acción | Botones | - |

---

## 🐛 TROUBLESHOOTING {#troubleshooting}

### **Error: "loadAllData is not defined"**
```
Causa: JavaScript no cargado o error de sintaxis
Solución: Verificar que enrichment-complete-v3.js esté sin errores
```

### **Error: "500 Internal Server Error en /test"**
```
Causa: Endpoint /api/enrichment/test no existe
Solución: Añadir endpoint en start_enrichment_api.py
```

### **Error: "No carga todos los registros"**
```
Causa: API Firebird no ejecutándose
Solución: python material_manager/firebird_api_v3.py
```

### **Error: "Análisis no funciona"**
```
Causa: API Enriquecimiento no ejecutándose
Solución: python material_manager/start_enrichment_api.py
```

### **Error: "API keys no válidas"**
```
Causa: API keys incorrectas o no configuradas
Solución: Verificar api_keys.json y configuración en UI
```

---

## 🚀 INICIO RÁPIDO

### **1. Iniciar Servidores**
```bash
# Terminal 1
python material_manager/firebird_api_v3.py

# Terminal 2
python material_manager/start_enrichment_api.py

# Terminal 3
python -m http.server 8000
```

### **2. Acceder**
```
http://localhost:8000/material_manager/enrichment-complete-v3.html
```

### **3. Configurar**
1. Expandir "⚙️ Configuración de Proveedores IA"
2. Seleccionar modelos
3. Introducir API Keys
4. Click "💾 Guardar Configuración"

### **4. Usar**
1. Click "📥 Cargar TODOS los Artículos"
2. Seleccionar proveedor
3. Click "🚀 Analizar Todos"
4. Click "📋 Copiar Todos IA → Usuario"
5. Click "💾 Exportar CSV"

---

## 📈 MÉTRICAS

| Métrica | Valor |
|---------|-------|
| Total Registros | 11,864 |
| Registros por Página | 50 |
| Total Páginas | 238 |
| Columnas por Registro | 21 |
| Modelos IA Disponibles | 17 |
| Proveedores IA | 3 |
| Líneas de Código JS | 683 |
| Líneas de Código CSS | 245 |
| Líneas de Código HTML | 228 |
| **Total Líneas** | **1,156** |

---

## 🔐 SEGURIDAD

### **API Keys**
- Almacenadas en `localStorage` (navegador)
- Tipo `password` en inputs
- No se envían al servidor web
- Solo se usan en llamadas a APIs IA

### **Datos**
- No se modifican en base de datos
- Solo lectura desde Firebird
- Exportación local (CSV/JSON)
- Sin persistencia en servidor

---

## 🎯 ESTADOS DEL SISTEMA

| Estado | Icono | Descripción |
|--------|-------|-------------|
| Inicial | 👋 | Esperando configuración |
| Cargando | 📥 | Cargando registros |
| Listo | ✅ | Registros cargados |
| Analizando | 🔄 | Análisis en progreso |
| Pausado | ⏸️ | Análisis pausado |
| Detenido | ⏹️ | Análisis detenido |
| Pausa Lote | ⏳ | Pausa entre lotes |
| Completado | ✅ | Análisis finalizado |
| Error | ❌ | Error en operación |

---

## 📝 NOTAS TÉCNICAS

### **Paginación**
- Cliente: 50 registros/página
- Servidor: 1000 registros/lote
- Total: 238 páginas cliente, 12 lotes servidor

### **Análisis por Lotes**
- Lote predeterminado: 20 registros
- Pausa predeterminada: 2000ms
- Evita rate limiting de APIs

### **Colores**
- `#cce5ff`: Azul claro (IA)
- `#c3e6cb`: Verde claro (Usuario)
- `#667eea`: Morado (Primario)
- `#764ba2`: Morado oscuro (Secundario)

### **Persistencia**
- Configuración: localStorage
- Prompts: localStorage
- Datos: Memoria (allData[])
- Exportación: Descarga local

---

## 🗄️ BASE DE DATOS FIREBIRD {#base-datos}

### **Información General**

| Propiedad | Valor |
|-----------|-------|
| Motor | Firebird 2.5+ |
| Charset | UTF8 / latin1 (permisivo) |
| Puerto | 3050 |
| Driver Python | `firebirdsql` (puro Python, sin DLLs) |

### **Tabla Principal: ARTICULO**

#### **Estructura**

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `CODIGO` | VARCHAR(20) | **PRIMARY KEY** - Código único del artículo |
| `NOMBRE` | VARCHAR(255) | Nombre/descripción del artículo |
| `CODFAMILIA` | VARCHAR(20) | Código de familia (clasificación) |
| `CODMARCA` | VARCHAR(20) | Código de marca |
| `PRECIOVENTA` | DECIMAL(10,2) | Precio de venta |
| `PRECIOCOSTE` | DECIMAL(10,2) | Precio de coste |
| `UNIDAD` | VARCHAR(10) | Unidad de medida (UD, M, KG, etc.) |

**Total de registros:** ~11,864 artículos

#### **Queries Comunes**

```sql
-- Contar total de artículos
SELECT COUNT(*) FROM ARTICULO;

-- Artículos con nombre
SELECT COUNT(*) FROM ARTICULO WHERE NOMBRE IS NOT NULL;

-- Artículos por familia
SELECT CODFAMILIA, COUNT(*) as TOTAL
FROM ARTICULO
GROUP BY CODFAMILIA
ORDER BY TOTAL DESC;

-- Buscar por nombre
SELECT CODIGO, NOMBRE, PRECIOVENTA
FROM ARTICULO
WHERE UPPER(NOMBRE) CONTAINING 'TUBO'
ORDER BY NOMBRE;
```

### **Conexión desde Python**

```python
import firebirdsql

# Parámetros de conexión
conn = firebirdsql.connect(
    host='HOST1',
    port=3050,
    database='C:\\path\\to\\2021.fdb',
    user='SYSDBA',
    password='masterkey',
    charset='latin1'  # Permisivo para bytes especiales
)

# Ejecutar query
cursor = conn.cursor()
cursor.execute("SELECT CODIGO, NOMBRE FROM ARTICULO WHERE NOMBRE IS NOT NULL")
rows = cursor.fetchall()

# Cerrar
cursor.close()
conn.close()
```

### **API Endpoints Firebird**

#### **POST /api/connect**
Verificar conexión a la base de datos
```json
Request:
{
  "host": "HOST1",
  "port": "3050",
  "database": "C:\\...\\2021.fdb",
  "username": "SYSDBA",
  "password": "masterkey"
}

Response:
{
  "success": true,
  "message": "Conexión verificada exitosamente"
}
```

#### **POST /api/normalize/count**
Contar total de artículos
```json
Request:
{
  ...connectionParams,
  "table_name": "ARTICULO",
  "field_name": "NOMBRE"
}

Response:
{
  "success": true,
  "total": 11864
}
```

#### **POST /api/normalize/with-metadata**
Obtener artículos con metadatos
```json
Request:
{
  ...connectionParams,
  "table_name": "ARTICULO",
  "field_name": "NOMBRE",
  "pk_field": "CODIGO",
  "limit": 1000,
  "offset": 0
}

Response:
{
  "success": true,
  "results": [
    {
      "codigo": "ABC123",
      "nombre_original": "TUBO PVC 110MM",
      "nombre_normalizado": "TUBO PVC 110MM",
      "codfamilia": "TUB",
      "codmarca": "PVC",
      "material_principal": "TUBO",
      "categoria": "FONTANERIA",
      "familia": "TUBOS",
      "confianza": 1
    }
  ]
}
```

### **Otras Tablas del Sistema**

| Tabla | Descripción |
|-------|-------------|
| `RDB$RELATIONS` | Metadatos de tablas |
| `RDB$RELATION_FIELDS` | Metadatos de columnas |
| `RDB$RELATION_CONSTRAINTS` | Constraints (PK, FK, etc.) |
| `RDB$INDEX_SEGMENTS` | Índices |
| `RDB$TRIGGERS` | Triggers |
| `RDB$PROCEDURES` | Procedimientos almacenados |

### **Queries de Sistema**

```sql
-- Listar todas las tablas
SELECT TRIM(RDB$RELATION_NAME)
FROM RDB$RELATIONS
WHERE RDB$SYSTEM_FLAG = 0
AND RDB$VIEW_BLR IS NULL
ORDER BY RDB$RELATION_NAME;

-- Columnas de una tabla
SELECT 
    TRIM(r.RDB$FIELD_NAME) as FIELD_NAME,
    f.RDB$FIELD_TYPE as FIELD_TYPE,
    f.RDB$FIELD_LENGTH as FIELD_LENGTH
FROM RDB$RELATION_FIELDS r
JOIN RDB$FIELDS f ON r.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
WHERE TRIM(r.RDB$RELATION_NAME) = 'ARTICULO'
ORDER BY r.RDB$FIELD_POSITION;

-- Primary Keys
SELECT TRIM(s.RDB$FIELD_NAME)
FROM RDB$RELATION_CONSTRAINTS rc
JOIN RDB$INDEX_SEGMENTS s ON rc.RDB$INDEX_NAME = s.RDB$INDEX_NAME
WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
AND TRIM(rc.RDB$RELATION_NAME) = 'ARTICULO';
```

### **Manejo de Encoding**

El sistema usa dos estrategias de encoding:

1. **UTF-8** (predeterminado): Para texto normal
2. **latin1** (permisivo): Para bytes especiales

```python
# Función de decodificación segura
def safe_decode(value):
    if isinstance(value, bytes):
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return value.decode('latin1')
            except:
                return str(value)
    return str(value) if value else ''
```

### **Estrategia de Conexión**

**v3 - Stateless (Actual):**
- ✅ Cada petición abre y cierra su propia conexión
- ✅ No mantiene estado entre peticiones
- ✅ Evita problemas de concurrencia
- ✅ Thread-safe

```python
# Patrón de uso
conn = None
try:
    conn = create_connection(**params)
    cursor = conn.cursor()
    # ... operaciones ...
    cursor.close()
finally:
    if conn:
        conn.close()
```

---

**Versión:** 3.1.0  
