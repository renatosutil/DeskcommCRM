"""Implantação por imagem verificada. Não modifica env, banco, proxy ou volumes."""
import argparse,datetime,hashlib,importlib.util,json,os,pathlib,re,subprocess,time,urllib.request
sp=importlib.util.spec_from_file_location('selective',pathlib.Path(__file__).with_name('rb-seletivo.py'));s=importlib.util.module_from_spec(sp);sp.loader.exec_module(s)
APP=pathlib.Path('/home/ubuntu/deskcommcrm');STAGE=APP/'preparacao/implantacao-rb-20261011T234433Z';VPN=APP/'preparacao/teste-warp-20261011T195136Z'
NAMES={'app':'deskcommcrm-app-1','worker':'deskcommcrm-worker-1','scheduler':'deskcommcrm-scheduler-1','coletor':'deskcommcrm-mega-api'}
ACTIVE_REVISION=None
PRESERVE=['cobranca_caddy','cobranca_n8n','cobranca_evolution','cobranca_redis','cobranca_postgres','cobranca_evolution_postgres','deskcommcrm-redis-1','deskcommcrm-waha-1','deskcommcrm-srh-1','deskcommcrm-mega-vpn']

def run(cmd,env=None):
    if cmd[:2]==['docker','compose']:
        if not ACTIVE_REVISION:raise RuntimeError('revisao')
        env=os.environ.copy() if env is None else dict(env)
        env['RB_IMAGE_REVISION']=ACTIVE_REVISION
    p=subprocess.run(cmd,capture_output=True,text=True,env=env)
    if p.returncode:raise RuntimeError('comando')
    return p.stdout

def state(n):return json.loads(run(['docker','inspect','--format','{"container":{{json .Id}},"image":{{json .Config.Image}},"id":{{json .Image}},"running":{{json .State.Running}},"oom":{{json .State.OOMKilled}},"restarts":{{.RestartCount}},"health":{{with index .State "Health"}}{{json .Status}}{{else}}"SEM_HEALTHCHECK"{{end}}}',n]))
def good(x):return x['running'] and not x['oom'] and x['restarts']==0 and x['health'] in ('healthy','SEM_HEALTHCHECK')
def available():return int(next(x.split()[1] for x in pathlib.Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
def resources():
    if available()<400*1024 or not all(good(state(n)) for n in PRESERVE[:6]):raise RuntimeError('recursos_ou_cobranca')
def wait(n):
    end=time.monotonic()+180
    while time.monotonic()<end:
        resources();x=state(n)
        if x['oom'] or x['restarts'] or not x['running']:raise RuntimeError('servico')
        if good(x):return
        time.sleep(3)
    raise RuntimeError('health_timeout')

def full_ci(sha):
    runs=s.request('actions/runs?head_sha='+s.revision(sha)+'&event=pull_request&per_page=100')['workflow_runs'];latest={}
    required={'.github/workflows/'+n for n in ('ci.yml','e2e.yml','perf.yml','publish-image.yml','rb-release.yml')}
    for x in runs:
        if x['head_sha']==sha and x['event']=='pull_request' and x['path'] in required:
            old=latest.get(x['path'])
            if old is None or (x.get('updated_at',''),x['id'],x['run_attempt'])>(old.get('updated_at',''),old['id'],old['run_attempt']):latest[x['path']]=x
    if set(latest)!=required or any(x['status']!='completed' or x['conclusion']!='success' for x in latest.values()):raise RuntimeError('ci_nao_aprovado')

def new_json(p,obj):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(obj,f);f.write('\n');f.flush();os.fsync(f.fileno())
def unique_dir():
    p=STAGE/('seletiva-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));p.mkdir(mode=0o700);return p

def checksum(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def verify_identity(path,image,expected_id):
 import tarfile
 if not re.fullmatch(r"sha256:[a-f0-9]{64}",expected_id):raise RuntimeError("identidade")
 selected=run(["docker","image","inspect",image,"--format",'{"id":{{json .Id}},"labels":{{json .Config.Labels}},"rootfs":{{json .RootFS}},"descriptor":{{json .Descriptor}}}'])
 actual=json.loads(selected)
 def blob(t,digest):
  if not re.fullmatch(r"sha256:[a-f0-9]{64}",digest):raise RuntimeError("identidade")
  data=t.get("blobs/sha256/"+digest.split(":")[1])
  if data is None:raise RuntimeError("identidade")
  if "sha256:"+hashlib.sha256(data).hexdigest()!=digest:raise RuntimeError("identidade")
  return json.loads(data)
 wanted={"manifest.json","index.json","blobs/sha256/"+expected_id.split(":")[1],"blobs/sha256/"+actual["id"].split(":")[1]}
 objects={}
 with tarfile.open(path,"r|gz") as archive:
  for member in archive:
   if member.name in wanted:
    if not member.isfile() or member.size>4*1024*1024 or member.name in objects:raise RuntimeError("identidade")
    objects[member.name]=archive.extractfile(member).read()
 t=objects
 config=blob(t,expected_id)
 manifests=json.loads(t["manifest.json"])
 if len(manifests)!=1 or image not in manifests[0]["RepoTags"] or manifests[0]["Config"]!="blobs/sha256/"+expected_id.split(":")[1]:raise RuntimeError("identidade")
 if config.get("architecture")!="amd64" or config.get("os")!="linux":raise RuntimeError("identidade")
 if actual["labels"]!=config["config"].get("Labels",{}) or actual["rootfs"].get("Layers")!=config["rootfs"].get("diff_ids"):raise RuntimeError("identidade")
 if actual["id"]!=expected_id:
  index=json.loads(t["index.json"])
  matches=[d for d in index["manifests"] if d["digest"]==actual["id"]]
  if len(matches)!=1 or actual.get("descriptor",{}).get("digest")!=actual["id"]:raise RuntimeError("identidade")
  manifest=blob(t,actual["id"])
  if manifest.get("config",{}).get("digest")!=expected_id:raise RuntimeError("identidade")
 return actual["id"],actual["labels"]

def changed(before,targets):return [c for c in ('coletor','app','worker','scheduler') if before[c]['id']!=targets[c]['id']]
def compose(c,override):
    if c=='coletor':return ['docker','compose','-p','deskcommcrm-megaprecos','--project-directory',str(VPN),'-f',str(VPN/'compose.vpn.yaml'),'-f',str(STAGE/'compose.api.yaml'),'-f',str(override)]
    cmd=['docker','compose','-p','deskcommcrm','--project-directory',str(APP)]
    for p in ('docker-compose.prod.yml','docker-compose.npm.yml','docker-compose.supabase-ca.yml'):cmd+=['-f',str(APP/p)]
    return cmd+['-f',str(STAGE/'compose.rb.yaml'),'-f',str(override)]
def overrides(folder,images):
    files={}
    for group in (['app','worker','scheduler'],['coletor']):
        p=folder/('images-'+group[0]+'.yaml');fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('services:\n')
            for c in group:
                image=images[c]['image']
                if not re.fullmatch(r'[a-zA-Z0-9_./:-]+',image):raise RuntimeError('imagem')
                f.write('  '+('api' if c=='coletor' else c)+':\n    image: '+json.dumps(image)+'\n');files[c]=p
    return files

def apply_changes(components,files,execute=run,check=wait):
    for c in components:
        execute(compose(c,files[c])+['up','-d','--no-deps','api' if c=='coletor' else c]);check(NAMES[c])

def paused_agent():
    raw=run(['python3','-B',str(STAGE/'agente-nativo.py'),'inspecionar'])
    lines=[x for x in raw.splitlines() if x.startswith('{')]
    if len(lines)!=1:raise RuntimeError('agente')
    x=json.loads(lines[0])
    if not x.get('ok') or not x.get('paused') or not x.get('restriction'):raise RuntimeError('agente_deve_estar_pausado_e_restrito')

def download(tag):
    sha=s.tag_revision(tag);full_ci(sha)
    release=s.request('releases/tags/'+tag);m=s.release_manifest(release)
    for old in set(x['revision'] for x in m['images'].values()):full_ci(old)
    folder=unique_dir();images={}
    for c,x in m['images'].items():
        image='deskcommcrm-rb-'+c+':'+x['revision'];archive=None
        for prior in STAGE.glob('imagens-ci*.json'):
            try:
                receipt=json.loads(prior.read_text());candidate=pathlib.Path(receipt['folder'])/('rb-'+c+'.tar.gz')
                if receipt['tag']==x['tag'] and candidate.resolve().is_relative_to(STAGE.resolve()) and candidate.is_file() and not candidate.is_symlink() and checksum(candidate)==x['sha256']:archive=candidate;break
            except (KeyError,OSError,ValueError):continue
        if archive is None:
            src=s.request('releases/tags/'+x['tag'])
            if src['draft'] or not src['prerelease']:raise RuntimeError('origem')
            url='https://github.com/'+s.REPO+'/releases/download/'+x['tag']+'/rb-'+c+'.tar.gz'
            if not any(a['name']=='rb-'+c+'.tar.gz' and a['browser_download_url']==url for a in src['assets']):raise RuntimeError('origem')
            archive=folder/('rb-'+c+'.tar.gz');fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as out,urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'RB-Atacado-Selective'}),timeout=120) as inp:
                while True:
                    chunk=inp.read(1024*1024)
                    if not chunk:break
                    out.write(chunk)
            if checksum(archive)!=x['sha256']:raise RuntimeError('checksum')
        run(['gzip','-t',str(archive)])
        if subprocess.run(['docker','image','inspect',image],capture_output=True).returncode:run(['docker','load','--input',str(archive)])
        ident,labels=verify_identity(archive,image,x['image_id'])
        if labels.get('org.opencontainers.image.revision')!=x['revision'] or labels.get('org.opencontainers.image.version')!='1.76.0-rb' or labels.get('org.opencontainers.image.source')!='https://github.com/'+s.REPO:raise RuntimeError('identidade')
        images[c]={'image':image,'id':ident,'revision':x['revision']};print(c+' IMAGEM_VERIFICADA',flush=True)
    receipt=folder/'verified.json';new_json(receipt,{'schema':2,'manifest':m,'images':images});print('RECIBO '+str(receipt),flush=True)

def deploy(receipt_path,dry=False):
    global ACTIVE_REVISION
    receipt=json.loads(receipt_path.read_text());m=s.validate_manifest(receipt['manifest']);full_ci(m['revision']);ACTIVE_REVISION=m['revision']
    if set(receipt['images'])!=set(NAMES):raise RuntimeError('recibo')
    for c,x in receipt['images'].items():
        if x['image']!='deskcommcrm-rb-'+c+':'+m['images'][c]['revision']:raise RuntimeError('recibo')
        if run(['docker','image','inspect',x['image'],'--format','{{.Id}}']).strip()!=x['id']:raise RuntimeError('identidade')
    before={c:state(n) for c,n in NAMES.items()};components=changed(before,receipt['images'])
    print('SERVICOS_A_TROCAR '+','.join(components),flush=True)
    if dry:return
    if not components:return
    paused_agent();resources()
    if APP.joinpath('.env').stat().st_mode&0o777!=0o600:raise RuntimeError('env_permissao')
    if not all(good(x) for x in before.values()):raise RuntimeError('servico_previo')
    preserved={n:state(n)['container'] for n in PRESERVE}
    folder=unique_dir();files=overrides(folder,receipt['images']);session=folder/'before.json'
    new_json(session,{'schema':2,'before':before,'components':components,'preserved':preserved,'manifest':m,'overrides':{c:str(p) for c,p in files.items()}})
    print('ROLLBACK_RECIBO '+str(session),flush=True)
    for c in components:run(compose(c,files[c])+['config','--quiet'])
    apply_changes(components,files)
    if any(state(n)['container']!=ident for n,ident in preserved.items()):raise RuntimeError('servico_preservado')
    if any(state(NAMES[c])['container']!=before[c]['container'] for c in NAMES if c not in components):raise RuntimeError('servico_nao_alterado')
    resources();print('IMPLANTACAO_SELETIVA_PASS',flush=True)

def rollback(path):
    global ACTIVE_REVISION
    record=json.loads(path.read_text())
    if record.get('schema')!=2 or not set(record['components'])<=set(NAMES) or len(record['components'])!=len(set(record['components'])) or set(record['before'])!=set(NAMES):raise RuntimeError('rollback_recibo')
    ACTIVE_REVISION=s.revision(record['manifest']['revision'])
    paused_agent();resources()
    for c in record['components']:
        x=record['before'][c]
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_./:-]*',x['image']):raise RuntimeError('rollback_imagem')
        if run(['docker','image','inspect',x['image'],'--format','{{.Id}}']).strip()!=x['id']:raise RuntimeError('rollback_imagem')
    files=overrides(unique_dir(),record['before'])
    for c in record['components']:run(compose(c,files[c])+['config','--quiet'])
    apply_changes(record['components'],files)
    if any(state(n)['container']!=ident for n,ident in record['preserved'].items()):raise RuntimeError('servico_preservado')
    print('ROLLBACK_SELETIVO_PASS_AGENTE_CONTINUA_PAUSADO',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['baixar','planejar','implantar','rollback']);ap.add_argument('--tag');ap.add_argument('--recibo',type=pathlib.Path);ap.add_argument('--repo',type=pathlib.Path,required=True);args=ap.parse_args();s.ROOT=args.repo
    try:
        if args.action=='baixar':download(args.tag)
        else:
            if not args.recibo or not args.recibo.resolve().is_relative_to(STAGE.resolve()) or args.recibo.is_symlink():raise RuntimeError('recibo')
            if args.action=='rollback':rollback(args.recibo)
            else:deploy(args.recibo,args.action=='planejar')
    except Exception:
        raise SystemExit('FAIL: etapa seletiva interrompida; agente deve permanecer pausado; sem correção automática.')
