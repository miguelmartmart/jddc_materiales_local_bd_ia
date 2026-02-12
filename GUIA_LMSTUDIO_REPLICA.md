# Guía de Replicación: Servicio de Análisis de Imágenes (Estilo `interjddcia`)

Esta guía explica **exactamente** cómo funciona el análisis de imágenes en la aplicación actual (`interjddcia`) para que puedas copiar la lógica a tu otra aplicación.

## 1. Arquitectura Real

A diferencia de lo que pensabas (que usa el puerto 8188 de ComfyUI), la aplicación actual utiliza **LM Studio** actuando como un servidor compatible con OpenAI.

*   **Servidor de IA**: LM Studio (Local).
*   **Puerto**: `1234` (Estándar de LM Studio).
*   **Protocolo**: API OpenAI (`/v1/chat/completions`).
*   **Modelo**: `qwen/qwen3-vl-8b` (o cualquier modelo "Vision" cargado).

## 2. Requisitos Previos (En el Servidor 192.168.0.42)

Para "hacer lo mismo" en tu otra app, en el servidor remoto (`192.168.0.42`) debes:

1.  Tener instalado **LM Studio**.
2.  Descargar y cargar un modelo de visión (Ej: `Qwen/Qwen2.5-VL-7B-Instruct-GGUF`).
3.  **Iniciar el Servidor Local** en LM Studio:
    *   Activar "Local Inference Server".
    *   Asegurarse de que escuche en `0.0.0.0` (red local) y no solo `localhost`, para que tu otra app pueda contactarlo.
    *   Puerto: `1234` (O el que configures, por defecto es este).

## 3. Implementación de Código (Python)

Aquí tienes el código "copiar y pegar" basado en cómo lo hace `backend/modules/images/service.py` pero limpio para tu nueva app.

**Librerías necesarias:**
```bash
pip install openai
```

**Código del Cliente:**

```python
import base64
from openai import OpenAI

# 1. Configuración del Cliente
# Apunta a la IP de tu servidor donde corre LM Studio (ej: 192.168.0.42)
client = OpenAI(
    base_url="http://192.168.0.42:1234/v1", 
    api_key="lm-studio"  # No se usa realmente, pero es obligatorio poner algo
)

def codificar_imagen(ruta_imagen):
    """Convierte la imagen a Base64"""
    with open(ruta_imagen, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def analizar_imagen(ruta_imagen, prompt="Describe esta imagen detalladamente."):
    print(f"Analizando: {ruta_imagen}...")
    
    # 2. Preparar la imagen
    base64_image = codificar_imagen(ruta_imagen)
    
    # 3. Enviar petición (Formato Estándar GPT-4 Vision)
    try:
        response = client.chat.completions.create(
            model="qwen-vl-chat", # El nombre del modelo cargado en LM Studio
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.7,
            max_tokens=-1  # Dejar que el modelo decida el largo
        )
        
        # 4. Obtener respuesta
        resultado = response.choices[0].message.content
        return resultado

    except Exception as e:
        return f"Error al analizar: {e}"

# Ejemplo de uso
if __name__ == "__main__":
    descripcion = analizar_imagen("foto_prueba.jpg")
    print("\n--- RESULTADO ---\n")
    print(descripcion)
```

## 4. Diferencias Clave con ComfyUI (8188)

*   **ComfyUI (8188)** es un sistema de *nodos* para *generar*. Usarlo para analizar es posible pero mucho más complejo de integrar (requiere WebSockets).
*   **LM Studio (1234)** es un servidor de API REST estándar. Es mucho más fácil de integrar en código (como ves arriba, son 15 líneas de código).

**Recomendación:** Si quieres replicar la funcionalidad de análisis de esta app, usa el método de LM Studio descrito arriba. Es más estable y estándar.
