import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch
from centro import core


class HistoryHealthTests(unittest.TestCase):
    def test_history_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            self.assertEqual(core.read_history(path), [])
            core.audit(path, 'health', 'correcto')
            rows = core.read_history(path)
            self.assertEqual(rows[0]['source'], 'history')
            self.assertEqual(rows[0]['state'], 'correcto')

    def test_history_rejects_private_and_invalid_records(self):
        for bad in ['{', '[]', json.dumps(dict(time='2026-10-15', event='scan', state='correcto', code='OK')),
                    json.dumps(dict(time=core.now(), event='secret', state='correcto', code='OK')),
                    json.dumps(dict(time=core.now(), event='scan', state='correcto', code='OK', secret='PRIVATE'))]:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'events.jsonl'
                path.write_text(bad, encoding='utf-8')
                rows = core.read_history(path)
                self.assertEqual(rows[0]['code'], 'LIMIT_REACHED')
                self.assertNotIn('PRIVATE', json.dumps(rows))

    def test_history_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'events.jsonl'
            for _ in range(3):
                core.audit(path, 'scan', 'correcto')
            self.assertEqual(len(core.read_history(path, limit=2)), 3)

    def response(self, data):
        opener = MagicMock()
        response = opener.open.return_value.__enter__.return_value
        response.status = 200
        response.read.return_value = data
        return opener

    def test_health_modes(self):
        for mode in ['synthetic-demo', 'local-client']:
            opener = self.response(json.dumps(dict(status='configured', mode=mode)).encode())
            with patch.object(core.urllib.request, 'build_opener', return_value=opener):
                result = core.local_health()
            self.assertEqual(result['state'], 'correcto')
            opener.open.assert_called_once_with('http://127.0.0.1:8781/api/health', timeout=3)

    def test_health_bad_contracts(self):
        for data in [b'bad', b'[]', b'{}', b'{"status":"configured","mode":[]}', b'x' * 4097, b'{"status":"configured","mode":"wrong","secret":"PRIVATE"}']:
            with self.subTest(data=data[:20]), patch.object(core.urllib.request, 'build_opener', return_value=self.response(data)):
                result = core.local_health()
                self.assertEqual(result['code'], 'UNEXPECTED_HEALTH')
                self.assertNotIn('PRIVATE', str(result))

    def test_health_transport_failure_no_retry(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.URLError('PRIVATE')
        with patch.object(core.urllib.request, 'build_opener', return_value=opener):
            result = core.local_health()
        self.assertEqual(result['code'], 'HTTP_FAILED')
        self.assertNotIn('PRIVATE', str(result))
        self.assertEqual(opener.open.call_count, 1)

    def test_redirect_denied(self):
        self.assertIsNone(core.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com'))

    def test_families(self):
        self.assertEqual(core.family({'name': 'DEVIA'}), 'DEVIA')
        self.assertEqual(core.family({'path': 'backend/api_clone'}), 'API SQL Obras')
        self.assertEqual(core.family({'name': 'DEVIA', 'source': 'windows'}), 'Windows')
