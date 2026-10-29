import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from centro import use_cases
from centro.ui import Center
from centro.use_cases_ui import UseCasesWindow


class UseCasesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.path=self.root/use_cases.RELATIVE;self.path.parent.mkdir(parents=True)
        self.item=dict(id='M1',priority='P1',roles=['Tecnico','Sistemas'],app='Portal',problem='Sin direccion',solution='Confirmar fuente',owner='Producto',status='Propuesta',acceptance='Destino confirmado',source='docs/guide.txt')
        self.save([self.item])

    def save(self,items):self.path.write_text(json.dumps({'schema':'jddc-use-cases/1','items':items}),encoding='utf-8')

    def test_filters_preserve_combined_role_priority_status_and_words(self):
        items=use_cases.load(self.root)
        self.assertEqual(len(use_cases.select(items,role='Tecnico',priority='P1',status='Propuesta',app='Portal',query='DIRECCION fuente')),1)
        for args in ({'role':'Compras'},{'priority':'P0'},{'status':'Implementado local'},{'app':'DEVIA'},{'query':'inexistente'}):
            self.assertEqual(use_cases.select(items,**args),[])

    def test_proposals_never_become_implemented_by_loading(self):
        with patch('socket.create_connection',side_effect=AssertionError('no network')),patch('subprocess.run',side_effect=AssertionError('no commands')):
            self.assertEqual(use_cases.load(self.root)[0]['status'],'Propuesta')

    def test_bad_shapes_statuses_and_duplicates_block_whole_catalog(self):
        mutations=[('roles','Tecnico'),('priority','P9'),('status','COMPLETED'),('source','../private'),('source','C:/private'),('source','/etc/passwd'),('source','https://remote'),('problem',None)]
        for key,value in mutations:
            bad=copy.deepcopy(self.item);bad['id']='M2';bad[key]=value;self.save([self.item,bad])
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):use_cases.load(self.root)
        self.save([self.item,self.item])
        with self.assertRaises(ValueError):use_cases.load(self.root)

    def test_single_invalid_path_is_rejected(self):
        bad=copy.deepcopy(self.item);bad['source']='docs\\outside.txt';self.save([bad])
        with self.assertRaises(ValueError):use_cases.load(self.root)

    def test_ui_filter_and_detail_explain_acceptance_and_clear(self):
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close)
        with patch('socket.create_connection',side_effect=AssertionError('no network')):
            win=UseCasesWindow(app,self.root);win.withdraw();self.addCleanup(win.destroy)
            self.assertEqual(len(win.tree.get_children()),1)
            win.tree.selection_set('M1');win.show_detail()
            self.assertIn('Cierre verificable',win.detail.get('1.0','end'))
            self.assertIn('Propuesta',win.detail.get('1.0','end'))
            win.role.set('Compras');self.assertEqual(win.tree.get_children(),())
            win.clear();self.assertEqual(len(win.tree.get_children()),1)

    def test_ui_missing_catalog_has_safe_message_without_actions(self):
        self.path.unlink()
        app=Center(self.root,autoload=False);app.withdraw();self.addCleanup(app.close)
        win=UseCasesWindow(app,self.root);win.withdraw();self.addCleanup(win.destroy)
        self.assertEqual(win.items,[])
