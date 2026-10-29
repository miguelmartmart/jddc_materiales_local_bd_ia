import json
import unittest
from centro import core


class WindowsInventoryTests(unittest.TestCase):
    def fixture(self):
        return {section: [] for section in core.WINDOWS_SECTIONS}

    def test_missing_sections_are_not_success(self):
        rows = core.windows_rows({})
        self.assertEqual(len(rows), len(core.WINDOWS_SECTIONS))
        self.assertTrue(all(r['state'] == 'bloqueado' for r in rows))

    def test_invalid_root(self):
        for value in [None, [], 'secret']:
            with self.assertRaises(ValueError): core.windows_rows(value)

    def test_partial_error_preserves_other_sections(self):
        data = self.fixture()
        data['dns'] = [{'error': 'PRIVATE_ERROR'}]
        data['system'] = [{'Caption': 'Windows'}]
        rows = core.windows_rows(data)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['state'], 'detectado')
        self.assertNotIn('PRIVATE_ERROR', str(rows))

    def test_malformed_items(self):
        data = self.fixture()
        data['routes'] = [None, 1, 'PRIVATE']
        rows = core.windows_rows(data)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['code'] == 'WINDOWS_FAILED' for r in rows))
        self.assertNotIn('PRIVATE', str(rows))

    def test_limit_and_windows_family(self):
        data = self.fixture()
        data['routes'] = [{'DestinationPrefix': 'PRIVATE_NET'}] * 301
        rows = core.windows_rows(data)
        self.assertEqual(len(rows), 301)
        self.assertEqual(rows[-1]['code'], 'LIMIT_REACHED')
        self.assertTrue(all(core.family(r) == 'Windows' for r in rows))
        self.assertNotIn('PRIVATE_NET', json.dumps(core.public_report(rows)))

    def test_empty_sections(self):
        self.assertEqual(core.windows_rows(self.fixture()), [])
