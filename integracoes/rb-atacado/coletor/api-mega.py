import socket
"""Private search bridge. No CRM credentials, orders, payments or raw prices."""
import base64,hmac,json,os,re,stat,subprocess,threading,time,unicodedata,importlib.util
from pathlib import Path
import aprovacoes as approvals
import mega_readonly as mega
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
CONFIG='/opt/rb-atacado/config.json'
LOCK=threading.BoundedSemaphore(1)
OPTIONS={}
FIELDS=('fornecedor','codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url','fonte','consultado_em_utc','disponibilidade','quantidade_disponivel','preco_final_aprovado_brl','situacao_preco')

def token_config():
 fd=os.open(CONFIG,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  s=os.fstat(fd)
  if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode)!=0o600 or s.st_size>4096:raise ValueError('configuracao_indisponivel')
  with os.fdopen(fd,'r',closefd=False) as f:c=json.load(f)
  t=c.get('authorization_token')
  if c.get('enabled') is not True or not isinstance(t,str) or not re.fullmatch('[a-f0-9]{64}',t):raise ValueError('configuracao_indisponivel')
  return t
 finally:os.close(fd)

def termo_valido(x):
 return isinstance(x,str) and 2<=len(x)<=120 and any(unicodedata.category(c).startswith('L') for c in x) and not re.search(r'\d{6,}',x) and all(unicodedata.category(c).startswith(('L','N')) or c in " .'-" for c in x)

def buscar(perfume):
 # Model receives projected JSON only. No shell, no inherited Supabase env, no direct fallback.
 r=subprocess.run(['python3','-B','/opt/coletor/consulta-vpn.py','--busca',perfume],capture_output=True,timeout=105,env={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','PYTHONDONTWRITEBYTECODE':'1'})
 if r.returncode or len(r.stdout)>100_000:raise ValueError('consulta_nao_confirmada')
 result=projetar(json.loads(r.stdout))
 now=time.monotonic()
 OPTIONS.clear()
 for item in result['opcoes']:OPTIONS[item['codigo']]=(now,item)
 return result

def projetar(raw):
 if not isinstance(raw,dict) or raw.get('status') not in ('opcoes_disponiveis','sem_estoque_nos_anuncios_verificados','nao_foi_possivel_confirmar'):raise ValueError('consulta_nao_confirmada')
 options=raw.get('opcoes')
 if not isinstance(options,list) or len(options)>20:raise ValueError('consulta_nao_confirmada')
 out=[]
 for x in options:
  if not isinstance(x,dict) or x.get('disponibilidade')!='disponivel':raise ValueError('consulta_nao_confirmada')
  if x.get('preco_final_aprovado_brl') is not None or x.get('quantidade_disponivel') is not None:raise ValueError('consulta_nao_confirmada')
  item={k:x.get(k) for k in FIELDS}
  for key in ('fonte','imagem_url'):
   url=item.get(key)
   if key=='imagem_url' and url is None:continue
   if not isinstance(url,str):raise ValueError('consulta_nao_confirmada')
   u=urlsplit(url)
   if u.scheme!='https' or u.hostname not in ('megaeletronicos.com','www.megaeletronicos.com','resource.megaeletronicos.com') or u.username or u.password or u.port or u.fragment:raise ValueError('consulta_nao_confirmada')
  out.append(item)
 complete=raw.get('detalhes_consultados_integralmente')
 if not isinstance(complete,bool) or (raw['status']=='opcoes_disponiveis')!=bool(out):raise ValueError('consulta_nao_confirmada')
 if raw['status']=='sem_estoque_nos_anuncios_verificados' and not complete:raise ValueError('consulta_nao_confirmada')
 return {'status':raw['status'],'opcoes':out,'cobertura_integral_catalogo':False,'detalhes_consultados_integralmente':complete}

def transporte():
 spec=importlib.util.spec_from_file_location('vpn',Path(__file__).with_name('consulta-vpn.py'))
 mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 return mod.fetch

def orcamento(code,quantity):
 config=approvals.read(CONFIG)
 fetch=transporte()
 consultar=lambda u,q,p,now=None:approvals.o.preparar(u,q,p,fetch=fetch,now=now)
 ledger=approvals.Ledger('/opt/rb-atacado/aprovacoes',config,consultar)
 return ledger.validar(code,quantity)

def foto(code):
 cached=OPTIONS.get(code)
 if not cached or time.monotonic()-cached[0]>120:raise ValueError('foto_requer_consulta_recente')
 old=cached[1];fetch=transporte()
 fresh=mega.extract(fetch(old['fonte'],mega.ALLOWED),old['fonte'])
 if fresh['disponibilidade']!='disponivel' or any(fresh.get(k)!=old.get(k) for k in ('codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url')):raise ValueError('foto_ou_produto_nao_confirmados')
 if not fresh.get('imagem_url'):raise ValueError('foto_nao_confirmada')
 body=fetch(fresh['imagem_url'],mega.IMAGE_HOSTS,imagem=True)
 if body.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
 elif body.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
 elif body[:4]==b'RIFF' and body[8:12]==b'WEBP':mime='image/webp'
 else:raise ValueError('foto_nao_confirmada')
 if len(body)>4_000_000:raise ValueError('foto_nao_confirmada')
 if time.monotonic()-cached[0]>120:raise ValueError('foto_requer_consulta_recente')
 return body,mime

class Handler(BaseHTTPRequestHandler):
 protocol_version='HTTP/1.1'
 def setup(self):
  super().setup();self.connection.settimeout(8)
 def log_message(self,*args):pass
 def reply(self,status,result):
  body=json.dumps(result,ensure_ascii=False).encode()
  self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close');self.end_headers();self.wfile.write(body);self.close_connection=True
 def do_GET(self):
  if self.path!='/health':self.reply(404,{'error':'nao_disponivel'});return
  try:
   token_config()
   import orcamento as o
   o.politica_privada()
   with socket.create_connection(('127.0.0.1',40000),timeout=2):pass
   self.reply(200,{'healthy':True})
  except Exception:self.reply(503,{'healthy':False})

 def do_POST(self):
  if self.path not in ('/v1/buscar','/v1/orcamento','/v1/foto'):return self.reply(404,{'error':'nao_disponivel'})
  try:
   authorization=self.headers.get('Authorization','')
   if len(self.headers.get_all('Authorization',[]))!=1 or not hmac.compare_digest(authorization,'Bearer '+token_config()):return self.reply(403,{'error':'nao_autorizado'})
   if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length',[]))!=1:return self.reply(400,{'error':'consulta_invalida'})
   size=int(self.headers['Content-Length'])
   if not 1<=size<=2048:return self.reply(400,{'error':'consulta_invalida'})
   data=json.loads(self.rfile.read(size))
   if not isinstance(data,dict):return self.reply(400,{'error':'consulta_invalida'})
   if self.path=='/v1/buscar':
    valid=set(data)=={'perfume'} and termo_valido(data['perfume'])
   elif self.path=='/v1/orcamento':
    valid=set(data)=={'codigo','quantidade'} and isinstance(data['codigo'],str) and bool(re.fullmatch(r'\d{1,12}',data['codigo'])) and type(data['quantidade']) is int and 1<=data['quantidade']<=1000
   else:
    valid=set(data)=={'codigo'} and isinstance(data['codigo'],str) and bool(re.fullmatch(r'\d{1,12}',data['codigo']))
   if not valid:return self.reply(400,{'error':'consulta_invalida'})
  except Exception:return self.reply(400,{'error':'consulta_invalida'})
  if not LOCK.acquire(blocking=False):return self.reply(429,{'error':'consulta_ocupada'})
  try:
   if self.path=='/v1/buscar':self.reply(200,buscar(data['perfume']))
   elif self.path=='/v1/orcamento':self.reply(200,orcamento(data['codigo'],data['quantidade']))
   else:
    body,mime=foto(data['codigo'])
    metadata={k:OPTIONS[data['codigo']][1].get(k) for k in ('codigo','nome','marca','versao','variante','volume_ml','apresentacao')}
    label=base64.b64encode(json.dumps(metadata,ensure_ascii=False).encode()).decode('ascii')
    self.send_response(200);self.send_header('X-RB-Produto',label);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close');self.end_headers();self.wfile.write(body);self.close_connection=True
  except Exception:self.reply(503,{'error':'consulta_nao_confirmada'})
  finally:LOCK.release()

class Server(ThreadingHTTPServer):
 # ThreadingHTTPServer otherwise allocates unbounded client threads.
 daemon_threads=True
 def __init__(self,*args,**kwargs):
  self.slots=threading.BoundedSemaphore(8);super().__init__(*args,**kwargs)
 def process_request(self,request,address):
  if not self.slots.acquire(blocking=False):request.close();return
  try:super().process_request(request,address)
  except BaseException:self.slots.release();raise
 def process_request_thread(self,request,address):
  try:super().process_request_thread(request,address)
  finally:self.slots.release()

if __name__=='__main__':
 # Private Docker namespace only; no host-port publication permitted.
 os.umask(0o077)
 try:
  token_config()
  import orcamento as o
  o.politica_privada()
 except Exception:raise SystemExit('configuracao_indisponivel')
 Server(('0.0.0.0',40100),Handler).serve_forever()
