"""Public sources over the container-local WARP proxy; no direct fallback."""
import argparse,json,subprocess
from urllib.parse import urljoin
import orcamento as o
import mega_readonly as mega

def fetch(url,hosts,imagem=False):
 maximum=4_000_000 if imagem else 3_000_000
 for hop in range(4):
  o.destino(url,hosts)
  r=subprocess.run(['curl','--silent','--show-error','--include','--proto','=https','--max-time','25','--max-filesize',str(maximum),'--proxy','socks5h://127.0.0.1:40000','--noproxy','','--user-agent','RBAtacado-Consulta/0.3',url],capture_output=True,timeout=30)
  if r.returncode:raise o.Recusa('consulta_vpn_nao_confirmada')
  header,sep,body=r.stdout.partition(b'\r\n\r\n')
  if not sep:raise o.Recusa('resposta_nao_confirmada')
  lines=header.decode('iso-8859-1').splitlines()
  status=int(lines[0].split()[1])
  headers={k.strip().lower():v.strip() for k,v in (line.split(':',1) for line in lines[1:] if ':' in line)}
  if status in (301,302,303,307,308):
   if 'location' not in headers:raise o.Recusa('redirecionamento_nao_confirmado')
   url=urljoin(url,headers['location']);continue
  if status!=200:raise o.Recusa('http_fonte_'+str(status))
  if len(body)>maximum:raise o.Recusa('conteudo_acima_limite')
  kind=headers.get('content-type','').split(';')[0].strip().lower()
  if imagem:
   valid=((kind=='image/jpeg' and body.startswith(b'\xff\xd8\xff')) or (kind=='image/png' and body.startswith(b'\x89PNG\r\n\x1a\n')) or (kind=='image/webp' and body[:4]==b'RIFF' and body[8:12]==b'WEBP'))
   if not valid:raise o.Recusa('imagem_nao_confirmada')
   return body
  if kind not in ('text/html','application/xhtml+xml'):raise o.Recusa('pagina_nao_confirmada')
  return body.decode('utf-8')
 raise o.Recusa('redirecionamentos_acima_limite')

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--busca')
 p.add_argument('--teste-orcamento',action='store_true')
 a=p.parse_args()
 try:
  if a.teste_orcamento:
   t=o.preparar('https://www.megaeletronicos.com/producto/966375/perfume-masculino-christian-dior-sauvage-edt-100-ml',2,'frasco',fetch=fetch)
   print(json.dumps({'teste':'PASS','fontes':'Mega_e_Compras_Paraguai','imagem_validada':t['produto']['imagem_validada'],'preco_pendente_oculto':o.publico(t)['preco_unitario_cents'] is None,'aprovado':False,'WhatsApp_enviado':False}))
  elif a.busca:
   mega.read_public=lambda url:fetch(url,o.MEGA_HOSTS)
   result=mega.search(a.busca)
   result['detalhes_consultados_integralmente']=result.pop('busca_completa')
   result['cobertura_integral_catalogo']=False
   print(json.dumps(result,ensure_ascii=False))
  else:raise o.Recusa('escolha_busca_ou_teste')
 except Exception as e:
  print(json.dumps({'teste':'FAIL','motivo':str(e) if isinstance(e,o.Recusa) else 'consulta_nao_confirmada'}))
  return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
