import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from centro.conversations_ui import read_turns, ConversationsWindow
from centro.ui import Center


class ConversationsTests(unittest.TestCase):
    def test_private_erp_sample_visible_without_ai_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / '.portal_private/validacion-devia/erp-fixture'
            target.mkdir(parents=True)
            (target/'DATOS-ERP-PRIVADOS.json').write_text(json.dumps([
                {'case': 'sample', 'sql': 'SELECT FIRST 3 ID FROM DEMO', 'fields': ['ID'], 'rows': [[7]]}]))
            app = Center(root, autoload=False)
            app.withdraw()
            try:
                window = ConversationsWindow(app, root)
                content = window.text.get('1.0', 'end')
                self.assertIn('no pasó por la IA', content)
                self.assertIn('SELECT FIRST 3 ID', content)
                self.assertIn('7', content)
                window.destroy()
            finally:
                app.close()

    def test_capture_closed_fields_and_display_read(self):
        source = Path(__file__).resolve().parents[2] / 'DEVIA_VALIDACION/private_transcript.py'
        spec = importlib.util.spec_from_file_location('capture', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module.append_turn(root, 'saludo', 1, 'Hola', {'answer': 'Hola de prueba',
                'approval_token': 'SECRET', 'csrf': 'SECRET', 'session_id': 'SECRET'})
            p = root / 'CONVERSACION-PRIVADA.jsonl'
            self.assertNotIn('SECRET', p.read_text())
            turns = read_turns(p, root)
            self.assertEqual(turns[0]['answer'], 'Hola de prueba')
            self.assertFalse(turns[0]['erp_execution_requested'])

    def test_unrecognized_execution_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            p = root / 'x.jsonl'
            p.write_text(json.dumps({'schema': 'devia-private-turn/1', 'erp_execution_requested': True}))
            with self.assertRaises(ValueError):
                read_turns(p, root)

    def test_empty_view_explains_missing_real_erp(self):
        with tempfile.TemporaryDirectory() as folder:
            app = Center(Path(folder), autoload=False)
            app.withdraw()
            try:
                window = ConversationsWindow(app, Path(folder))
                self.assertIn('No consulta filas ERP', window.text.get('1.0', 'end'))
                self.assertIn('No hay transcripciones', window.text.get('1.0', 'end'))
                window.destroy()
            finally:
                app.close()
