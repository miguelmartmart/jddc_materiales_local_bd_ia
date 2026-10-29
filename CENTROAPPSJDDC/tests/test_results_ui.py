import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from centro import core, evidence
from centro.ui import Center
from centro.results_ui import ResultsWindow, category, report_text


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_campaign_cases_and_known_failure(self):
        p = self.root / 'RESULTADOS.json'
        p.write_text(json.dumps({'schema': 'devia-client-validation/1', 'synthetic_only': True,
            'records': [{'id': 'case_pass', 'status': 'pass'}, {'id': 'known', 'status': 'expected_failure'}]}))
        record = evidence.summarize(p, self.root)
        text = report_text(record, self.root)
        self.assertEqual(category(record), 'Tests ejecutados')
        self.assertIn('1 fallos conocidos', text)
        self.assertLess(text.index('expected_failure · known'), text.index('pass · case_pass'))

    def test_real_attempt_does_not_invent_transcript(self):
        r = core.row('informes', 'attempt', detail='INTENTO REAL: Sin cierre acreditado')
        self.assertEqual(category(r), 'Intentos reales y red')
        self.assertIn('No hay transcripción', report_text(r, self.root))

    def test_removed_file_retains_summary(self):
        r = core.row('informes', 'missing', detail='SINTÉTICO: resumen', path=self.root/'gone.json')
        self.assertIn('No se pudo leer', report_text(r, self.root))

    def test_results_ignore_inventory_filters(self):
        app = Center(self.root, autoload=False)
        app.withdraw()
        self.addCleanup(app.close)
        app.type_filter.set('Pruebas disponibles')
        app.search.set('nonexistent')
        r = core.row('informes', 'campaign', detail='RED REAL: TCP=pass')
        with patch('centro.results_ui.evidence.inventory', return_value=[r]):
            window = ResultsWindow(app, self.root)
        self.addCleanup(window.destroy)
        tree, text = window.details['Intentos reales y red']
        self.assertEqual(len(tree.get_children()), 1)
        self.assertIn('TCP=pass', text.get('1.0', 'end'))
        self.assertIn('No se han encontrado', window.details['Tests ejecutados'][1].get('1.0', 'end'))

    def test_open_results_button_uses_dedicated_window(self):
        app = Center(self.root, autoload=False)
        app.withdraw()
        self.addCleanup(app.close)
        with patch('centro.results_ui.ResultsWindow') as factory:
            app.show_devia_tests()
        factory.assert_called_once_with(app, self.root)
