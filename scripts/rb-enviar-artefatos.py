"""Upload repetível somente para rascunho da própria revisão; nunca imprime token/log cru."""
import hashlib,json,os,pathlib,re,subprocess,time

def enviar(env=None,run=subprocess.run,sleep=time.sleep,root=pathlib.Path('/tmp')):
    env=os.environ if env is None else env
    component=env['COMPONENTE'];revision=env['REVISAO'];tag=env['TAG_RB']
    if component not in ('app','worker','scheduler','coletor') or not re.fullmatch(r'[a-f0-9]{40}',revision):
        raise ValueError('configuracao')
    if not re.fullmatch(r'rb-1\.76\.0-'+revision+r'-[0-9]+-a[0-9]+',tag):
        raise ValueError('configuracao')
    files=[root/('rb-'+component+s) for s in ('.tar.gz','.sha256','.image-id')]
    if any(not p.is_file() or p.is_symlink() for p in files):raise ValueError('artefato')
    if not 0<files[0].stat().st_size<2*1024**3:raise ValueError('limite_artefato')
    with files[0].open('rb') as source: digest=hashlib.file_digest(source,'sha256').hexdigest()
    if files[1].read_text().strip()!=digest+'  '+files[0].name:raise ValueError('checksum')
    if not re.fullmatch(r'sha256:[a-f0-9]{64}\n?',files[2].read_text()):raise ValueError('identidade')
    for attempt in range(3):
        # Revalida a condição antes de cada tentativa; --clobber só é permitido em draft próprio.
        result=run(['gh','release','view',tag,'--json','isDraft,targetCommitish,tagName'],capture_output=True,text=True)
        if result.returncode:raise ValueError('consulta_release')
        data=json.loads(result.stdout)
        if data.get('isDraft') is not True or data.get('targetCommitish')!=revision or data.get('tagName')!=tag:
            raise ValueError('release_nao_autorizada')
        result=run(['gh','release','upload',tag,*map(str,files),'--clobber'],capture_output=True,text=True)
        if result.returncode==0:return
        if attempt<2:sleep(10*(attempt+1))
    raise ValueError('upload')

if __name__=='__main__':
    try:
        enviar()
        print('PASS: artefatos enviados ao rascunho verificado.')
    except (ValueError,KeyError,OSError,json.JSONDecodeError):
        raise SystemExit('FAIL: upload protegido não concluiu; release permanece em rascunho.')
