"""Synthetic navigation/export regression, never invokes ERP, web or installed apps."""
import copy,json,tempfile,threading,unittest,zipfile,hashlib,time
from pathlib import Path
from unittest.mock import patch
from centro import project_catalog as projects,knowledge
from centro.project_export import export_sources
from centro.explorer_ui import HomeWindow,PAGE_SIZE
from centro.ui import Center

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/projects.RELATIVE;self.path.parent.mkdir(parents=True)
        self.p=dict(id='erp',title='Operaci\u00f3n ERP',family=['ERP','Consulta'],description='Facturas proveedor',state='Pendiente',roots=['src'],tags=['ERP','IA'],resource_ids=['start'],delivery_ids=[],access_ids=[],task_apps=[])
        self.data={'schema':'jddc-projects/1','reviewed_at':'2026-10-27T09:00:00+01:00','projects':[self.p]};self.save()
        (self.root/'src/deep').mkdir(parents=True);(self.root/'src/main.py').write_text('value = 3\n')
        (self.root/'src/deep/other.py').write_text('value = 4\n')
        (self.root/'guide.txt').write_text('SYNTHETIC GUIDANCE')
        index=dict(schema='jddc-continuity/1',reviewed_at=self.data['reviewed_at'],data_files={'equipment_summary':'summary.json','use_cases':'cases.json'},resources=[dict(id='start',title='Empezar',kind='Guia',description='Ayuda',path='guide.txt',observed_at=None)])
        (self.root/knowledge.RELATIVE).write_text(json.dumps(index))
    def save(self):self.path.write_text(json.dumps(self.data),encoding='utf-8')
    def model(self):return projects.build(self.root)
    def app(self):
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close);return app
    def home(self):
        win=HomeWindow(self.app(),self.root);win.withdraw();return win
    def test_catalog_strict_ids_fields_dates_and_paths(self):
        original=copy.deepcopy(self.data)
        for change in [lambda:self.data['projects'].append(self.p),lambda:self.p.update(roots=['../outside']),lambda:self.p.update(roots=['.portal_private/secret']),lambda:self.p.update(roots=['config']),lambda:self.p.update(family=[]),lambda:self.data.update(reviewed_at='2026-10-27')]:
            self.data=copy.deepcopy(original);self.p=self.data['projects'][0];change();self.save()
            with self.assertRaises(ValueError):projects.load(self.root)
    def test_graph_rejects_cycles_and_missing_parents(self):
        for nodes in [[projects.Node('a','a','Familia','b')],[projects.Node('a','a','Familia','b'),projects.Node('b','b','Familia','a')]]:
            with self.assertRaises(ValueError):projects.Catalog(nodes)
    def test_global_partial_multiword_accents_and_tags(self):
        m=self.model()
        self.assertEqual(m.search('OPERACION prove',kind='Proyecto')[0].project,'erp')
        self.assertEqual(len(m.search('',kind='Proyecto',tag='IA')),1)
        self.assertEqual(m.search('impossible'),[])
        self.assertEqual(m.search('',kind='Proyecto',tag='Seguridad'),[])
    def test_scope_and_state_filters_include_descendants(self):
        m=self.model();family=m.children['root'][0]
        self.assertEqual(len(m.search('proveedor',scope=family,kind='Proyecto',state='Pendiente')),1)
        self.assertEqual(m.search('proveedor',scope='project:erp:guides',kind='Proyecto'),[])
    def test_unicode_search_matches_short_terms(self):
        n=projects.Node('n','\u6570\u636e','Proyecto');m=projects.Catalog([n])
        self.assertEqual(m.search('\u6570')[0].id,'n')
    def test_one_level_listing_no_content_read(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('no read')):
            found,partial=projects.folder_entries(self.root,'src')
        self.assertFalse(partial);self.assertEqual(len(found),2);self.assertNotIn('src/deep/other.py',[p for p,d in found])
    def test_folder_limits_and_runtime_paths(self):
        found,partial=projects.folder_entries(self.root,'src',limit=1);self.assertTrue(partial);self.assertEqual(len(found),1)
        with self.assertRaises(ValueError):projects.folder_entries(self.root,'../other')
    def test_opening_home_does_not_execute_or_read_business_sources(self):
        with patch('socket.create_connection',side_effect=AssertionError('network')),patch('subprocess.run',side_effect=AssertionError('process')),patch('os.startfile',side_effect=AssertionError('launch')):
            win=self.home();self.assertIn('1 proyectos',win.review.get());self.assertEqual(win.current,'root')
    def test_navigation_back_forward_preserves_query_filters_and_page(self):
        win=self.home();win.query.set('operacion');win.kind.set('Proyecto');win.tag.set('IA');win.flush_search();before=win.snapshot()
        win.navigate('project:erp');self.assertEqual(win.query.get(),'');self.assertEqual(len(win.tree.get_children()),5)
        win.back();self.assertEqual(win.snapshot(),before);win.forward();self.assertEqual(win.current,'project:erp')
    def test_nested_code_folders_up_and_back(self):
        win=self.home();key='project:erp:code:0';win.navigate(key,'src');self.assertEqual(len(win.visible),2)
        deep=next(n for n in win.visible.values() if n.path=='src/deep');win.selected=deep;win.open_selected();self.assertEqual(win.folder,'src/deep')
        win.up();self.assertEqual(win.folder,'src');win.up();self.assertEqual(win.folder,'')
    def test_selection_is_invalidated_immediately_during_search(self):
        win=self.home();win.quick_filter('Proyecto');key=next(iter(win.visible));win.tree.selection_set(key);win.show_selected();self.assertIsNotNone(win.selected)
        win.query.set('missing');self.assertIsNone(win.selected);self.assertIn('disabled',win.download_button.state());win.flush_search();self.assertEqual(win.tree.get_children(),())
    def test_guides_load_only_on_explicit_open(self):
        win=self.home();win.navigate('project:erp:guides');key=next(iter(win.visible));win.tree.selection_set(key);win.show_selected()
        self.assertNotIn('SYNTHETIC GUIDANCE',win.text.get('1.0','end'));win.open_selected();self.assertIn('SYNTHETIC GUIDANCE',win.text.get('1.0','end'))
    def test_lazy_navigation_expands_without_duplicates(self):
        win=self.home();initial=len(win.nav.get_children('root'));self.assertEqual(initial,1)
        family=win.model.children['root'][0];win.populate_nav(family);first=win.nav.get_children(family);win.populate_nav(family);self.assertEqual(first,win.nav.get_children(family))
        win.navigate('project:erp:guides');self.assertTrue(win.nav.exists('project:erp:guides'))
    def test_many_results_are_paged_not_truncated(self):
        self.data['projects']=[dict(self.p,id='p'+str(i),title='Project '+str(i)) for i in range(250)];self.save()
        win=self.home();win.quick_filter('Proyecto');self.assertEqual(win.total,250);self.assertEqual(len(win.visible),PAGE_SIZE)
        win.turn_page(1);self.assertEqual(len(win.visible),100);win.turn_page(1);self.assertEqual(len(win.visible),50);win.turn_page(-1);self.assertEqual(len(win.visible),100)
    def test_close_with_pending_search_cancels_callbacks(self):
        win=self.home();win.query.set('pending');win.destroy();self.assertTrue(win._closed);self.assertTrue(win.cancel_export.is_set())
    def test_missing_catalog_preserves_tools_and_explains_absence(self):
        self.path.unlink();win=self.home();self.assertIn('no disponible',win.review.get());self.assertEqual(win.visible,{})
    def export(self,name='export.zip',selected=None,cancel=None,progress=lambda text:None):
        return export_sources(self.root,selected or [self.p],self.root/name,cancel or threading.Event(),progress)
    def test_export_manifest_hashes_nested_sources_and_no_execution(self):
        with patch('subprocess.run',side_effect=AssertionError('no process')):result=self.export()
        self.assertEqual(result['files'],3)
        with zipfile.ZipFile(self.root/'export.zip') as z:
            m=json.loads(z.read('MANIFIESTO-PROYECTOS.json'))
            for rel,meta in m['files'].items():self.assertEqual(hashlib.sha256(z.read(rel)).hexdigest(),meta['sha256'])
    def test_export_omits_private_runtime_binary_and_literal_secret(self):
        for folder in ['config','.portal_private','data','node_modules']:
            path=self.root/'src'/folder;path.mkdir();(path/'sensitive.txt').write_text('private')
        for name,text in [('key.pem','PRIVATE KEY'),('secret.txt','hidden'),('normal.py','password = "real-value-for-synthetic-test"'),('image.png','binary')]:
            (self.root/'src'/name).write_text(text)
        self.export()
        with zipfile.ZipFile(self.root/'export.zip') as z:
            names=z.namelist();self.assertNotIn('src/normal.py',names);self.assertNotIn('src/secret.txt',names);self.assertFalse(any('/config/' in n or 'node_modules' in n for n in names))
    def test_existing_export_is_never_overwritten(self):
        (self.root/'export.zip').write_bytes(b'old')
        with self.assertRaises(FileExistsError):self.export()
        self.assertEqual((self.root/'export.zip').read_bytes(),b'old')
    def test_cancel_before_and_during_export_leaves_no_output(self):
        cancel=threading.Event();cancel.set()
        with self.assertRaises(ValueError):self.export(cancel=cancel)
        self.assertFalse((self.root/'export.zip').exists())
        cancel.clear()
        with self.assertRaises(ValueError):self.export(cancel=cancel,progress=lambda _:cancel.set())
        self.assertFalse((self.root/'export.zip').exists())
    def test_changed_or_unknown_catalog_record_cannot_select_other_roots(self):
        p=dict(self.p,roots=['guide.txt'])
        with self.assertRaises(ValueError):self.export(selected=[p])
    def test_export_failure_cleans_only_its_new_output(self):
        with patch('centro.project_export.zipfile.ZipFile.writestr',side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):self.export()
        self.assertFalse((self.root/'export.zip').exists())
    def test_shared_sources_are_stored_once_for_bulk_export(self):
        other=dict(self.p,id='other');self.data['projects'].append(other);self.save();result=self.export(selected=[self.p,other])
        self.assertEqual(result['files'],3);self.assertEqual(result['projects'],2)
    def test_catalog_cannot_export_entire_workspace_as_source(self):
        self.p['roots']=['.'];self.save()
        with self.assertRaises(ValueError):projects.load(self.root)
    def test_cancel_during_write_removes_its_partial_archive(self):
        cancel=threading.Event()
        def progress(text):
            if text.startswith('Guardando'):cancel.set()
        with self.assertRaises(ValueError):self.export(cancel=cancel,progress=progress)
        self.assertFalse((self.root/'export.zip').exists())
    def test_changed_source_during_export_does_not_leave_output(self):
        def progress(text):
            if text.startswith('Guardando'):(self.root/'guide.txt').write_text('CHANGED')
        with self.assertRaises(ValueError):self.export(progress=progress)
        self.assertFalse((self.root/'export.zip').exists())
    def test_source_limit_fails_before_creating_output(self):
        with patch('centro.project_export.MAX_FILES',1),self.assertRaises(ValueError):self.export()
        self.assertFalse((self.root/'export.zip').exists())
