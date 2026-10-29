"""Continuity across years, relocation, obsolete dates and safe UI navigation."""
import copy,json,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from centro import knowledge,equipment_summary,use_cases,core,__version__
from centro.ui import Center
from centro.continuity_ui import ContinuityWindow as HomeWindow


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/knowledge.RELATIVE;self.path.parent.mkdir(parents=True)
        self.resource={'id':'start','title':'Facturas y operaci\u00f3n','kind':'Guia','description':'Proveedor y periodo','path':'docs/start.txt','observed_at':'2026-10-26T12:00:00+01:00'}
        (self.root/'docs').mkdir();(self.root/'docs/start.txt').write_text('START GUIDANCE',encoding='utf-8')
        self.data={'schema':'jddc-continuity/1','reviewed_at':'2026-10-26T12:00:00+01:00','data_files':{'equipment_summary':'docs/current.json','use_cases':'docs/tasks.json'},'resources':[self.resource]}
        self.save()

    def save(self):self.path.write_text(json.dumps(self.data),encoding='utf-8')

    def test_relative_index_survives_relocation_and_changes_active_pointer(self):
        self.assertEqual(knowledge.load(self.root)['resources'][0]['path'],'docs/start.txt')
        self.assertEqual(knowledge.data_path(self.root,'equipment_summary','old.json'),self.root/'docs/current.json')
        self.data['data_files']['equipment_summary']='docs/new.json';self.save()
        self.assertEqual(knowledge.data_path(self.root,'equipment_summary','old.json'),self.root/'docs/new.json')
        self.assertEqual(knowledge.read_resource(self.root,self.resource),'START GUIDANCE')

    def test_no_silent_fallback_when_index_is_corrupt(self):
        self.path.write_text('{bad')
        with self.assertRaises(ValueError):knowledge.data_path(self.root,'use_cases','old.json')
        self.assertEqual(equipment_summary.inventory(self.root)[0]['state'],'bloqueado')
        self.path.unlink()
        self.assertEqual(knowledge.data_path(self.root,'use_cases','old.json'),self.root/'old.json')

    def test_current_data_can_be_replaced_without_editing_code(self):
        (self.root/'docs/current.json').write_text(json.dumps({'schema':'jddc-equipment-summary/1','generated_at':'2026-10-26T00:00:00+01:00','entries':[]}),encoding='utf-8')
        self.assertEqual(equipment_summary.inventory(self.root),[])
        task=dict(id='M1',priority='P1',roles=['Tecnico'],app='Portal',problem='Q',solution='S',owner='O',status='Propuesta',acceptance='A',source='docs/start.txt')
        (self.root/'docs/tasks.json').write_text(json.dumps({'schema':'jddc-use-cases/1','items':[task]}),encoding='utf-8')
        self.assertEqual(use_cases.load(self.root)[0]['id'],'M1')

    def test_staleness_years_future_missing_and_aware_dates(self):
        then=datetime(2026,10,26,11,tzinfo=timezone.utc)
        self.assertIn('requiere revision',knowledge.age_text(self.data['reviewed_at'],then+timedelta(days=365*3)))
        self.assertIn('Fecha futura',knowledge.age_text(self.data['reviewed_at'],then-timedelta(days=1)))
        self.assertIn('no especificada',knowledge.age_text(None,then))
        self.assertIn('no interpretable',knowledge.age_text('2026-10-26',then))
        self.assertIn('0 dias',knowledge.age_text(self.data['reviewed_at'],then))

    def test_paths_private_files_and_executable_resources_rejected(self):
        for value in ('../secret.txt','/etc/passwd','C:/secret.txt','docs\\secret.txt','.PORTAL_PRIVATE/capture.txt','docs/launch.cmd','https://host/doc.txt'):
            self.data['resources'][0]['path']=value;self.save()
            with self.subTest(value=value),self.assertRaises(ValueError):knowledge.load(self.root)

    def test_duplicate_keys_ids_bad_dates_and_oversize_index_block(self):
        original=copy.deepcopy(self.data)
        self.path.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaises(ValueError):knowledge.load(self.root)
        self.data=copy.deepcopy(original);self.data['resources']*=2;self.save()
        with self.assertRaises(ValueError):knowledge.load(self.root)
        self.data=copy.deepcopy(original);self.data['reviewed_at']='2026-10-26';self.save()
        with self.assertRaises(ValueError):knowledge.load(self.root)
        self.path.write_bytes(b' '* (core.LIMIT+1))
        with self.assertRaises(ValueError):knowledge.load(self.root)

    def test_search_is_multiterm_accent_insensitive_and_by_type(self):
        self.assertEqual(len(knowledge.find([self.resource],'OPERACION proveedor')),1)
        self.assertEqual(knowledge.find([self.resource],'operacion',kind='Incidente'),[])
        self.assertEqual(knowledge.find([self.resource],'not-found'),[])

    def app(self):
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close);return app

    def test_clean_view_has_explicit_access_to_omitted_metadata(self):
        app=self.app()
        app.rows=[core.row('informes','Documentaci\u00f3n: old.md'),dict(core.row('informes','Resumen actual'),source='equipment_summary')]
        app.render()
        self.assertFalse(app.include_files.get())
        self.assertIn('1 archivos/documentos ocultos',app.summary.get())
        rows=lambda:[r for (_,iid),r in app.visible.items() if iid.isdigit()]
        self.assertEqual(len(rows()),1)
        app.include_files.set(True);app.render();self.assertEqual(len(rows()),2)
        self.assertEqual(len(app.rows),2)

    def test_home_read_search_missing_resource_and_version_are_explicit(self):
        app=self.app()
        with patch('socket.create_connection',side_effect=AssertionError('no network')),patch('subprocess.run',side_effect=AssertionError('no process')):
            win=HomeWindow(app,self.root);win.withdraw()
            self.assertIn('START GUIDANCE',win.text.get('1.0','end'))
            self.assertIn(__version__,win.title())
            self.assertIn('No acredita estado',win.review.get())
            (self.root/'docs/start.txt').unlink();win.show_selected()
            self.assertIn('Recurso ausente',win.text.get('1.0','end'))
            win.query.set('not-found');self.assertEqual(win.tree.get_children(),())
            self.assertNotIn('START GUIDANCE',win.text.get('1.0','end'))

    def test_home_missing_index_remains_readable_without_network(self):
        self.path.unlink();app=self.app();win=HomeWindow(app,self.root);win.withdraw()
        self.assertIn('Indice no disponible',win.review.get());self.assertEqual(win.resources,[])

    def test_existing_home_is_reused_and_closed_home_can_reopen(self):
        app=self.app();app.show_home();first=app.home_window
        app.show_home();self.assertIs(first,app.home_window)
        first.destroy();app.show_home();self.assertIsNot(first,app.home_window)

    def test_link_check_reports_missing_paths_without_repair_or_presumed_success(self):
        result=knowledge.check(self.root)
        self.assertFalse(result['all_paths_available'])
        self.assertEqual(result['paths'][-1]['status'],'localizado')
        self.assertFalse((self.root/'docs/current.json').exists())
        for name in ('current.json','tasks.json'):(self.root/'docs'/name).write_text('{}')
        self.assertTrue(knowledge.check(self.root)['all_paths_available'])
