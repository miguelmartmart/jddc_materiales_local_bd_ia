import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from centro.ui import Center
from centro import core


class UITests(unittest.TestCase):
    def test_actions_stay_in_their_sections(self):
        def buttons(widget):
            found = []
            for child in widget.winfo_children():
                if child.winfo_class() == 'TButton':
                    found.append(child.cget('text'))
                found.extend(buttons(child))
            return found
        self.assertNotIn('Resultados de pruebas', buttons(self.app.top))
        self.assertNotIn('Exportar resumen ZIP…', buttons(self.app.top))
        self.assertNotIn('Portal Ubuntu', buttons(self.app.top))
        reports = self.app.notebook.nametowidget(self.app.notebook.tabs()[9])
        self.assertIn('Resultados de pruebas', buttons(reports))
        self.assertIn('Exportar resumen ZIP…', buttons(reports))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Center(Path(self.tmp.name), autoload=False)
        self.app.withdraw()
        self.addCleanup(self.app.close)

    def test_hierarchical_details(self):
        self.app.rows = [core.row('aplicaciones', 'DEVIA 0.1.4', path='C:/demo')]
        self.app.render()
        tree = self.app.trees['aplicaciones']
        self.assertEqual(len(tree.get_children('0')), 1)
        self.app.populate_details(tree,'0')
        self.assertEqual(len(tree.get_children('0')), 3)
        tree.selection_set('0')
        self.app.select(tree)
        self.assertIn('C:/demo', self.app.detail.get('1.0', 'end'))

    def test_filter(self):
        self.app.rows = [core.row('aplicaciones', 'DEVIA'), core.row('aplicaciones', 'Portal')]
        self.app.search.set('portal')
        self.app.render()
        self.assertEqual(len(self.app.trees['aplicaciones'].get_children()), 1)

    def test_state_filter(self):
        self.app.rows = [core.row('red', 'A', 'correcto'), core.row('red', 'B', 'fallo')]
        self.app.state_filter.set('fallo')
        self.app.render()
        self.assertEqual(len(self.app.trees['red'].get_children()), 1)

    def test_background_error_visible(self):
        self.app.events.put(('scan', [], 'READ_FAILED'))
        self.app.poll()
        self.assertEqual(self.app.rows[0]['code'], 'READ_FAILED')
        self.assertFalse(self.app.busy)

    def test_log_error_visible(self):
        with patch.object(core, 'audit', side_effect=PermissionError('private')):
            self.app.log('scan', 'fallo')
        self.assertIn('No se pudo guardar', self.app.status.get())
        self.assertNotIn('private', self.app.status.get())

    def test_missing_selection(self):
        self.app.open_location()
        self.assertIn('Selecciona', self.app.status.get())

    def test_no_scan_during_smoke(self):
        self.assertEqual(self.app.rows, [])
        self.assertFalse(self.app.busy)

    def test_family_filter(self):
        self.app.rows = [core.row('aplicaciones', 'DEVIA'), core.row('aplicaciones', 'Portal')]
        self.app.family_filter.set('DEVIA')
        self.assertEqual(self.app.trees['aplicaciones'].get_children(), ('group:DEVIA',))

    def test_refresh_preserves_measured_results(self):
        measured = dict(core.row('red', 'TCP', 'correcto'), source='probe')
        self.app.rows = [measured, core.row('aplicaciones', 'old')]
        self.app.events.put(('scan', [core.row('aplicaciones', 'new')], None))
        self.app.poll()
        self.assertIn(measured, self.app.rows)
        self.assertNotIn('old', [r['name'] for r in self.app.rows])

    def test_history_replaces_without_duplication(self):
        record = dict(core.row('informes', 'Historial'), source='history')
        for _ in range(2):
            self.app.events.put(('history', [record], None))
            self.app.poll()
        self.assertEqual(self.app.rows, [record])

    def test_small_screen_detail_visible(self):
        self.app.deiconify()
        self.app.geometry('974x668')
        self.app.update()
        self.assertGreater(self.app.detail.winfo_height(), 40)
        self.assertLess(self.app.detail.winfo_rooty() + self.app.detail.winfo_height(),
                        self.app.winfo_rooty() + self.app.winfo_height())

    def test_maximize_gives_table_more_height_and_restores(self):
        self.app.deiconify()
        self.app.geometry('974x668')
        self.app.update()
        self.app.set_initial_sash()
        self.app.update()
        tree = self.app.trees['aplicaciones']
        normal = tree.winfo_height()
        self.assertGreater(normal, 170)
        self.app.toggle_table()
        self.app.update()
        self.assertGreater(tree.winfo_height(), normal + 100)
        self.assertEqual(len(self.app.panes.panes()), 1)
        self.app.toggle_table()
        self.assertEqual(len(self.app.panes.panes()), 2)

    def test_sort_name_both_directions(self):
        self.app.rows = [core.row('aplicaciones', 'DEVIA Z'), core.row('aplicaciones', 'DEVIA A')]
        self.app.render()
        tree = self.app.trees['aplicaciones']
        self.app.sort_tree(tree, '#0')
        self.assertEqual(tree.get_children('group:DEVIA'), ('1', '0'))
        self.app.sort_tree(tree, '#0')
        self.assertEqual(tree.get_children('group:DEVIA'), ('0', '1'))

    def test_sort_dates_uses_offsets(self):
        a, b = core.row('red', 'A'), core.row('red', 'B')
        a['checked_at'] = '2026-10-19T12:00:00+02:00'
        b['checked_at'] = '2026-10-19T11:00:00+00:00'
        self.app.rows = [a, b]
        self.app.render()
        tree = self.app.trees['red']
        self.app.sort_tree(tree, 'time')
        group = tree.get_children()[0]
        self.assertEqual(tree.get_children(group), ('0', '1'))

    def test_type_filter_and_clear(self):
        # This existing test exercises the explicit full metadata view.
        self.app.include_files.set(True)
        self.app.rows = [core.row('informes', 'Documentación: README.md'), core.row('informes', 'informe.json')]
        self.app.type_filter.set('Documentación')
        self.assertEqual(len([r for (t,i),r in self.app.visible.items() if i.isdigit()]), 1)
        self.app.clear_filters()
        self.assertEqual(len([r for (t,i),r in self.app.visible.items() if i.isdigit()]), 2)

    def test_filter_clears_stale_private_detail(self):
        self.app.detail.configure(state='normal')
        self.app.detail.insert('1.0', 'PREVIOUS_PRIVATE_DETAIL')
        self.app.render()
        self.assertNotIn('PREVIOUS_PRIVATE_DETAIL', self.app.detail.get('1.0', 'end'))

    def test_sort_survives_render(self):
        self.app.rows = [core.row('aplicaciones', 'DEVIA Z'), core.row('aplicaciones', 'DEVIA A')]
        self.app.render()
        tree = self.app.trees['aplicaciones']
        self.app.sort_tree(tree, '#0')
        self.app.render()
        self.assertEqual(tree.get_children('group:DEVIA'), ('1', '0'))


if __name__ == '__main__': unittest.main()
