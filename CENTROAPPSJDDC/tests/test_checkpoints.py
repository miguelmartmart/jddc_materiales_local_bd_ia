"""Business meaning of continuity points: no renewed evidence or false success."""
import copy,json,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from centro import checkpoints,core,knowledge
from centro.ui import Center
from centro.checkpoints_ui import CheckpointsWindow


class CheckpointsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.index=self.root/knowledge.RELATIVE;self.index.parent.mkdir(parents=True)
        (self.root/'docs').mkdir()
        self.document=self.root/'docs/guide.txt';self.document.write_text('PRIVATE CONTENT NOT TO COPY',encoding='utf-8')
        (self.root/'docs/current.json').write_text('{}');(self.root/'docs/tasks.json').write_text('{}')
        self.data={'schema':'jddc-continuity/1','reviewed_at':'2026-10-26T12:00:00+01:00',
            'data_files':{'equipment_summary':'docs/current.json','use_cases':'docs/tasks.json'},
            'resources':[{'id':'guide','title':'Guide','kind':'Guia','description':'Test','path':'docs/guide.txt','observed_at':'2026-10-20T10:00:00+00:00'}]}
        self.write_index()

    def write_index(self):self.index.write_text(json.dumps(self.data),encoding='utf-8')
    def item(self,point,key='resource:guide'):return next(i for i in point['items'] if i['id']==key)
    def difference(self,a,b):return next(i for i in checkpoints.compare(a,b) if i['id']=='resource:guide')
    def point_path(self,point):return self.root/checkpoints.DIRECTORY/(point['id']+'.json')

    def test_capture_after_years_never_renews_observation_or_stores_content(self):
        with patch('socket.create_connection',side_effect=AssertionError('no network')),patch('subprocess.run',side_effect=AssertionError('no command')):
            point=checkpoints.collect(self.root,clock=lambda:datetime(2036,1,1,tzinfo=timezone.utc))
        self.assertEqual(self.item(point)['declared_observed_at'],'2026-10-20T10:00:00+00:00')
        self.assertEqual(point['index_reviewed_at'],self.data['reviewed_at'])
        self.assertFalse(point['scope']['historical_evidence_renewed']);self.assertFalse(point['scope']['remote_state_checked'])
        self.assertNotIn('PRIVATE CONTENT',json.dumps(point));self.assertFalse((self.root/checkpoints.DIRECTORY).exists())

    def test_collect_does_not_modify_documents_or_claim_atomic_snapshot(self):
        raw=self.document.read_bytes();mtime=self.document.stat().st_mtime_ns
        point=checkpoints.collect(self.root)
        self.assertEqual(raw,self.document.read_bytes());self.assertEqual(mtime,self.document.stat().st_mtime_ns)
        self.assertFalse(point['scope']['cross_file_atomic_snapshot_verified'])

    def test_save_is_append_only_and_reads_do_not_create_directories(self):
        self.assertEqual(checkpoints.list_ids(self.root),[])
        self.assertFalse((self.root/checkpoints.DIRECTORY).exists())
        first=checkpoints.save(self.root);raw=self.point_path(first).read_bytes()
        second=checkpoints.save(self.root)
        self.assertNotEqual(first['id'],second['id']);self.assertEqual(raw,self.point_path(first).read_bytes())
        self.assertEqual(checkpoints.read(self.root,first['id']),first)
        self.assertEqual(len(checkpoints.list_ids(self.root)),2)

    def test_changed_file_unchanged_reference_and_dates_reported_separately(self):
        before=checkpoints.collect(self.root);self.document.write_text('UPDATED CONTENT')
        after=checkpoints.collect(self.root)
        self.assertEqual(self.difference(before,after)['status'],'Archivo cambiado')
        self.assertEqual(self.item(before)['declared_observed_at'],self.item(after)['declared_observed_at'])
        self.assertEqual(self.difference(after,checkpoints.collect(self.root))['status'],'Sin cambios de archivo/referencia')

    def test_unavailable_twice_never_becomes_unchanged_or_success(self):
        self.document.unlink();before=checkpoints.collect(self.root);after=checkpoints.collect(self.root)
        self.assertEqual(self.item(after)['status'],'unavailable')
        self.assertEqual(self.difference(before,after)['status'],'Contenido no verificable ahora')
        self.document.write_text('Restored')
        self.assertEqual(self.difference(after,checkpoints.collect(self.root))['status'],'Ahora disponible;sin contraste previo')

    def test_removed_reference_does_not_mean_deleted_file(self):
        before=checkpoints.collect(self.root);self.data['resources'][0]['id']='renamed';self.write_index()
        diffs=checkpoints.compare(before,checkpoints.collect(self.root))
        self.assertEqual(next(x for x in diffs if x['id']=='resource:guide')['status'],'Referencia retirada')
        self.assertEqual(next(x for x in diffs if x['id']=='resource:renamed')['status'],'Referencia nueva')
        self.assertTrue(self.document.exists())

    def test_destination_change_and_metadata_change_are_explicit(self):
        before=checkpoints.collect(self.root);(self.root/'docs/new.txt').write_bytes(self.document.read_bytes())
        self.data['resources'][0]['path']='docs/new.txt';self.write_index();after=checkpoints.collect(self.root)
        self.assertEqual(self.difference(before,after)['status'],'Destino de referencia cambiado')
        self.data['resources'][0]['title']='New title';self.write_index()
        self.assertEqual(self.difference(after,checkpoints.collect(self.root))['status'],'Metadatos de referencia cambiados')

    def test_corruption_and_duplicate_json_keys_are_not_silently_accepted(self):
        point=checkpoints.save(self.root);path=self.point_path(point)
        bad=copy.deepcopy(point);bad['items'][0]['title']='FAKE';path.write_text(json.dumps(bad))
        with self.assertRaises(ValueError):checkpoints.read(self.root,point['id'])
        with self.assertRaises(ValueError):checkpoints.save(self.root)
        self.assertEqual(len(checkpoints.list_ids(self.root)),1)
        raw=json.dumps(point);path.write_text(raw[:-1]+',"schema":"jddc-continuity-point/1"}')
        with self.assertRaises(ValueError):checkpoints.read(self.root,point['id'])

    def test_invalid_ids_private_paths_and_naive_clock_are_rejected(self):
        for identifier in ('../secret','C:/secret','abc'):
            with self.assertRaises(ValueError):checkpoints.read(self.root,identifier)
        with self.assertRaises(ValueError):checkpoints.collect(self.root,clock=lambda:datetime(2030,1,1))
        point=checkpoints.collect(self.root);point['items'][0]['path']='.portal_private/secret.txt'
        with self.assertRaises(ValueError):checkpoints.validate(point)

    def test_limit_preserves_old_points_and_unexpected_files_are_visible(self):
        with patch.object(checkpoints,'MAX_POINTS',2):
            first=checkpoints.save(self.root);second=checkpoints.save(self.root)
            with self.assertRaises(ValueError):checkpoints.save(self.root)
        self.assertEqual(len(checkpoints.list_ids(self.root)),2)
        (self.root/checkpoints.DIRECTORY/'unexpected.txt').write_text('Do not remove')
        with self.assertRaises(ValueError):checkpoints.list_ids(self.root)
        self.assertTrue(self.point_path(first).exists());self.assertTrue(self.point_path(second).exists())

    def test_clock_rollback_does_not_replace_the_latest_capture(self):
        later=checkpoints.collect(self.root,clock=lambda:datetime(2040,1,1,tzinfo=timezone.utc))
        with patch.object(checkpoints,'collect',return_value=later):checkpoints.save(self.root)
        with self.assertRaises(ValueError):checkpoints.save(self.root)
        self.assertEqual(checkpoints.list_ids(self.root),[later['id']])

    def test_index_change_during_capture_stops_before_saving(self):
        original=core.safe_file;seen=0
        def reading(path,root,limit=core.LIMIT):
            nonlocal seen
            if path==self.index:
                seen+=1
                if seen>=4:return b'CHANGED'
            return original(path,root,limit)
        with patch.object(core,'safe_file',side_effect=reading),self.assertRaises(ValueError):checkpoints.collect(self.root)
        self.assertFalse((self.root/checkpoints.DIRECTORY).exists())

    def test_unsafe_storage_directory_is_rejected(self):
        directory=self.root/checkpoints.DIRECTORY;directory.mkdir(parents=True)
        original=core.linked
        with patch.object(core,'linked',side_effect=lambda p:p==directory or original(p)),self.assertRaises(ValueError):checkpoints.save(self.root)

    def test_ui_does_not_save_on_open_and_requires_explicit_action(self):
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close)
        with patch('socket.create_connection',side_effect=AssertionError('no network')):
            win=CheckpointsWindow(app,self.root);win.withdraw()
            self.assertIn('Sin punto anterior',win.summary.get());self.assertFalse((self.root/checkpoints.DIRECTORY).exists())
            win.save();self.assertEqual(len(checkpoints.list_ids(self.root)),1)
            self.assertIn('no se han modificado',win.summary.get())
            self.assertEqual(win.tree.get_children(),())
            win.changed.set(False);win.render();self.assertEqual(len(win.tree.get_children()),4)

    def test_latest_invalid_point_does_not_fall_back_to_an_older_point(self):
        older=checkpoints.save(self.root);latest=checkpoints.save(self.root)
        self.point_path(latest).write_text('BROKEN PRIVATE DETAILS')
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close)
        win=CheckpointsWindow(app,self.root);win.withdraw()
        self.assertIn('no disponible',win.summary.get());self.assertTrue(win.save_button.instate(['disabled']))
        self.assertEqual(win.baseline.get(),latest['id']);self.assertNotIn('PRIVATE',win.summary.get())
        self.assertEqual(checkpoints.read(self.root,older['id']),older)
