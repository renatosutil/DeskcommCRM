import unittest,runpy,os,json,io,contextlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).parent
FILES=('ci.yml','e2e.yml','perf.yml','publish-image.yml','rb-release.yml')
def valid():
 return [{'head_sha':'a'*40,'event':'pull_request','path':'.github/workflows/'+f,'id':i,'run_attempt':1,
  'updated_at':'2026-10-11T00:00:00Z','status':'completed','conclusion':'success'} for i,f in enumerate(FILES,1)]
def execute(runs,repo='renatosutil/DeskcommCRM',offline=False):
 env={'REPOSITORIO':repo,'REVISAO':'a'*40,'GH_TOKEN':'fixture-non-production'}
 response=io.BytesIO(json.dumps({'workflow_runs':runs}).encode())
 out=io.StringIO()
 with patch.dict(os.environ,env,clear=True),patch('urllib.request.urlopen',side_effect=OSError() if offline else None,return_value=response),contextlib.redirect_stdout(out):
  runpy.run_path(str(ROOT/'rb-verificar-ci.py'),run_name='__main__')
 return out.getvalue()
class Test(unittest.TestCase):
 def test_complete_same_commit(self):self.assertIn('PASS',execute(valid()))
 def test_missing(self):
  with self.assertRaises(SystemExit):execute(valid()[:-1])
 def test_failed(self):
  a=valid();a[0]['conclusion']='failure'
  with self.assertRaises(SystemExit):execute(a)
 def test_queued(self):
  a=valid();a[0]['status']='queued';a[0]['conclusion']=None
  with self.assertRaises(SystemExit):execute(a)
 def test_other_sha(self):
  a=valid();a[0]['head_sha']='b'*40
  with self.assertRaises(SystemExit):execute(a)
 def test_push_does_not_substitute_pr(self):
  a=valid();a[0]['event']='push'
  with self.assertRaises(SystemExit):execute(a)
 def test_latest_failed_rerun_blocks_previous_pass(self):
  a=valid();r={**a[0],'run_attempt':2,'updated_at':'2026-10-11T01:00:00Z','conclusion':'failure'};a.append(r)
  with self.assertRaises(SystemExit):execute(a)
 def test_error_never_allows(self):
  with self.assertRaises(SystemExit):execute(valid(),offline=True)
 def test_other_repository(self):
  with self.assertRaises(SystemExit):execute(valid(),repo='fixture/other')
if __name__=='__main__':unittest.main()
