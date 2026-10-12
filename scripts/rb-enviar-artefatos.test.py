import hashlib,importlib.util,json,pathlib,subprocess,tempfile,unittest
p=pathlib.Path(__file__).with_name('rb-enviar-artefatos.py')
spec=importlib.util.spec_from_file_location('upload',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class UploadTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
        self.sha='a'*40;self.tag='rb-1.76.0-'+self.sha+'-123-a1'
        self.env={'COMPONENTE':'worker','REVISAO':self.sha,'TAG_RB':self.tag}
        archive=self.root/'rb-worker.tar.gz';archive.write_bytes(b'synthetic-oci')
        (self.root/'rb-worker.sha256').write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
        (self.root/'rb-worker.image-id').write_text('sha256:'+'b'*64+'\n')
        self.calls=[];self.waits=[];self.failures=0;self.draft=True;self.target=self.sha
    def fake_run(self,cmd,**kwargs):
        self.calls.append(cmd)
        if cmd[2]=='view':return subprocess.CompletedProcess(cmd,0,json.dumps({'isDraft':self.draft,'targetCommitish':self.target,'tagName':self.tag}),'')
        if self.failures:self.failures-=1;return subprocess.CompletedProcess(cmd,1,'','synthetic-error')
        return subprocess.CompletedProcess(cmd,0,'','')
    def invoke(self):m.enviar(self.env,self.fake_run,self.waits.append,self.root)
    def test_success(self):self.invoke();self.assertEqual(len(self.calls),2);self.assertIn('--clobber',self.calls[-1])
    def test_partial_upload_retry(self):self.failures=1;self.invoke();self.assertEqual(len(self.calls),4);self.assertEqual(self.waits,[10])
    def test_three_attempts_only(self):
        self.failures=9
        with self.assertRaisesRegex(ValueError,'upload'):self.invoke()
        self.assertEqual(len(self.calls),6);self.assertEqual(self.waits,[10,20])
    def test_published_release_never_modified(self):
        self.draft=False
        with self.assertRaisesRegex(ValueError,'release_nao_autorizada'):self.invoke()
        self.assertEqual(len(self.calls),1)
    def test_other_revision_never_modified(self):
        self.target='c'*40
        with self.assertRaisesRegex(ValueError,'release_nao_autorizada'):self.invoke()
        self.assertEqual(len(self.calls),1)
    def test_bad_checksum_no_network(self):
        (self.root/'rb-worker.sha256').write_text('incorrect')
        with self.assertRaisesRegex(ValueError,'checksum'):self.invoke()
        self.assertEqual(self.calls,[])
    def test_bad_tag_no_network(self):
        self.env['TAG_RB']='stable'
        with self.assertRaisesRegex(ValueError,'configuracao'):self.invoke()
        self.assertEqual(self.calls,[])
if __name__=='__main__':unittest.main()
