import json,os,urllib.request,re
required={'.github/workflows/'+x for x in ('ci.yml','e2e.yml','perf.yml','publish-image.yml','rb-release.yml')}
try:
 repo=os.environ['REPOSITORIO'];sha=os.environ['REVISAO']
 if repo!='renatosutil/DeskcommCRM' or not re.fullmatch('[a-f0-9]{40}',sha):raise ValueError()
 req=urllib.request.Request('https://api.github.com/repos/'+repo+'/actions/runs?head_sha='+sha+'&event=pull_request&per_page=100',
  headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(req,timeout=30) as r:runs=json.load(r)['workflow_runs']
 latest={}
 for run in runs:
  if run['head_sha']==sha and run['event']=='pull_request' and run['path'] in required:
   previous=latest.get(run['path'])
   if previous is None or (run.get('updated_at',''),run['id'],run['run_attempt'])>(previous.get('updated_at',''),previous['id'],previous['run_attempt']):latest[run['path']]=run
 if set(latest)!=required or any(r['status']!='completed' or r['conclusion']!='success' for r in latest.values()):raise ValueError()
 print('PASS: CI completo do mesmo commit.')
except Exception:
 raise SystemExit('FAIL: CI completo do mesmo commit ainda não foi aprovado.')
