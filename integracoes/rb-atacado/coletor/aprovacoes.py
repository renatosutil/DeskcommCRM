"""Private, operator-approved quotes for exactly one configured test contact."""
import fcntl,json,os,re,stat,tempfile,uuid
from pathlib import Path
from datetime import datetime,timezone
import orcamento as o

class Recusa(Exception):pass

def scope(config):
 if config.get('enabled') is not True:raise Recusa('configuracao_indisponivel')
 try:
  for key in ('organization_id','contact_id'):uuid.UUID(config[key])
 except Exception:raise Recusa('configuracao_indisponivel')
 return {key:config[key] for key in ('organization_id','contact_id')}

def read(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 with os.fdopen(fd,'r') as f:
  s=os.fstat(f.fileno())
  if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o600 or s.st_uid!=os.getuid() or s.st_size>65536:raise Recusa('arquivo_nao_privado')
  return json.load(f)

def directory(path):
 p=Path(path)
 s=p.lstat()
 if not stat.S_ISDIR(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o700 or s.st_uid!=os.getuid():raise Recusa('diretorio_nao_privado')
 return p

def key(code,qty):
 if not isinstance(code,str) or not re.fullmatch(r'\d{1,12}',code) or type(qty) is not int or not 1<=qty<=1000:raise Recusa('produto_ou_quantidade_invalidos')
 return 'ativo-'+code+'-'+str(qty)+'.json'

def _replace(path,value):
 fd,tmp=tempfile.mkstemp(prefix='.ativo-',dir=path.parent)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'w') as f:json.dump(value,f);f.write('\n');f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
  fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 finally:
  try:os.unlink(tmp)
  except FileNotFoundError:pass

class Ledger:
 def __init__(self,folder,config,consultar,clock=lambda:datetime.now(timezone.utc)):
  self.folder=directory(folder);self.config=scope(config);self.consultar=consultar;self.clock=clock
 def _lock(self):
  fd=os.open(self.folder/'.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
  s=os.fstat(fd)
  if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o600 or s.st_uid!=os.getuid():os.close(fd);raise Recusa('arquivo_nao_privado')
  fcntl.flock(fd,fcntl.LOCK_EX);return fd
 def _ref(self,code,qty):
  v=read(self.folder/key(code,qty))
  if v.get('scope')!=self.config:raise Recusa('fora_do_teste')
  if v.get('ref') is None:raise Recusa('aprovacao_revogada')
  try:uuid.UUID(v['ref'])
  except Exception:raise Recusa('aprovacao_invalida')
  return v['ref']
 def preparar(self,url,qty,presentation):
  ticket=self.consultar(url,qty,presentation,now=self.clock())
  key(ticket['produto']['codigo'],qty)
  ref=str(uuid.uuid4())
  o.gravar_novo(self.folder/('pendente-'+ref+'.json'),{'scope':self.config,'ticket':ticket})
  # The pending retail preview is for the operator, never the model/customer.
  return ref,{'produto':ticket['produto']['nome'],'quantidade':qty,'moeda':'BRL','preco_unitario_cents':ticket['interno']['preco_unitario_cents'],'subtotal_cents':ticket['interno']['subtotal_cents'],'aprovado':False}
 def aprovar(self,ref,minutes):
  try:uuid.UUID(ref)
  except Exception:raise Recusa('aprovacao_invalida')
  record=read(self.folder/('pendente-'+ref+'.json'))
  if record.get('scope')!=self.config:raise Recusa('fora_do_teste')
  approved=o.aprovar(record['ticket'],minutes,consultar=self.consultar,now=self.clock())
  if self.clock()>=datetime.fromisoformat(approved['aprovacao']['valido_ate_utc']):raise Recusa('aprovacao_expirada')
  code=approved['produto']['codigo'];qty=approved['quantidade'];name=key(code,qty)
  fd=self._lock()
  try:
   marker=self.folder/('aprovado-de-'+ref+'.json')
   if marker.exists():raise Recusa('pendente_ja_aprovado')
   approval=str(uuid.uuid4())
   o.gravar_novo(self.folder/('aprovado-'+approval+'.json'),{'scope':self.config,'ticket':approved})
   target=self.folder/name
   if target.exists():o.gravar_novo(self.folder/('historico-'+str(uuid.uuid4())+'.json'),read(target))
   o.gravar_novo(marker,{'scope':self.config,'ref':approval})
   _replace(target,{'scope':self.config,'ref':approval})
  finally:os.close(fd)
  return {'aprovado':True,'quantidade':qty,'moeda':'BRL','preco_unitario_cents':approved['interno']['preco_unitario_cents'],'subtotal_cents':approved['interno']['subtotal_cents'],'valido_ate_utc':approved['aprovacao']['valido_ate_utc']}
 def validar(self,code,qty):
  ref=self._ref(code,qty)
  record=read(self.folder/('aprovado-'+ref+'.json'))
  if record.get('scope')!=self.config:raise Recusa('fora_do_teste')
  t=record['ticket']
  if t.get('quantidade')!=qty or t.get('produto',{}).get('codigo')!=code:raise Recusa('produto_ou_quantidade_divergentes')
  fresh=o.validar_aprovado(t,consultar=self.consultar,now=self.clock())
  # A revoke/replacement during remote I/O cannot authorize the old price.
  if self._ref(code,qty)!=ref:raise Recusa('aprovacao_alterada')
  if self.clock()>=datetime.fromisoformat(t['aprovacao']['valido_ate_utc']):raise Recusa('aprovacao_expirada')
  if fresh.get('situacao')!='aprovado' or type(fresh.get('preco_unitario_cents')) is not int or fresh.get('subtotal_cents')!=fresh['preco_unitario_cents']*qty:raise Recusa('orcamento_nao_confirmado')
  fresh['valido_ate_utc']=t['aprovacao']['valido_ate_utc']
  return fresh
 def revogar(self,code,qty):
  fd=self._lock()
  try:
   target=self.folder/key(code,qty);previous=read(target)
   if previous.get('scope')!=self.config:raise Recusa('fora_do_teste')
   o.gravar_novo(self.folder/('historico-'+str(uuid.uuid4())+'.json'),previous)
   _replace(target,{'scope':self.config,'ref':None})
  finally:os.close(fd)
  return {'revogado':True}
