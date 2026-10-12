import importlib.util,json,pathlib,subprocess,tempfile,unittest
from unittest.mock import patch
p=pathlib.Path(__file__).with_name('rb-seletivo.py');sp=importlib.util.spec_from_file_location('selective_test',p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Inputs(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True)
        for k,v in [('user.email','fixture@example.invalid'),('user.name','Fixture')]:self.g('config',k,v)
        self.write('.dockerignore','.github\nscripts/rb-seletivo.py\ntests\n')
        for c,f in m.FILES.items():
            text='FROM fixture\nCOPY . .\n' if c in ('app','worker') else 'FROM fixture\nCOPY '+('docker/scheduler/entrypoint.sh' if c=='scheduler' else 'integracoes/rb-atacado/coletor/estimativa.py')+' ./\n'
            self.write(f,text)
        for f in ['lib/shared.ts','docker/scheduler/entrypoint.sh','integracoes/rb-atacado/coletor/estimativa.py']:self.write(f,'fixture')
        self.old=self.commit();inputs=m.fingerprints(self.old,self.root)
        self.previous={'schema':2,'revision':self.old,'images':{c:{'revision':self.old,'tag':'rb-1.76.0-'+self.old+'-1-a1','sha256':'a'*64,'image_id':'sha256:'+'b'*64,'inputs':inputs[c]} for c in m.FILES}}
    def g(self,*a):return subprocess.check_output(['git',*a],cwd=self.root,stderr=subprocess.DEVNULL).decode().strip()
    def write(self,p,text):p=self.root/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
    def commit(self):self.g('add','.');self.g('commit','-qm','fixture');return self.g('rev-parse','HEAD')
    def choose(self,force=False):return m.choose(self.g('rev-parse','HEAD'),self.previous,force,self.root)
    def test_unchanged_reuses_four(self):self.assertEqual(self.choose()['build'],[])
    def test_first_release_builds_four(self):self.assertEqual(len(m.choose(self.old,None,root=self.root)['build']),4)
    def test_scheduler_change_also_affects_broad_context(self):
        self.write('docker/scheduler/entrypoint.sh','changed');self.commit();p=self.choose();self.assertEqual({x['name'] for x in p['build']},{'app','worker','scheduler'});self.assertIn('coletor',p['reuse'])
    def test_agent_code_builds_app_worker_only(self):
        self.write('lib/shared.ts','changed');self.commit();self.assertEqual({x['name'] for x in self.choose()['build']},{'app','worker'})
    def test_ignored_pipeline_no_build(self):
        self.write('.github/workflows/test.yml','changed');self.commit();self.assertEqual(self.choose()['build'],[])
    def test_force_rebuild_all(self):self.assertEqual(len(self.choose(True)['build']),4)
    def test_missing_previous_component_refused(self):
        del self.previous['images']['worker']
        with self.assertRaises(ValueError):self.choose()
    def test_tampered_inputs_refused(self):
        self.previous['images']['worker']['inputs']='0'*64
        with self.assertRaisesRegex(ValueError,'inputs_changed'):self.choose()
    def test_other_source_tag_refused(self):
        self.previous['images']['worker']['tag']='rb-1.76.0-'+'c'*40+'-1-a1'
        with self.assertRaisesRegex(ValueError,'provenance'):self.choose()
    def test_deleted_input_changes_identity(self):
        (self.root/'lib/shared.ts').unlink();self.commit();self.assertEqual({x['name'] for x in self.choose()['build']},{'app','worker'})
    def test_unknown_copy_form_conservative(self):
        self.write('Dockerfile.scheduler','FROM fixture\nCOPY ["docker/scheduler/entrypoint.sh", "/entry"]\n');self.commit();p=self.choose();self.assertIn('scheduler',{x['name'] for x in p['build']})
    def test_multiline_copy_includes_each_file(self):
        entries={'Dockerfile.scheduler':('100644','d'),'a':('100644','1'),'b':('100644','2')}
        a=m.digest_entries('scheduler',entries,'COPY a \\\n b ./\n')
        entries['b']=('100644','3');self.assertNotEqual(a,m.digest_entries('scheduler',entries,'COPY a \\\n b ./\n'))
    def test_reused_image_revision_is_not_relabelled(self):
        self.write('lib/shared.ts','changed');new=self.commit();p=self.choose();self.assertNotEqual(p['reuse']['scheduler']['revision'],new)
    def final_fixture(self,plan):
        tag='rb-1.76.0-'+plan['revision']+'-2-a1'
        assets=[{'name':'rb-'+x['name']+suffix} for x in plan['build'] for suffix in m.SUFFIXES]
        release={'draft':True,'target_commitish':plan['revision'],'assets':assets}
        def small(release,name):
            if name.endswith('.sha256'):return ('a'*64+'  '+name.removesuffix('.sha256')+'.tar.gz\n').encode()
            return ('sha256:'+'b'*64+'\n').encode()
        return tag,release,small
    def test_manifest_all_reused_without_new_archives(self):
        plan=self.choose();tag,release,small=self.final_fixture(plan)
        with patch.object(m,'ROOT',self.root),patch.object(m,'request',return_value=release),patch.object(m,'small_asset',side_effect=small):
            manifest=m.finalize(plan,tag)
        self.assertEqual(manifest['images'],self.previous['images'])
    def test_manifest_mixed_revisions(self):
        self.write('lib/shared.ts','changed');new=self.commit();plan=self.choose();tag,release,small=self.final_fixture(plan)
        with patch.object(m,'ROOT',self.root),patch.object(m,'request',return_value=release),patch.object(m,'small_asset',side_effect=small):
            manifest=m.finalize(plan,tag)
        self.assertEqual(manifest['images']['app']['revision'],new);self.assertEqual(manifest['images']['scheduler']['revision'],self.old)
    def test_manifest_requires_draft(self):
        plan=self.choose();tag,release,small=self.final_fixture(plan);release['draft']=False
        with patch.object(m,'request',return_value=release):
            with self.assertRaisesRegex(ValueError,'draft'):m.finalize(plan,tag)
    def test_manifest_requires_exact_assets(self):
        plan=self.choose();tag,release,small=self.final_fixture(plan);release['assets']=[{'name':'unexpected'}]
        with patch.object(m,'request',return_value=release):
            with self.assertRaisesRegex(ValueError,'assets'):m.finalize(plan,tag)
    def test_manifest_changed_inputs_cannot_reuse(self):
        self.write('lib/shared.ts','changed');new=self.commit();bad=dict(self.previous);bad['revision']=new
        with self.assertRaisesRegex(ValueError,'inputs_changed'):m.validate_manifest(bad,self.root)
    def test_invalid_digest_refused(self):
        self.previous['images']['app']['sha256']='invalid'
        with self.assertRaisesRegex(ValueError,'identity'):m.validate_manifest(self.previous,self.root)
if __name__=='__main__':unittest.main()
