import importlib.util,pathlib,tempfile,unittest,json
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('rb-implantar-seletivo.py');sp=importlib.util.spec_from_file_location('deploy_test',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Deploy(unittest.TestCase):
    def test_equal_ids_no_restart(self):
        a={c:{'id':c} for c in m.NAMES};self.assertEqual(m.changed(a,a),[])
    def test_only_changed_image_selected(self):
        a={c:{'id':c} for c in m.NAMES};b={c:dict(x) for c,x in a.items()};b['worker']['id']='changed';self.assertEqual(m.changed(a,b),['worker'])
    def test_dependency_order(self):
        a={c:{'id':'old'} for c in m.NAMES};b={c:{'id':'new'} for c in m.NAMES};self.assertEqual(m.changed(a,b),['coletor','app','worker','scheduler'])
    def test_up_only_requested_service_no_billing(self):
        calls=[];checks=[];m.apply_changes(['worker'],{'worker':pathlib.Path('/fixture/override.yaml')},lambda c:calls.append(c),checks.append)
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][-4:],['up','-d','--no-deps','worker']);self.assertEqual(checks,['deskcommcrm-worker-1'])
        self.assertNotIn('cobranca',str(calls))
    def test_failed_service_stops_remaining(self):
        calls=[]
        def fail(n):raise RuntimeError('fixture')
        with self.assertRaises(RuntimeError):m.apply_changes(['app','worker'],{c:pathlib.Path('/fixture') for c in m.NAMES},lambda c:calls.append(c),fail)
        self.assertEqual(len(calls),1)
    def test_overrides_preserve_all_image_revisions(self):
        with tempfile.TemporaryDirectory() as d:
            images={c:{'image':'deskcommcrm-rb-'+c+':'+'a'*40} for c in m.NAMES};f=m.overrides(pathlib.Path(d),images)
            self.assertEqual(f['app'],f['worker']);self.assertIn(images['scheduler']['image'],f['app'].read_text());self.assertEqual(f['app'].stat().st_mode&0o777,0o600)
    def test_rollback_targets_only_session_changes(self):
        with tempfile.TemporaryDirectory() as d:
            before={c:{'image':'deskcommcrm-rb-'+c+':'+'a'*40,'id':'fixture-id'} for c in m.NAMES}
            record={'schema':2,'before':before,'components':['worker'],'preserved':{'cobranca_caddy':'same'},'manifest':{'revision':'a'*40}}
            p=pathlib.Path(d)/'before.json';p.write_text(json.dumps(record))
            with patch.object(m,'paused_agent'),patch.object(m,'resources'),patch.object(m,'run',return_value='fixture-id'),patch.object(m,'unique_dir',return_value=pathlib.Path(d)),patch.object(m,'state',return_value={'container':'same'}),patch.object(m,'apply_changes') as apply:
                m.rollback(p);self.assertEqual(apply.call_args.args[0],['worker'])
    def test_rollback_requires_paused_agent(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'before.json';p.write_text(json.dumps({'schema':2,'components':['worker'],'before':{c:{} for c in m.NAMES},'manifest':{'revision':'a'*40}}))
            with patch.object(m,'paused_agent',side_effect=RuntimeError('paused')),patch.object(m,'apply_changes') as apply:
                with self.assertRaises(RuntimeError):m.rollback(p)
                apply.assert_not_called()
if __name__=='__main__':unittest.main()
