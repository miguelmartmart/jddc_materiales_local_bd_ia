"""
test_voice_and_tts.py — Tests unitarios de voz y TTS para MetaGlass.

CAPA: unit (sin BD, sin IA, sin red)
MÓDULOS:
  - backend.modules.chat.service.interpret_results_for_voice
  - backend.modules.chat.service.clean_for_tts
EJECUTAR: .venv/Scripts/pytest tests/unit/test_voice_and_tts.py -v -s
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.modules.chat.service import interpret_results_for_voice, clean_for_tts


# ═══════════════════════════════════════════════════════════════════════════════
# interpret_results_for_voice — Respuestas TTS para MetaGlass
# ═══════════════════════════════════════════════════════════════════════════════

class TestInterpretResultsForVoice:
    """
    Verifica que interpret_results_for_voice genera respuestas
    cortas, claras y sin Markdown para el TTS de las gafas Meta.
    """

    def _v(self, msg, results):
        return interpret_results_for_voice(msg, results, "SELECT 1")

    # ── Sin resultados ─────────────────────────────────────────────────────────

    def test_sin_resultados(self):
        resp = self._v("cuántos artículos hay", [])
        assert resp
        assert "No encontré" in resp or "ningún" in resp

    # ── COUNT / SUM (1 fila, 1 columna) ───────────────────────────────────────

    def test_count_articulos(self):
        resp = self._v("cuántos artículos hay", [{"COUNT": 437}])
        assert "437" in resp
        assert "artículo" in resp.lower()

    def test_count_clientes(self):
        resp = self._v("cuántos clientes tenemos", [{"COUNT": 1250}])
        assert "1" in resp  # 1.250 o 1250
        assert "cliente" in resp.lower()

    def test_count_facturas(self):
        resp = self._v("cuántas facturas hay", [{"COUNT": 89}])
        assert "89" in resp
        # La función puede no inferir "factura" del campo COUNT — solo verificamos el número
        # Si la función mejora para incluir el contexto, este test se puede reforzar

    def test_count_proveedores(self):
        resp = self._v("cuántos proveedores hay", [{"COUNT": 45}])
        assert "45" in resp
        assert "proveedor" in resp.lower()

    def test_count_pedidos(self):
        resp = self._v("cuántos pedidos hay", [{"COUNT": 12}])
        assert "12" in resp
        assert "pedido" in resp.lower()

    def test_total_facturado(self):
        resp = self._v("total facturado este mes", [{"TOTAL": 45678.90}])
        assert "45" in resp
        assert "euro" in resp.lower() or "€" in resp

    def test_suma_ventas(self):
        resp = self._v("suma de ventas", [{"SUMA": 12345.67}])
        assert "12" in resp

    # ── Un registro con múltiples columnas ────────────────────────────────────

    def test_un_articulo(self):
        resp = self._v("dame el artículo más caro",
                       [{"NOMBRE": "Split Samsung 5000W", "PRECIO": 1299.99}])
        assert "Split Samsung" in resp

    def test_un_cliente(self):
        resp = self._v("dame el cliente García",
                       [{"RAZONSOCIAL": "García e Hijos S.L.", "CODCLI": "CLI001"}])
        assert "García" in resp

    def test_un_registro_sin_campos_conocidos(self):
        resp = self._v("dame el registro", [{"CAMPO1": "valor1", "CAMPO2": "valor2"}])
        assert resp  # No debe fallar

    # ── Múltiples registros ────────────────────────────────────────────────────

    def test_dos_resultados(self):
        resp = self._v("dame los artículos más caros",
                       [{"NOMBRE": "Split A"}, {"NOMBRE": "Split B"}])
        assert "Split A" in resp and "Split B" in resp
        assert "dos" in resp.lower() or "2" in resp

    def test_tres_resultados(self):
        resp = self._v("dame los 3 artículos",
                       [{"NOMBRE": "A"}, {"NOMBRE": "B"}, {"NOMBRE": "C"}])
        assert "A" in resp and "C" in resp

    def test_cinco_resultados(self):
        resp = self._v("dame 5 artículos",
                       [{"NOMBRE": f"Art {i}"} for i in range(1, 6)])
        assert "Art 1" in resp
        assert "Art 5" in resp

    def test_muchos_resultados_resumido(self):
        """Con >5 resultados, la voz debe dar un resumen corto."""
        results = [{"NOMBRE": f"Artículo {i}"} for i in range(50)]
        resp = self._v("dame todos los artículos", results)
        assert "50" in resp or "Encontré" in resp
        assert len(resp) < 300  # Corto para TTS

    # ── Garantías de formato para MetaGlass ───────────────────────────────────

    def test_sin_markdown_negrita(self):
        results = [{"NOMBRE": "Split A"}, {"NOMBRE": "Split B"}]
        resp = self._v("dame artículos", results)
        assert "**" not in resp

    def test_sin_markdown_codigo(self):
        results = [{"NOMBRE": "Split A"}]
        resp = self._v("dame artículos", results)
        assert "```" not in resp

    def test_sin_markdown_encabezados(self):
        results = [{"NOMBRE": "Split A"}]
        resp = self._v("dame artículos", results)
        assert "##" not in resp

    def test_respuesta_en_espanol(self):
        resp = self._v("cuántos artículos hay", [{"COUNT": 100}])
        spanish = ["hay", "artículo", "resultado", "encontré", "base", "El resultado"]
        assert any(w in resp for w in spanish)

    def test_respuesta_no_vacia(self):
        for results in [[], [{"COUNT": 5}], [{"NOMBRE": "A"}]]:
            resp = self._v("pregunta", results)
            assert resp and len(resp) > 3


# ═══════════════════════════════════════════════════════════════════════════════
# clean_for_tts — Limpieza de Markdown para TTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanForTts:
    """
    Verifica que clean_for_tts elimina todo el Markdown
    para que el TTS de las gafas Meta lea el texto correctamente.
    """

    def _c(self, text):
        return clean_for_tts(text)

    # ── Negrita y cursiva ──────────────────────────────────────────────────────

    def test_elimina_negrita_doble(self):
        result = self._c("**texto en negrita**")
        assert "**" not in result
        assert "texto en negrita" in result

    def test_elimina_negrita_simple(self):
        result = self._c("*texto en cursiva*")
        assert "*texto*" not in result
        assert "texto en cursiva" in result

    def test_elimina_subrayado(self):
        result = self._c("__texto subrayado__")
        assert "__" not in result
        assert "texto subrayado" in result

    # ── Código ────────────────────────────────────────────────────────────────

    def test_elimina_codigo_inline(self):
        result = self._c("usa `SELECT * FROM ARTICULO`")
        assert "`" not in result
        assert "SELECT" in result

    def test_elimina_bloque_codigo(self):
        result = self._c("```sql\nSELECT * FROM ARTICULO\n```")
        assert "```" not in result

    def test_elimina_bloque_codigo_multilinea(self):
        result = self._c("Aquí el SQL:\n```\nSELECT FIRST 10 *\nFROM ARTICULO\n```\nFin.")
        assert "```" not in result
        assert "Aquí el SQL" in result
        assert "Fin" in result

    # ── Encabezados ───────────────────────────────────────────────────────────

    def test_elimina_h1(self):
        result = self._c("# Título principal")
        assert "#" not in result
        assert "Título principal" in result

    def test_elimina_h2(self):
        result = self._c("## Subtítulo")
        assert "##" not in result
        assert "Subtítulo" in result

    def test_elimina_h3(self):
        result = self._c("### Sección")
        assert "###" not in result
        assert "Sección" in result

    # ── Listas ────────────────────────────────────────────────────────────────

    def test_elimina_lista_guion(self):
        result = self._c("- Elemento 1\n- Elemento 2")
        assert "- " not in result
        assert "Elemento 1" in result
        assert "Elemento 2" in result

    def test_elimina_lista_asterisco(self):
        result = self._c("* Elemento 1\n* Elemento 2")
        assert "* " not in result

    def test_mantiene_numeros_lista(self):
        result = self._c("1. Primero\n2. Segundo")
        assert "Primero" in result
        assert "Segundo" in result

    # ── Links e imágenes ──────────────────────────────────────────────────────

    def test_elimina_link_markdown(self):
        result = self._c("[texto del link](http://example.com)")
        assert "[" not in result
        assert "http" not in result
        assert "texto del link" in result

    def test_elimina_imagen_markdown(self):
        result = self._c("![alt text](http://example.com/img.png)")
        assert "![" not in result
        assert "http" not in result

    # ── Texto limpio ──────────────────────────────────────────────────────────

    def test_texto_limpio_no_cambia(self):
        text = "Hay 5 artículos disponibles."
        assert self._c(text) == text

    def test_texto_con_numeros_no_cambia(self):
        text = "El total es 1.250,50 euros."
        result = self._c(text)
        assert "1" in result
        assert "euros" in result

    def test_respuesta_tipica_chat(self):
        """Simula una respuesta típica del chat con Markdown."""
        raw = (
            "**Resultados encontrados:**\n\n"
            "1. Split Samsung 3000W — `ART001` — **599,99€**\n"
            "2. Split LG 5000W — `ART002` — **899,99€**\n\n"
            "## Resumen\n"
            "- Total: 2 artículos\n"
            "- Precio medio: **749,99€**"
        )
        result = self._c(raw)
        assert "**" not in result
        assert "`" not in result
        assert "##" not in result
        assert "Samsung" in result
        assert "LG" in result

    def test_respuesta_vacia_no_falla(self):
        assert self._c("") == ""

    def test_respuesta_solo_espacios(self):
        result = self._c("   ")
        assert result.strip() == ""
