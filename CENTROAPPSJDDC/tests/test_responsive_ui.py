"""Responsive local UI without automatic scans or loss of diagnostic detail."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from centro import core
from centro.ui import Center
from centro.search_index import SearchIndex


class ResponsiveUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.app=Center(self.root,autoload=False);self.app.withdraw();self.addCleanup(self.app.close)

    def pump(self,ms=180):
        self.app.after(ms,self.app.quit);self.app.mainloop()

    def test_startup_context_does_not_run_inventory_windows_health_or_network(self):
        with patch('centro.ui.core.scan',side_effect=AssertionError('no scan')),patch('centro.ui.core.windows_inventory',side_effect=AssertionError('no windows')),patch('centro.ui.core.local_health',side_effect=AssertionError('no HTTP')),patch('socket.create_connection',side_effect=AssertionError('no network')):
            self.app.load_context();self.app.load_context()
        self.assertFalse(self.app.inventory_loaded)
        self.assertEqual(len(self.app.rows),1)
        self.assertIn('pendiente',self.app.summary.get())

    def test_normal_autoload_opens_guidance_but_does_not_scan(self):
        with patch('centro.ui.core.scan') as scan,patch('centro.ui.evidence.inventory') as evidence,patch('socket.create_connection',side_effect=AssertionError('no network')):
            other=Center(self.root,autoload=True);other.withdraw();self.addCleanup(other.close)
            other.after(300,other.quit);other.mainloop()
            self.assertTrue(other._context_loaded);self.assertIsNotNone(other.home_window)
            self.assertFalse(other.inventory_loaded);scan.assert_not_called();evidence.assert_not_called()

    def test_explicit_refresh_replaces_pending_context_and_preserves_measured_dates(self):
        self.app.load_context()
        measured=dict(core.row('red','Measured',path='x'),source='probe');stamp=measured['checked_at'];self.app.rows.append(measured)
        fresh=core.row('aplicaciones','Fresh app')
        with patch('centro.ui.core.scan',return_value=[fresh]) as scan,patch('centro.ui.evidence.inventory',return_value=[]),patch('centro.ui.equipment_summary.inventory',return_value=[]):
            self.app.refresh();self.pump(300);scan.assert_called()
        self.assertTrue(self.app.inventory_loaded);self.assertIn(fresh,self.app.rows)
        self.assertFalse(any(r.get('source')=='startup_context' for r in self.app.rows))
        self.assertEqual(next(r for r in self.app.rows if r['name']=='Measured')['checked_at'],stamp)

    def test_typing_burst_produces_one_filter_rebuild(self):
        self.app.rows=[core.row('informes','Invoice alpha')]
        with patch.object(self.app,'render',wraps=self.app.render) as render:
            for value in ('i','in','inv','invo','invoice'):self.app.search.set(value)
            self.assertEqual(render.call_count,0)
            self.pump(200);self.assertEqual(render.call_count,1)
        self.assertIsNone(self.app._render_job)

    def test_pending_search_immediately_removes_stale_selection_and_private_detail(self):
        self.app.rows=[core.row('informes','Old',detail='PRIVATE OLD DETAIL')];self.app.render()
        tree=self.app.trees['informes'];tree.selection_set('0');self.app.select(tree)
        self.assertIn('PRIVATE OLD DETAIL',self.app.detail.get('1.0','end'))
        self.app.search.set('absent')
        self.assertIsNone(self.app.selected);self.assertEqual(self.app.visible,{})
        self.app.select(tree);self.assertNotIn('PRIVATE OLD DETAIL',self.app.detail.get('1.0','end'))
        self.app.render();self.assertIsNone(self.app._render_job)

    def test_closed_tree_creates_details_only_on_open_and_reuses_them(self):
        self.app.rows=[core.row('informes','Detailed',detail='Full details')];self.app.render()
        tree=self.app.trees['informes'];self.assertEqual(len(tree.get_children('0')),1)
        self.app.populate_details(tree,'0');self.assertEqual(len(tree.get_children('0')),3)
        ids=tree.get_children('0');self.app.populate_details(tree,'0');self.assertEqual(ids,tree.get_children('0'))
        self.assertIn('Full details',tree.item(ids[1],'text'))

    def test_expand_all_still_exposes_every_detail(self):
        self.app.rows=[core.row('informes','A'),core.row('informes','B')];self.app.render()
        self.app.notebook.select(self.app.notebook.tabs()[9]);self.app.expand(True)
        tree=self.app.trees['informes']
        self.assertEqual(len(tree.get_children('0')),3);self.assertEqual(len(tree.get_children('1')),3)

    def test_pending_search_is_safely_cancelled_on_close(self):
        self.app.search.set('pending');self.assertIsNotNone(self.app._render_job)
        self.app.close();self.app.render();self.app.close()


class SearchIndexTests(unittest.TestCase):
    def test_words_accents_case_and_unicode(self):
        index=SearchIndex();rows=[core.row('informes','Facturaci\u00f3n',detail='Cliente Fran\u00e7ois'),core.row('informes','\u57ce\u5e02 invoice')]
        self.assertEqual([i for i,r in index.select(rows,'FRANCOIS facturacion')],[0])
        self.assertEqual([i for i,r in index.select(rows,'invoice \u57ce\u5e02')],[1])
        self.assertEqual(index.select(rows,'no-match'),[])

    def test_modified_and_removed_records_do_not_reuse_stale_text(self):
        index=SearchIndex();row=core.row('informes','Old')
        self.assertEqual(len(index.select([row],'old')),1)
        row['name']='New';self.assertEqual(index.select([row],'old'),[])
        self.assertEqual(len(index.select([row],'new')),1);self.assertEqual(index.cached_records,1)
        index.select([],'new');self.assertEqual(index.cached_records,0)

    def test_empty_query_shows_every_record_and_releases_search_cache(self):
        index=SearchIndex();rows=[core.row('informes','Alpha'),core.row('informes','Beta')]
        index.select(rows,'alpha');self.assertEqual(index.cached_records,2)
        self.assertEqual([i for i,r in index.select(rows,'')],[0,1]);self.assertEqual(index.cached_records,0)
