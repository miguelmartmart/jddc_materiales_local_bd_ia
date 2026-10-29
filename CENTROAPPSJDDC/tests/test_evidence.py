import json
from pathlib import Path
import tempfile
import unittest
from centro import evidence


class EvidenceTests(unittest.TestCase):
    def test_integrated_unknown_status_never_echoes_private_text(self):
        row = self.summarize({'mode': 'real_integrated_one_row', 'state': 'PRIVATE_SECRET'})
        self.assertEqual(row['state'], 'bloqueado')
        self.assertNotIn('PRIVATE_SECRET', str(row))

    def test_integrated_completion_requires_execution_and_cleanup(self):
        base = {'mode': 'real_integrated_one_row', 'state': 'completed_pending_comparison',
                'steps': [], 'cleanup': 'pass'}
        self.assertEqual(self.summarize(base)['state'], 'bloqueado')
        base['steps'] = [{'phase': 'execute', 'executed': True}]
        self.assertEqual(self.summarize(base)['state'], 'parcial')
        base['cleanup'] = 'blocked'
        self.assertEqual(self.summarize(base)['state'], 'bloqueado')

    def test_erp_completed_requires_five_queries_and_close(self):
        base = {'mode': 'real_erp_readonly_sample', 'state': 'completed', 'steps': [], 'cleanup': 'pass'}
        self.assertEqual(self.summarize(base)['state'], 'bloqueado')
        base['steps'] = [{'state': 'pass'}] * 5
        self.assertEqual(self.summarize(base)['state'], 'parcial')
        base['cleanup'] = 'blocked'
        row = self.summarize(base)
        self.assertEqual(row['state'], 'bloqueado')
        self.assertIn('Cierre no confirmado', row['detail'])

    def summarize(self, data):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'RESULTADOS.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            return evidence.summarize(path, Path(folder))

    def test_known_failure_not_success(self):
        result = self.summarize({'schema':'devia-client-validation/1','synthetic_only':True,
            'records':[{'status':'pass'},{'status':'expected_failure'}]})
        self.assertEqual(result['state'], 'parcial')
        self.assertIn('1 fallos conocidos', result['detail'])

    def test_running_is_not_completed_conversation(self):
        result = self.summarize({'mode':'web_real_no_erp_execution','state':'running','steps':[]})
        self.assertEqual(result['state'], 'no_comprobado')
        self.assertIn('Sin cierre acreditado', result['detail'])

    def test_private_response_never_in_details(self):
        result = self.summarize({'mode':'web_real_no_erp_execution','state':'blocked',
            'steps':[{'body':'PRIVATE_DATA','password':'SECRET'}], 'error_type':'SECRET'})
        self.assertNotIn('PRIVATE_DATA', str(result))
        self.assertNotIn('SECRET', str(result))

    def test_unknown_scope_blocks(self):
        for data in [{}, {'schema':'devia-client-validation/1','synthetic_only':False,'records':[]},
                     {'mode':'web_real_no_erp_execution','state':'fake-success'}]:
            self.assertEqual(self.summarize(data)['state'], 'bloqueado')

    def test_network_not_erp(self):
        result = self.summarize({'http_sent':False,'steps':[{'service':'web','tcp':'pass','tls':'pass'}]})
        self.assertIn('Sin HTTP', result['detail'])
        self.assertNotEqual(result['state'], 'correcto')

    def test_inventory_has_pending_and_no_raw_transcripts(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = evidence.inventory(Path(folder))
        self.assertTrue(all(r['source']=='evidence' for r in rows))
        self.assertTrue(any('ERP real' in r['name'] for r in rows))
