import importlib.util,pathlib,subprocess,unittest
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('rb-ciclo-rapido.py')
s=importlib.util.spec_from_file_location('fast',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FastTest(unittest.TestCase):
    def test_changes_include_staged_and_tracked_worktree(self):
        with patch.object(m.subprocess,'check_output',side_effect=['a'*40+'\n',b'edge/crm/send-message.ts\0']) as call:
            self.assertEqual(m.changed('fixture-base'),['edge/crm/send-message.ts'])
            self.assertNotIn('HEAD',call.call_args.args[0])
    def test_missing_base_is_failure(self):
        with patch.object(m.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,['git'])):
            with self.assertRaises(subprocess.CalledProcessError):m.changed('fixture-base')
    def test_docs_no_build(self):self.assertEqual(m.planejar(['docs/a.md'])['commands'],[])
    def test_price_tests_only_python(self):
        p=m.planejar(['integracoes/rb-atacado/coletor/estimativa.py'])
        self.assertEqual(len(p['commands']),4);self.assertFalse(p['needs_node'])
    def test_delivery_includes_contact_and_photo(self):
        p=m.planejar(['lib/mcp/tools/rb-atacado/entrega.ts'])
        self.assertIn('tests/unit/rb-foto.test.ts',p['commands'][0]);self.assertIn('tests/unit/rb-elegibilidade-confirmada.test.ts',p['commands'][0])
    def test_transport_includes_native_guards(self):
        p=m.planejar(['edge/crm/send-message.ts'])
        self.assertIn('tests/unit/opt-out-deteccao.test.ts',p['commands'][0]);self.assertTrue(p['requires_expanded_review'])
    def test_unknown_never_silent(self):
        p=m.planejar(['lib/unknown.ts'])
        self.assertIn(['pnpm','test:unit'],p['commands']);self.assertTrue(p['requires_expanded_review'])
    def test_database_needs_expanded_review(self):self.assertTrue(m.planejar(['supabase/baseline.sql'])['requires_expanded_review'])
    def test_pipeline_includes_structural_contracts(self):
        p=m.planejar(['.github/workflows/rb-rapido.yml'])
        self.assertTrue(p['needs_node']);self.assertEqual(len(p['commands']),len(m.PIPELINE_TESTS)+2)
    def test_never_publishes(self):
        for paths in [[],['lib/unknown.ts'],['edge/crm/send-message.ts']]:self.assertFalse(m.planejar(paths)['publication_authorized'])
    def test_no_build_up_or_external_connection_commands(self):
        p=m.planejar(['edge/crm/send-message.ts','integracoes/rb-atacado/coletor/api-mega.py'])
        self.assertTrue(all(c[0] in ('pnpm','python3') for c in p['commands']))
    def test_runner_stops_on_first_failure(self):
        calls=[]
        def run(cmd,**kw):calls.append(cmd);return subprocess.CompletedProcess(cmd,1)
        with self.assertRaises(SystemExit):m.execute({'commands':[['fixture1'],['fixture2']]},run)
        self.assertEqual(len(calls),1)
    def test_deletion_covered_by_path(self):self.assertTrue(m.planejar(['lib/mcp/tools/rb-atacado/provas.ts'])['needs_node'])
    def test_test_phase_does_not_repeat_typecheck(self):
        calls=[]
        def run(cmd,**kw):calls.append(cmd);return subprocess.CompletedProcess(cmd,0)
        m.execute({'commands':[['python3','fixture.py'],['pnpm','typecheck']]},run,fase='testes')
        self.assertEqual(calls,[['python3','fixture.py']])
    def test_type_phase_only_checks_types(self):
        calls=[]
        def run(cmd,**kw):calls.append(cmd);return subprocess.CompletedProcess(cmd,0)
        m.execute({'commands':[['python3','fixture.py'],['pnpm','typecheck']]},run,fase='tipos')
        self.assertEqual(calls,[['pnpm','typecheck']])
if __name__=='__main__':unittest.main()
