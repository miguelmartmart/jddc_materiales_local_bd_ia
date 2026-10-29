import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from centro.evidence_checks import integrity, basic_checks, local_time, comparison_text


class ChecksTests(unittest.TestCase):
    def test_contrast_must_match_capture_and_have_context(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            capture = root/'INTEGRADA-PRIVADA.json'
            capture.write_text('{}')
            d = {'schema': 'devia-cell-comparison/1', 'status': 'match', 'cells_checked': 1,
                 'different_cells': 0, 'capture_sha256': hashlib.sha256(capture.read_bytes()).hexdigest()}
            report = root/'CONTRASTE.json'
            report.write_text(json.dumps(d))
            self.assertIn('no válido', comparison_text(capture, root))
            d.update(same_dataset_declared=True, same_selection_declared=True)
            report.write_text(json.dumps(d))
            self.assertIn('Coinciden', comparison_text(capture, root))
            capture.write_text('{"changed":true}')
            self.assertIn('no válido', comparison_text(capture, root))

    def test_modified_capture_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = root / 'INTEGRADA-PRIVADA.json'
            p.write_text('{}')
            (root/'RESULTADOS.json').write_text(json.dumps({'private_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}))
            self.assertIn('coincide', integrity(p, root))
            p.write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                integrity(p, root)

    def test_empty_and_duplicate_not_semantic_pass(self):
        rows = [{'case': 'hello', 'turn': 1, 'answer': ''}] * 2
        text = basic_checks(rows)
        self.assertIn('2 sin respuesta', text)
        self.assertIn('1 identificadores repetidos', text)
        self.assertIn('no evalúan', text)

    def test_missing_timezone_never_guessed(self):
        self.assertIn('zona no indicada', local_time('2026-10-19T10:00:00'))
        self.assertEqual(local_time(None), 'Fecha no válida')
