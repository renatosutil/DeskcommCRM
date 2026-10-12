"""Manifesto público de imagens seletivas. Credenciais de CI só em memória, nunca em logs."""
import argparse,hashlib,json,os,pathlib,re,shlex,subprocess,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
REPO='renatosutil/DeskcommCRM'
FILES={'app':'Dockerfile','worker':'Dockerfile.worker','scheduler':'Dockerfile.scheduler','coletor':'integracoes/rb-atacado/Dockerfile.coletor'}
SUFFIXES=('.tar.gz','.sha256','.image-id')

def git(*args,root=None):return subprocess.check_output(['git',*args],cwd=root or ROOT,stderr=subprocess.DEVNULL)
def revision(s):
    if not re.fullmatch('[a-f0-9]{40}',s):raise ValueError('revision')
    return s

def tag_revision(tag):
    m=re.fullmatch(r'rb-1\.76\.0-([a-f0-9]{40})-[0-9]+-a[0-9]+',tag)
    if not m:raise ValueError('tag')
    return m[1]

def ancestor(old,new,root=None):return subprocess.run(['git','merge-base','--is-ancestor',old,new],cwd=root or ROOT,capture_output=True).returncode==0

def tree(sha,root=None):
    out={}
    for row in git('ls-tree','-r','-z',revision(sha),root=root).split(b'\0'):
        if not row:continue
        meta,name=row.split(b'\t',1);mode,kind,blob=meta.decode().split()
        if kind!='blob':raise ValueError('unsupported_git_entry')
        out[name.decode()]=(mode,blob)
    return out

def source(sha,path,root=None):return git('show',revision(sha)+':'+path,root=root).decode()

def digest_entries(component,entries,dockerfile,ignore='',specific_ignore=None):
    # Conservador: só exclui padrões literais comprovados. Globs/negações nunca escondem entrada.
    rules=[]
    if not any(l.strip().startswith('!') for l in ignore.splitlines()):
        rules=[l.strip().strip('/') for l in ignore.splitlines() if l.strip() and not l.lstrip().startswith('#') and not any(x in l for x in '*?[]!')]
    def excluded(path):return any(path==p or path.startswith(p+'/') for p in rules)
    text=dockerfile.replace('\\\n',' ');sources=[];broad=False
    for line in text.splitlines():
        m=re.match(r'^\s*(COPY|ADD)\s+(.+)$',line,re.I)
        if not m:continue
        words=shlex.split(m[2])
        if any(w.startswith('--from=') for w in words):continue
        if m[1].upper()=='ADD' or any(w.startswith('--') for w in words) or len(words)<2:
            broad=True;continue
        for p in words[:-1]:
            p=p.removeprefix('./').rstrip('/')
            if p in ('.','') or any(c in p for c in '*?[]$') or p.startswith('/') or '..' in pathlib.PurePosixPath(p).parts:broad=True
            else:sources.append(p)
    if '--mount=' in text or any(v[0]=='120000' for v in entries.values()):broad=True
    selected={p:v for p,v in entries.items() if (broad or any(p==s or p.startswith(s+'/') for s in sources)) and not excluded(p)}
    selected[FILES[component]]=entries[FILES[component]]
    # Context filter affects COPY . only; explicit COPY inputs are independently fingerprinted.
    if broad:
        for p in ('.dockerignore',specific_ignore):
            if p and p in entries:selected[p]=entries[p]
    payload={'algorithm':1,'component':component,'version':'1.76.0','entries':sorted((p,*v) for p,v in selected.items())}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def fingerprints(sha,root=None):
    entries=tree(sha,root);out={}
    for c,f in FILES.items():
        special=f+'.dockerignore'
        ignore_path=special if special in entries else '.dockerignore'
        ignore=source(sha,ignore_path,root) if ignore_path in entries else ''
        out[c]=digest_entries(c,entries,source(sha,f,root),ignore,special if special in entries else None)
    return out

def request(path):
    headers={'User-Agent':'RB-Atacado-Selective','Accept':'application/vnd.github+json'}
    if os.environ.get('GH_TOKEN'):headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers=headers),timeout=30) as r:return json.load(r)

def small_asset(release,name):
    matches=[a for a in release['assets'] if a['name']==name]
    if len(matches)!=1 or matches[0]['size']>65536:raise ValueError('asset')
    a=matches[0]
    if release['draft']:
        p=subprocess.run(['gh','api','repos/'+REPO+'/releases/assets/'+str(a['id']),'-H','Accept: application/octet-stream'],capture_output=True)
        if p.returncode:raise ValueError('asset_read')
        return p.stdout
    expected='https://github.com/'+REPO+'/releases/download/'+release['tag_name']+'/'+name
    if a['browser_download_url']!=expected:raise ValueError('asset_origin')
    with urllib.request.urlopen(urllib.request.Request(expected,headers={'User-Agent':'RB-Atacado-Selective'}),timeout=60) as r:return r.read(65537)

def validate_manifest(m,root=None):
    if m.get('schema')!=2 or set(m.get('images',{}))!=set(FILES):raise ValueError('manifest')
    sha=revision(m['revision']);expected=fingerprints(sha,root)
    for c,x in m['images'].items():
        old=revision(x['revision'])
        if tag_revision(x['tag'])!=old or not ancestor(old,sha,root):raise ValueError('provenance')
        if not re.fullmatch('[a-f0-9]{64}',x['sha256']) or not re.fullmatch('sha256:[a-f0-9]{64}',x['image_id']):raise ValueError('identity')
        if x['inputs']!=expected[c] or fingerprints(old,root)[c]!=expected[c]:raise ValueError('inputs_changed')
    return m

def release_manifest(release,root=None):
    if release['draft'] or not release['prerelease']:raise ValueError('release')
    sha=tag_revision(release['tag_name'])
    if any(a['name']=='rb-release.json' for a in release['assets']):
        m=json.loads(small_asset(release,'rb-release.json'))
        if m['revision']!=sha:raise ValueError('release_revision')
        return validate_manifest(m,root)
    if set(a['name'] for a in release['assets'])!={'rb-'+c+s for c in FILES for s in SUFFIXES}:raise ValueError('legacy_assets')
    inputs=fingerprints(sha,root);images={}
    for c in FILES:
        checksum=small_asset(release,'rb-'+c+'.sha256').decode().split()
        if len(checksum)!=2 or checksum[1]!='rb-'+c+'.tar.gz':raise ValueError('checksum')
        images[c]={'revision':sha,'tag':release['tag_name'],'sha256':checksum[0],'image_id':small_asset(release,'rb-'+c+'.image-id').decode().strip(),'inputs':inputs[c]}
    return validate_manifest({'schema':2,'revision':sha,'images':images},root)

def choose(sha,previous=None,force=False,root=None):
    sha=revision(sha);inputs=fingerprints(sha,root);reuse={};build=[]
    if previous:validate_manifest(previous,root)
    for c,f in FILES.items():
        x=(previous or {}).get('images',{}).get(c)
        if x and not force and ancestor(x['revision'],sha,root) and x['inputs']==inputs[c]:reuse[c]=x
        else:build.append({'name':c,'file':f})
    return {'revision':sha,'inputs':inputs,'reuse':reuse,'build':build}

def plan_current():
    sha=revision(os.environ['REVISAO']);previous=None
    releases=request('releases?per_page=100')
    candidates=[x for x in releases if not x['draft'] and x['tag_name'].startswith('rb-1.76.0-')]
    for x in sorted(candidates,key=lambda x:x.get('published_at') or '',reverse=True):
        old=tag_revision(x['tag_name'])
        if ancestor(old,sha):previous=release_manifest(x);break
    return choose(sha,previous,os.environ.get('RB_FORCE_REBUILD')=='true')

def finalize(plan,tag):
    sha=revision(plan['revision'])
    if tag_revision(tag)!=sha:raise ValueError('tag')
    release=request('releases/tags/'+tag)
    if not release['draft'] or release['target_commitish']!=sha:raise ValueError('draft')
    names={a['name'] for a in release['assets']}
    expected={'rb-'+x['name']+s for x in plan['build'] for s in SUFFIXES}
    if names not in (expected,expected|{'rb-release.json'}):raise ValueError('assets')
    images=dict(plan['reuse'])
    for x in plan['build']:
        c=x['name'];checksum=small_asset(release,'rb-'+c+'.sha256').decode().split()
        if len(checksum)!=2 or checksum[1]!='rb-'+c+'.tar.gz':raise ValueError('checksum')
        images[c]={'revision':sha,'tag':tag,'sha256':checksum[0],'image_id':small_asset(release,'rb-'+c+'.image-id').decode().strip(),'inputs':plan['inputs'][c]}
    return validate_manifest({'schema':2,'revision':sha,'images':images})

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['plan','finalize']);args=ap.parse_args()
    try:
        if args.action=='plan':
            plan=plan_current()
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:
                f.write('plan='+json.dumps(plan,separators=(',',':'))+'\n')
                f.write('matrix='+json.dumps({'include':plan['build']},separators=(',',':'))+'\n')
                f.write('build_required='+str(bool(plan['build'])).lower()+'\n')
            print('PASS: construir '+','.join(x['name'] for x in plan['build'])+'; reaproveitar '+','.join(plan['reuse']))
        else:
            m=finalize(json.loads(os.environ['RB_PLAN']),os.environ['TAG_RB'])
            pathlib.Path('/tmp/rb-release.json').write_text(json.dumps(m,sort_keys=True)+'\n')
            print('PASS: manifesto verificado, quatro componentes rastreáveis.')
    except Exception:
        raise SystemExit('FAIL: publicação seletiva recusada; sem deploy.')
