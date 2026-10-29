"""Local downloads: immutable existing files, honest provenance and no vault reads."""
import copy,hashlib,json,os,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from centro import delivery_access as catalog,knowledge,core
from centro.ui import Center
from centro.delivery_access_ui import DeliveryAccessWindow


class DeliveryAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/catalog.RELATIVE;self.path.parent.mkdir(parents=True)
        (self.root/'DEVIA_VALIDACION').mkdir();self.zip=self.root/'DEVIA_VALIDACION/sample.zip'
        with zipfile.ZipFile(self.zip,'w') as archive:archive.writestr('test.txt','SYNTHETIC')
        self.sha=hashlib.sha256(self.zip.read_bytes()).hexdigest()
        self.item=dict(id='Z1',title='Test delivery',state='Candidato',purpose='Review only',path='DEVIA_VALIDACION/sample.zip',expected_sha256=self.sha)
        self.doc=self.root/'docs/access.txt';self.doc.parent.mkdir();self.doc.write_text('REFERENCE GUIDE',encoding='utf-8')
        self.access=dict(id='A1',app='Test app',manager='windows_vault',location='OS vault',status='Not checked',next_step='Individual access',guide='docs/access.txt')
        self.data={'schema':'jddc-deliveries-access/1','reviewed_at':'2026-10-26T12:00:00+01:00','deliveries':[self.item],'access':[self.access]}
        self.save()

    def save(self):self.path.write_text(json.dumps(self.data),encoding='utf-8')
    def sidecar(self,value=None,name='sample.zip'):
        self.zip.with_name(self.zip.name+'.sha256').write_text((value or self.sha)+'  '+name+'\n',encoding='utf-8')

    def test_catalog_does_not_launch_managers_or_network(self):
        with patch('subprocess.Popen',side_effect=AssertionError('no launch')),patch('socket.create_connection',side_effect=AssertionError('no network')):
            self.assertEqual(len(catalog.load(self.root)['access']),1)
            self.assertEqual(catalog.guide(self.root,self.access),'REFERENCE GUIDE')

    def test_closed_access_schema_rejects_secret_fields_and_arbitrary_launchers(self):
        for key,value in [('password','SECRET'),('token','SECRET'),('command','arbitrary')]:
            bad=copy.deepcopy(self.data);bad['access'][0][key]=value;self.path.write_text(json.dumps(bad))
            with self.subTest(key=key),self.assertRaises(ValueError):catalog.load(self.root)
        self.save();self.data['access'][0]['manager']='execute';self.save()
        with self.assertRaises(ValueError):catalog.load(self.root)

    def test_private_or_external_catalog_paths_are_rejected(self):
        for path in ('../secret.zip','C:/secret.zip','.PORTAL_PRIVATE/secret.zip','https://host/file.zip'):
            self.data['deliveries'][0]['path']=path;self.save()
            with self.subTest(path=path),self.assertRaises(ValueError):catalog.load(self.root)

    def test_pinned_and_sidecar_checks_are_distinct_from_signature(self):
        self.sidecar();result=catalog.verify(self.root,self.item)
        self.assertEqual(result['sha256'],self.sha);self.assertEqual(result['reference'],'catalogo y SHA local')
        self.assertFalse(result['publisher_signature_verified']);self.assertFalse(result['zip_contents_extracted'])

    def test_unknown_zip_hash_is_calculated_without_claiming_prior_reference(self):
        item=dict(self.item,expected_sha256=None)
        result=catalog.verify(self.root,item)
        self.assertFalse(result['prior_hash_available']);self.assertIn('sin huella previa',result['reference'])
        self.sidecar();self.assertEqual(catalog.verify(self.root,item)['reference'],'SHA local')

    def test_hash_mismatch_and_wrong_sidecar_filename_block_copy(self):
        self.sidecar('0'*64)
        destination=self.root/'copy.zip'
        with self.assertRaises(ValueError):catalog.copy_to(self.root,self.item,destination)
        self.assertFalse(destination.exists())
        self.sidecar(name='other.zip')
        with self.assertRaises(ValueError):catalog.verify(self.root,self.item)

    def test_existing_destination_and_source_are_never_overwritten(self):
        destination=self.root/'copy.zip';destination.write_bytes(b'KEEP ORIGINAL')
        original=self.zip.read_bytes()
        with self.assertRaises(FileExistsError):catalog.copy_to(self.root,self.item,destination)
        self.assertEqual(destination.read_bytes(),b'KEEP ORIGINAL')
        with self.assertRaises(FileExistsError):catalog.copy_to(self.root,self.item,self.zip)
        self.assertEqual(original,self.zip.read_bytes())

    def test_download_copy_matches_and_does_not_extract(self):
        destination=self.root/'copy.zip'
        result=catalog.copy_to(self.root,self.item,destination)
        self.assertEqual(result['sha256'],self.sha);self.assertEqual(destination.read_bytes(),self.zip.read_bytes())
        self.assertFalse((self.root/'test.txt').exists())

    def test_changed_source_after_verify_removes_only_new_incomplete_copy(self):
        fake=dict(catalog.verify(self.root,self.item),sha256='0'*64)
        destination=self.root/'copy.zip'
        with patch.object(catalog,'verify',return_value=fake),self.assertRaises(ValueError):catalog.copy_to(self.root,self.item,destination)
        self.assertFalse(destination.exists());self.assertTrue(self.zip.exists())

    def test_limits_bad_zip_and_nonzip_destination_are_visible(self):
        with patch.object(catalog,'MAX_ZIP_BYTES',1),self.assertRaises(ValueError):catalog.verify(self.root,self.item)
        with self.assertRaises(ValueError):catalog.copy_to(self.root,self.item,self.root/'danger.exe')
        self.zip.write_text('not a zip')
        with self.assertRaises(ValueError):catalog.verify(self.root,self.item)

    def test_discovery_keeps_known_items_and_marks_new_without_approval(self):
        (self.root/'other.zip').write_bytes(self.zip.read_bytes())
        found=catalog.deliveries(self.root)
        self.assertEqual(len(found['items']),2)
        new=next(x for x in found['items'] if x['path']=='other.zip')
        self.assertEqual(new['state'],'Por clasificar');self.assertIsNone(new['expected_sha256'])
        self.assertFalse(found['discovery_partial'])

    def test_credential_guide_cannot_open_env_or_private_files(self):
        item=dict(self.access,guide='docs/token.env')
        with self.assertRaises(ValueError):catalog.guide(self.root,item)
        item['guide']='.portal_private/credentials.txt'
        with self.assertRaises(ValueError):catalog.guide(self.root,item)

    def test_native_manager_uses_only_fixed_arguments_and_no_shell(self):
        if os.name!='nt':self.skipTest('Native Windows manager launch arguments')
        with patch('subprocess.Popen') as launch:
            catalog.open_manager('windows_vault');args,kwargs=launch.call_args
            self.assertEqual(args[0][-2:],['/name','Microsoft.CredentialManager']);self.assertFalse(kwargs['shell'])
            catalog.open_manager('certificates');self.assertTrue(launch.call_args.args[0][-1].endswith('certmgr.msc'))
            count=launch.call_count
            with self.assertRaises(ValueError):catalog.open_manager('erp_admin')
            self.assertEqual(launch.call_count,count)

    def app(self):
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close);return app

    def test_ui_opens_without_secret_reads_or_manager_launch(self):
        app=self.app()
        with patch('subprocess.Popen',side_effect=AssertionError('explicit action only')),patch('socket.create_connection',side_effect=AssertionError('no network')):
            win=DeliveryAccessWindow(app,self.root);win.withdraw()
            self.assertEqual(len(win.zip_tree.get_children()),1)
            self.assertEqual(len(win.access_tree.get_children()),1)
            win.access_tree.selection_set('A1');win.show_access()
            self.assertIn('no comprobados',win.access_text.get('1.0','end'))
            win.query.set('none');self.assertEqual(win.zip_tree.get_children(),())
            self.assertTrue(win.manager_button.instate(['disabled']))

    def test_ui_download_uses_explicit_save_dialog_and_copies_selected_zip(self):
        app=self.app();win=DeliveryAccessWindow(app,self.root);win.withdraw()
        win.zip_tree.selection_set('Z1');win.show_zip();destination=self.root/'saved.zip'
        with patch('centro.delivery_access_ui.filedialog.asksaveasfilename',return_value=str(destination)):
            win.copy()
        self.assertEqual(destination.read_bytes(),self.zip.read_bytes());self.assertIn('Copia guardada',win.message.get())

    def test_support_report_never_contains_catalog_access_text(self):
        rows=[core.row('cuentas','Private app',detail=self.access['location'])]
        output=json.dumps(core.public_report(rows))
        self.assertNotIn('OS vault',output);self.assertNotIn('Private app',output)

    def test_download_and_access_actions_are_visible_at_user_window_size(self):
        app=self.app();win=DeliveryAccessWindow(app,self.root)
        win.geometry('940x650');win.update()
        self.assertTrue(win.zip_actions.winfo_ismapped())
        self.assertGreater(win.zip_text.winfo_height(),80)
        for button in win.zip_actions.winfo_children():
            self.assertTrue(button.winfo_ismapped())
            self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),win.winfo_rootx()+win.winfo_width())
        notebook=win.access_actions.master.master
        notebook.select(win.access_actions.master);win.update()
        self.assertTrue(win.access_actions.winfo_ismapped())
        self.assertGreater(win.access_text.winfo_height(),80)
