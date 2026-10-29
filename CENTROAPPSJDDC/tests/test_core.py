import json
import os
import socket
import sqlite3
import ssl
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from centro import core


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def file(self, name, data=''):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data, encoding='utf-8')
        return p

    def test_env_no_values(self):
        p = self.file('.env', 'DB_PASSWORD=top-secret\nDB_HOST=192.0.2.1\nAI_TOKEN=private\n')
        out = core.config_summary(p, self.root)
        self.assertNotIn('top-secret', str(out))
        self.assertNotIn('192.0.2.1', str(out))
        self.assertIn('ERP', out['detail'])
        self.assertEqual(out['state'], 'no_comprobado')

    def test_json_no_unknown_key_leak(self):
        p = self.file('deployment.json', '{"private-customer-name":"secret", "PORTAL_TLS_KEY":"secret.key"}')
        out = core.config_summary(p, self.root)
        self.assertNotIn('private-customer', str(out))
        self.assertNotIn('secret.key', str(out))

    def test_corrupt_json(self):
        self.assertEqual(core.config_summary(self.file('deployment.json', '{'), self.root)['code'], 'INVALID_CONFIG')

    def test_list_json(self):
        self.assertEqual(core.config_summary(self.file('deployment.json', '[]'), self.root)['code'], 'INVALID_CONFIG')

    def test_large_file(self):
        p = self.file('.env', 'a' * (core.LIMIT + 1))
        self.assertEqual(core.config_summary(p, self.root)['state'], 'bloqueado')

    def test_outside_root(self):
        with self.assertRaises(ValueError):
            core.safe_file(self.root.parent / 'other', self.root)

    def test_mock_reparse_rejected(self):
        p = self.file('config.env')
        with patch.object(core, 'linked', return_value=True):
            with self.assertRaises(ValueError): core.safe_file(p, self.root)

    def test_scan_missing(self):
        _, issues = core.walk(self.root / 'missing')
        self.assertEqual(issues, ['READ_FAILED'])

    def test_walk_file_limit(self):
        for i in range(10): self.file(f'{i}.txt')
        _, issues = core.walk(self.root, max_files=3)
        self.assertIn('LIMIT_REACHED', issues)

    def test_walk_depth_limit(self):
        self.file('a/b/c/report.txt')
        files, issues = core.walk(self.root, max_depth=0)
        self.assertFalse(files)
        self.assertIn('LIMIT_REACHED', issues)

    def test_walk_excludes_runtime(self):
        self.file('.venv/secret.log')
        self.file('normal.log')
        files, _ = core.walk(self.root)
        self.assertEqual([p.name for p in files], ['normal.log'])

    def test_version_discovery(self):
        self.file('DEVIA/pyproject.toml', '[project]\nname="devia-pilot"\nversion="0.1.4"')
        rows = core.scan(self.root)
        self.assertTrue(any(r['name'] == 'DEVIA 0.1.4' for r in rows))

    def test_report_contents_not_read(self):
        self.file('informe-secret.txt', 'sensitive business data')
        rows = core.scan(self.root)
        self.assertNotIn('sensitive business data', str(rows))

    def test_account_read_only_no_hash(self):
        db = self.root / 'accounts.sqlite'
        with closing(sqlite3.connect(db)) as c:
            c.execute('CREATE TABLE users(name TEXT, password_hash TEXT)')
            c.execute("INSERT INTO users VALUES ('employee', 'never-read-me')")
            c.commit()
        before = db.read_bytes()
        rows = core.portal_accounts(db, self.root)
        self.assertEqual(rows[0]['name'], 'employee')
        self.assertNotIn('never-read-me', str(rows))
        self.assertEqual(db.read_bytes(), before)

    def test_account_unknown_schema(self):
        db = self.root / 'db.sqlite'
        with closing(sqlite3.connect(db)): pass
        self.assertEqual(core.portal_accounts(db, self.root)[0]['code'], 'ACCOUNT_READ_FAILED')

    def test_private_key_not_decoded(self):
        p = self.file('wrong.crt', '-----BEGIN PRIVATE KEY-----\nsecret')
        with patch.object(ssl._ssl, '_test_decode_cert') as decode:
            self.assertEqual(core.cert_summary(p, self.root)['code'], 'KEY_SKIPPED')
            decode.assert_not_called()

    def test_corrupt_cert(self):
        p = self.file('bad.crt', 'invalid')
        self.assertEqual(core.cert_summary(p, self.root)['code'], 'CERT_PARSE_FAILED')

    def test_export_closed_schema(self):
        source = core.row('red', 'private-account', detail='token secret 192.0.2.1', path='C:/private')
        source.update(code='secret-token', state='customer-name', kind='password')
        result = json.dumps(core.public_report([source]))
        for value in ['private-account', '192.0.2.1', 'C:/private', 'secret-token', 'customer-name', 'password']:
            self.assertNotIn(value, result)
        self.assertIn('UNKNOWN', result)

    def test_zip_valid(self):
        dest = self.root / 'support.zip'
        core.export_zip(dest, [core.row('cuentas', 'private-name')])
        with zipfile.ZipFile(dest) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()), 3)
            self.assertNotIn(b'private-name', z.read('RESUMEN.json'))

    def test_zip_existing_preserved(self):
        dest = self.file('support.zip', 'original')
        with self.assertRaises(FileExistsError): core.export_zip(dest, [])
        self.assertEqual(dest.read_text(), 'original')

    def test_zip_failed_write_cleanup(self):
        dest = self.root / 'support.zip'
        with patch.object(zipfile.ZipFile, 'writestr', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): core.export_zip(dest, [])
        self.assertFalse(dest.exists())

    def test_audit_rejects_free_text(self):
        with self.assertRaises(ValueError): core.audit(self.root/'event', 'secret-token', 'correcto')

    def test_audit_json(self):
        p = self.root / 'log/events.jsonl'
        core.audit(p, 'scan', 'parcial', 'LIMIT_REACHED')
        self.assertEqual(json.loads(p.read_text())['code'], 'LIMIT_REACHED')

    def test_invalid_urls(self):
        for url in ['file:///etc/passwd', 'http://example.com', 'https://u:p@example.com',
                    'https://example.com?token=abc', 'https://example.com/login', 'https://example.com:99999']:
            with self.subTest(url=url), patch.object(socket, 'create_connection') as connect:
                self.assertEqual(core.probe(url)['code'], 'INVALID_URL')
                connect.assert_not_called()

    def test_timeout_no_exception_leak(self):
        with patch.object(socket, 'create_connection', side_effect=TimeoutError('secret')):
            r = core.probe('http://127.0.0.1:8781')
        self.assertEqual(r['code'], 'TIMEOUT')
        self.assertNotIn('secret', str(r))

    def test_dns_error(self):
        with patch.object(socket, 'create_connection', side_effect=socket.gaierror()):
            self.assertEqual(core.probe('https://local.invalid')['code'], 'DNS_FAILED')

    def test_tls_strict_default(self):
        ctx = ssl.create_default_context()
        self.assertTrue(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        with patch.object(ssl, 'create_default_context', return_value=ctx) as factory, \
             patch.object(socket, 'create_connection', side_effect=TimeoutError):
            core.probe('https://local.invalid')
            factory.assert_called_once_with(cafile=None)

    def test_tls_cert_failure(self):
        with patch.object(socket, 'create_connection', side_effect=ssl.SSLCertVerificationError('private')):
            self.assertEqual(core.probe('https://local.invalid')['code'], 'TLS_INVALID')

    def test_windows_command_no_mutation(self):
        for command in ['Set-Net', 'Remove-', 'Stop-Process', 'Get-Credential', 'Export-Pfx']:
            self.assertNotIn(command, core.WINDOWS_COMMAND)


if __name__ == '__main__': unittest.main()
