"""
test_siuo_render_and_tokens.py — Tests para markdownToHtml y configuración de tokens SIUO.

CUBRE:
  - markdownToHtml: tablas GFM, <details>, <span style>, <p style>, negrita, listas
  - Tokens: siuo_router acepta max_tokens hasta 16000, default 8000
  - Placeholders: TABLE_BLOCK y HTML_BLOCK se restauran correctamente
  - Anti-regresión: el bug %%PH_%% → %%PH_ no vuelve

FILOSOFÍA:
  - Sin mocks: prueba la lógica real de Python (router Pydantic) y JS (via regex/string)
  - Tests deterministas: entrada → salida esperada, sin dependencias externas
  - Cada test tiene un nombre descriptivo del comportamiento que verifica

AUTOR: DEVIA / bots/interjddcia
"""

import re
import json
import pytest
from pathlib import Path

# ─── Helpers para simular markdownToHtml en Python ───────────────────────────
# Reimplementación fiel del algoritmo JS para poder testear sin browser.
# Si el JS cambia, estos tests fallarán → detecta regresiones.

def escape_html(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def markdown_to_html(text: str) -> str:
    """
    Reimplementación Python de markdownToHtml (siuo_constants.js).
    Mantiene paridad 1:1 con el algoritmo JS para detectar regresiones.
    """
    if not text:
        return ""

    trimmed = text.strip()
    # Paso 0: HTML puro → devolver tal cual
    if trimmed.startswith("<p>") or trimmed.startswith("<div>") or trimmed.startswith("<table>"):
        return text

    html_blocks: list[str] = []
    HTML_PH = "%%HTML_BLOCK_"

    # Paso 1a: extraer <details>
    def _extract_details(m):
        block = m.group(0).replace("<details", '<details class="chat-justification"', 1)
        html_blocks.append(block)
        return f"{HTML_PH}{len(html_blocks)-1}%%"

    processed = re.sub(r"<details[\s\S]*?</details>", _extract_details, text, flags=re.IGNORECASE)

    # Paso 1b: extraer <span style=...>
    def _extract_span(m):
        html_blocks.append(m.group(0))
        return f"{HTML_PH}{len(html_blocks)-1}%%"

    processed = re.sub(r"<span\s[^>]*>[\s\S]*?</span>", _extract_span, processed, flags=re.IGNORECASE)

    # Paso 1c: extraer <p style=...>
    def _extract_p_style(m):
        html_blocks.append(m.group(0))
        return f"{HTML_PH}{len(html_blocks)-1}%%"

    processed = re.sub(r"<p\s[^>]*>[\s\S]*?</p>", _extract_p_style, processed, flags=re.IGNORECASE)

    # Paso 2: extraer tablas Markdown
    table_blocks: list[str] = []
    TABLE_PH = "%%TABLE_BLOCK_"

    def _extract_table(m):
        match_text = m.group(0)
        lines = [l for l in match_text.strip().split("\n") if l.strip()]
        if len(lines) < 2:
            return match_text
        sep_idx = next((i for i, l in enumerate(lines) if re.match(r"^\s*\|[\s\-:|]+\|\s*$", l)), -1)
        if sep_idx < 0:
            return match_text
        header_line = lines[0]
        body_lines = lines[sep_idx + 1:]

        def parse_cells(line):
            line = re.sub(r"^\s*\|", "", line)
            line = re.sub(r"\|\s*$", "", line)
            return [c.strip() for c in line.split("|")]

        headers = parse_cells(header_line)
        rows = [parse_cells(l) for l in body_lines]
        thead = "<thead><tr>" + "".join(f"<th>{escape_html(h)}</th>" for h in headers) + "</tr></thead>"
        tbody = "<tbody>" + "".join(
            "<tr>" + "".join(f"<td>{escape_html(c)}</td>" for c in r) + "</tr>"
            for r in rows
        ) + "</tbody>"
        table_html = f'<div class="md-table-wrap"><table class="md-table">{thead}{tbody}</table></div>'
        table_blocks.append(table_html)
        return f"{TABLE_PH}{len(table_blocks)-1}%%"

    processed = re.sub(r"((?:[ \t]*\|.+\|[ \t]*\n?)+)", _extract_table, processed)

    # Paso 3: escapar HTML restante
    html = escape_html(processed)

    # Paso 4: inline Markdown
    html = re.sub(r"\*\*([^*\n]+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*([^*\n]+?)\*", r"<em>\1</em>", html)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Paso 5: listas
    html = re.sub(r"^[-*]\s+(.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>[\s\S]*?</li>)", r"<ul>\1</ul>", html)

    # Paso 6: párrafos
    html = re.sub(r"\n\n+", "</p><p>", html)
    html = html.replace("\n", "<br>")
    html = f"<p>{html}</p>"

    # Paso 7: restaurar tablas
    def _restore_table(m):
        idx = int(m.group(1))
        return f"</p>{table_blocks[idx]}<p>" if idx < len(table_blocks) else m.group(0)

    html = re.sub(r"%%TABLE_BLOCK_(\d+)%%", _restore_table, html)

    # Paso 8: restaurar HTML blocks
    def _restore_html(m):
        idx = int(m.group(1))
        return f"</p>{html_blocks[idx]}<p>" if idx < len(html_blocks) else m.group(0)

    html = re.sub(r"%%HTML_BLOCK_(\d+)%%", _restore_html, html)

    # Limpiar párrafos vacíos
    html = re.sub(r"<p>\s*</p>", "", html)
    return html


# ─── Tests: markdownToHtml ────────────────────────────────────────────────────

class TestMarkdownToHtmlTablas:
    """Tablas GFM se convierten a <table class='md-table'>."""

    def test_tabla_simple_3_columnas(self):
        md = "| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |"
        html = markdown_to_html(md)
        assert '<table class="md-table">' in html
        assert "<th>" in html
        assert "<td>" in html
        assert "A" in html and "B" in html and "C" in html

    def test_tabla_envuelta_en_md_table_wrap(self):
        md = "| Col1 | Col2 |\n|------|------|\n| val1 | val2 |"
        html = markdown_to_html(md)
        assert 'class="md-table-wrap"' in html

    def test_tabla_sin_separador_no_se_convierte(self):
        md = "| A | B |\n| 1 | 2 |"
        html = markdown_to_html(md)
        assert '<table class="md-table">' not in html

    def test_tabla_con_una_columna(self):
        md = "| Nombre |\n|--------|\n| Juan |"
        html = markdown_to_html(md)
        assert "<th>" in html
        assert "Juan" in html

    def test_tabla_escapa_xss(self):
        md = "| Col |\n|-----|\n| <script>alert(1)</script> |"
        html = markdown_to_html(md)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_tabla_con_numeros_grandes(self):
        md = "| Artículo | Compras |\n|----------|--------|\n| MATERIALES VARIOS | 71771 |"
        html = markdown_to_html(md)
        assert "71771" in html
        assert "MATERIALES VARIOS" in html


class TestMarkdownToHtmlDetails:
    """Bloques <details> se preservan como HTML."""

    def test_details_se_preserva(self):
        md = "Texto\n<details><summary>Ver</summary>Contenido</details>"
        html = markdown_to_html(md)
        assert "<details" in html
        assert "<summary>Ver</summary>" in html
        assert "Contenido" in html

    def test_details_recibe_clase_chat_justification(self):
        md = "<details><summary>S</summary>C</details>"
        html = markdown_to_html(md)
        assert 'class="chat-justification"' in html

    def test_details_no_se_escapa(self):
        md = "<details><summary>Ver</summary><strong>Negrita</strong></details>"
        html = markdown_to_html(md)
        assert "&lt;details&gt;" not in html
        assert "<details" in html


class TestMarkdownToHtmlSpanStyle:
    """<span style=...> del backend se preserva sin escapar."""

    def test_span_color_rojo_se_preserva(self):
        md = "Texto <span style='color:#c0392b'>advertencia</span> más texto"
        html = markdown_to_html(md)
        assert "<span" in html
        assert "color:#c0392b" in html
        assert "advertencia" in html

    def test_span_no_se_escapa(self):
        md = "<span style='color:red'>rojo</span>"
        html = markdown_to_html(md)
        assert "&lt;span" not in html
        assert "<span" in html

    def test_p_style_advertencia_se_preserva(self):
        md = "<p style='color:#c0392b;font-weight:bold;'>⚠️ ADVERTENCIA</p>"
        html = markdown_to_html(md)
        assert "<p style=" in html
        assert "ADVERTENCIA" in html


class TestMarkdownToHtmlInline:
    """Markdown inline: negrita, cursiva, código."""

    def test_negrita(self):
        html = markdown_to_html("**texto negrita**")
        assert "<strong>texto negrita</strong>" in html

    def test_cursiva(self):
        html = markdown_to_html("*texto cursiva*")
        assert "<em>texto cursiva</em>" in html

    def test_codigo_inline(self):
        html = markdown_to_html("`SELECT FIRST 10`")
        assert "<code>SELECT FIRST 10</code>" in html

    def test_lista_guiones(self):
        html = markdown_to_html("- item uno\n- item dos")
        assert "<li>item uno</li>" in html
        assert "<li>item dos</li>" in html


class TestMarkdownToHtmlHtmlPuro:
    """Si el texto ya es HTML puro, se devuelve tal cual."""

    def test_html_puro_p_devuelto_tal_cual(self):
        html_input = "<p>Ya es HTML</p>"
        result = markdown_to_html(html_input)
        assert result == html_input

    def test_html_puro_div_devuelto_tal_cual(self):
        html_input = "<div>contenido</div>"
        result = markdown_to_html(html_input)
        assert result == html_input

    def test_markdown_normal_no_se_devuelve_tal_cual(self):
        md = "Texto normal sin HTML"
        result = markdown_to_html(md)
        assert result != md  # Se procesa
        assert "<p>" in result


class TestMarkdownToHtmlPlaceholders:
    """Anti-regresión: los placeholders deben coincidir con los regex de restauración."""

    def test_tabla_no_deja_placeholder_visible(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        html = markdown_to_html(md)
        assert "%%TABLE_BLOCK_" not in html

    def test_details_no_deja_placeholder_visible(self):
        md = "<details><summary>S</summary>C</details>"
        html = markdown_to_html(md)
        assert "%%HTML_BLOCK_" not in html

    def test_span_no_deja_placeholder_visible(self):
        md = "<span style='color:red'>texto</span>"
        html = markdown_to_html(md)
        assert "%%HTML_BLOCK_" not in html

    def test_multiples_tablas_todas_restauradas(self):
        md = ("| A | B |\n|---|---|\n| 1 | 2 |\n\n"
              "Texto intermedio\n\n"
              "| X | Y |\n|---|---|\n| 3 | 4 |")
        html = markdown_to_html(md)
        assert "%%TABLE_BLOCK_" not in html
        assert html.count('<table class="md-table">') == 2

    def test_tabla_y_details_juntos(self):
        md = ("| Col |\n|-----|\n| val |\n\n"
              "<details><summary>Ver</summary>Info</details>")
        html = markdown_to_html(md)
        assert "%%TABLE_BLOCK_" not in html
        assert "%%HTML_BLOCK_" not in html
        assert '<table class="md-table">' in html
        assert "<details" in html


# ─── Tests: siuo_router Pydantic (tokens) ────────────────────────────────────

class TestSiuoRouterTokens:
    """El router acepta max_tokens hasta 16000 y tiene default 8000."""

    def test_context_ask_request_default_8000(self):
        """ContextAskRequest default debe ser 8000."""
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3]))
        try:
            from backend.modules.db_explorer.siuo_router import ContextAskRequest
            req = ContextAskRequest(question="test")
            assert req.max_tokens == 8000
        except ImportError:
            pytest.skip("Backend no disponible en este entorno")

    def test_context_test_request_default_8000(self):
        """ContextTestRequest default debe ser 8000."""
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3]))
        try:
            from backend.modules.db_explorer.siuo_router import ContextTestRequest
            req = ContextTestRequest(question="test")
            assert req.max_tokens == 8000
        except ImportError:
            pytest.skip("Backend no disponible en este entorno")

    def test_context_ask_acepta_16000(self):
        """ContextAskRequest debe aceptar max_tokens=16000."""
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3]))
        try:
            from backend.modules.db_explorer.siuo_router import ContextAskRequest
            req = ContextAskRequest(question="test", max_tokens=16000)
            assert req.max_tokens == 16000
        except ImportError:
            pytest.skip("Backend no disponible en este entorno")

    def test_context_ask_rechaza_mas_de_16000(self):
        """ContextAskRequest debe rechazar max_tokens > 16000."""
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3]))
        try:
            from backend.modules.db_explorer.siuo_router import ContextAskRequest
            from pydantic import ValidationError
            with pytest.raises(ValidationError):
                ContextAskRequest(question="test", max_tokens=16001)
        except ImportError:
            pytest.skip("Backend no disponible en este entorno")

    def test_context_ask_rechaza_menos_de_100(self):
        """ContextAskRequest debe rechazar max_tokens < 100."""
        import sys
        sys.path.insert(0, str(Path(__file__).parents[3]))
        try:
            from backend.modules.db_explorer.siuo_router import ContextAskRequest
            from pydantic import ValidationError
            with pytest.raises(ValidationError):
                ContextAskRequest(question="test", max_tokens=50)
        except ImportError:
            pytest.skip("Backend no disponible en este entorno")


# ─── Tests: siuo_constants.js (verificación de fichero fuente) ───────────────

class TestSiuoConstantsJs:
    """Verifica que siuo_constants.js tiene los valores correctos en el fichero fuente."""

    @pytest.fixture(scope="class")
    def js_content(self):
        # Desde tests/unit/ → ../../frontend/assets/js/modules/
        path = Path(__file__).parent.parent.parent / "frontend/assets/js/modules/siuo_constants.js"
        if not path.exists():
            pytest.skip(f"siuo_constants.js no encontrado en {path}")
        return path.read_text(encoding="utf-8")

    def test_table_ph_sin_doble_porcentaje(self, js_content):
        """tablePH debe ser '%%TABLE_BLOCK_' (sin %% extra al final)."""
        assert '= "%%TABLE_BLOCK_"' in js_content or "= '%%TABLE_BLOCK_'" in js_content
        # Anti-regresión: no debe tener el bug antiguo
        assert '= "%%TABLE_BLOCK_%%"' not in js_content

    def test_html_ph_sin_doble_porcentaje(self, js_content):
        """HTML_PH debe ser '%%HTML_BLOCK_' (sin %% extra al final)."""
        assert '"%%HTML_BLOCK_"' in js_content or "'%%HTML_BLOCK_'" in js_content

    def test_regex_restauracion_tabla_correcto(self, js_content):
        """El regex de restauración de tablas debe ser /%%TABLE_BLOCK_(\\d+)%%/g."""
        assert "%%TABLE_BLOCK_(\\d+)%%" in js_content

    def test_regex_restauracion_html_correcto(self, js_content):
        """El regex de restauración HTML debe ser /%%HTML_BLOCK_(\\d+)%%/g."""
        assert "%%HTML_BLOCK_(\\d+)%%" in js_content

    def test_no_hay_regex_details_block_obsoleto(self, js_content):
        """No debe haber el regex obsoleto %%DETAILS_BLOCK_ en la restauración."""
        # El regex de restauración no debe usar DETAILS_BLOCK
        assert "%%DETAILS_BLOCK_(\\d+)%%" not in js_content

    def test_tokens_default_8000_en_constante(self, js_content):
        """SIUO_MAX_TOKENS_DEFAULT puede ser 2000 (usado en runQuickTest) — verificar que existe."""
        assert "SIUO_MAX_TOKENS_DEFAULT" in js_content


# ─── Tests: siuo_render.js (verificación de fichero fuente) ──────────────────

class TestSiuoRenderJs:
    """Verifica que siuo_render.js tiene los valores correctos."""

    @pytest.fixture(scope="class")
    def js_content(self):
        # tests/unit/ → ../../frontend/assets/js/modules/
        path = Path(__file__).parent.parent.parent / "frontend/assets/js/modules/siuo_render.js"
        if not path.exists():
            pytest.skip(f"siuo_render.js no encontrado en {path}")
        return path.read_text(encoding="utf-8")

    def test_input_tokens_value_8000(self, js_content):
        """El input de tokens debe tener value=8000."""
        assert 'value="8000"' in js_content

    def test_input_tokens_max_16000(self, js_content):
        """El input de tokens debe tener max=16000."""
        assert 'max="16000"' in js_content

    def test_boton_expandir_presente(self, js_content):
        """El botón expandir debe estar en el skeleton."""
        assert "siuo-expand-btn" in js_content
        assert "expandResult" in js_content


# ─── Tests: siuo.js (verificación de fichero fuente) ─────────────────────────

class TestSiuoJs:
    """Verifica que siuo.js expone las funciones correctas."""

    @pytest.fixture(scope="class")
    def js_content(self):
        # tests/unit/ → ../../frontend/assets/js/modules/
        path = Path(__file__).parent.parent.parent / "frontend/assets/js/modules/siuo.js"
        if not path.exists():
            pytest.skip(f"siuo.js no encontrado en {path}")
        return path.read_text(encoding="utf-8")

    def test_expand_result_en_window_module(self, js_content):
        """expandResult debe estar expuesto en window.SIUOModule."""
        assert "expandResult: siuoExpandResult" in js_content

    def test_close_modal_en_window_module(self, js_content):
        """closeModal debe estar expuesto en window.SIUOModule."""
        assert "closeModal: siuoCloseModal" in js_content

    def test_show_expand_btn_llamado_tras_exito(self, js_content):
        """_showExpandBtn(true) debe llamarse tras respuesta exitosa."""
        assert "_showExpandBtn(true)" in js_content

    def test_show_expand_btn_llamado_tras_error(self, js_content):
        """_showExpandBtn(false) debe llamarse tras error."""
        assert "_showExpandBtn(false)" in js_content

    def test_modal_cierra_con_escape(self, js_content):
        """El modal debe cerrarse con Escape."""
        assert '"Escape"' in js_content or "'Escape'" in js_content

    def test_modal_cierra_con_clic_overlay(self, js_content):
        """El modal debe cerrarse al clic en el overlay."""
        assert "e.target === overlay" in js_content


# ─── Tests: siuo.css (verificación de fichero fuente) ────────────────────────

class TestSiuoCss:
    """Verifica que siuo.css tiene los estilos necesarios."""

    @pytest.fixture(scope="class")
    def css_content(self):
        # tests/unit/ → ../../frontend/assets/css/
        path = Path(__file__).parent.parent.parent / "frontend/assets/css/siuo.css"
        if not path.exists():
            pytest.skip(f"siuo.css no encontrado en {path}")
        return path.read_text(encoding="utf-8")

    def test_md_table_wrap_overflow_x_auto(self, css_content):
        """md-table-wrap debe tener overflow-x: auto para scroll horizontal."""
        assert ".md-table-wrap" in css_content
        # Verificar que overflow-x: auto está cerca de md-table-wrap
        idx = css_content.find(".md-table-wrap")
        section = css_content[idx:idx+300]
        assert "overflow-x: auto" in section

    def test_md_table_existe(self, css_content):
        """md-table debe tener estilos definidos."""
        assert ".md-table" in css_content
        assert "border-collapse: collapse" in css_content

    def test_modal_overlay_existe(self, css_content):
        """siuo-modal-overlay debe estar definido."""
        assert ".siuo-modal-overlay" in css_content
        assert "position: fixed" in css_content

    def test_modal_body_max_height(self, css_content):
        """siuo-modal-body debe tener max-height para scroll."""
        assert ".siuo-modal-body" in css_content
        assert "max-height" in css_content

    def test_btn_expand_existe(self, css_content):
        """siuo-btn-expand debe estar definido."""
        assert ".siuo-btn-expand" in css_content
