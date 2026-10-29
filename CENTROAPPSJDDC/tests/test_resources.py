import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from centro import core


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_categories_without_reading_contents(self):
        for name, kind in [('README.md', 'informes'), ('requirements.txt', 'configuracion'),
                           ('package.json', 'configuracion'), ('run.cmd', 'aplicaciones'),
                           ('test_example.py', 'informes'), ('map.pmtiles', 'configuracion'),
                           ('backup.zip', 'informes'), ('app.service', 'aplicaciones')]:
            with self.subTest(name=name):
                path = self.root / name
                path.write_text('PRIVATE_CONTENT')
                with patch.object(core, 'safe_file', side_effect=AssertionError('must not read')):
                    result = core.resource_summary(path, self.root)
                self.assertEqual(result['kind'], kind)
                self.assertEqual(result['state'], 'no_comprobado')
                self.assertNotIn('PRIVATE_CONTENT', str(result))
                self.assertIn('Modificado:', result['detail'])

    def test_private_material_not_indexed_as_resource(self):
        for name in ['private.key', 'identity.pfx', '.env', 'passwords.txt']:
            self.assertIsNone(core.resource_summary(self.root / name, self.root))

    def test_missing_resource_visible(self):
        result = core.resource_summary(self.root / 'README.md', self.root)
        self.assertEqual(result['code'], 'READ_FAILED')

    def test_external_resource_rejected(self):
        result = core.resource_summary(self.root.parent / 'README.md', self.root)
        self.assertEqual(result['code'], 'READ_FAILED')

    def test_scan_includes_resources_once(self):
        (self.root / 'informe.zip').write_bytes(b'not a zip')
        rows = core.scan(self.root)
        resources = [r for r in rows if r['path'].endswith('informe.zip')]
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['state'], 'no_comprobado')
