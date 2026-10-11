"""Consulta e preparação de orçamento. Não acessa CRM, .env ou WhatsApp."""
import argparse
import ipaddress
import json
import os
import re
import socket
import stat
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
import mega_readonly as mega

MEGA_HOSTS = mega.ALLOWED
FX_HOSTS = {'www.comprasparaguai.com.br', 'comprasparaguai.com.br'}
FX_URL = 'https://www.comprasparaguai.com.br/'
MAX_AGE = timedelta(minutes=15)

class Recusa(ValueError):
    pass

def agora():
    return datetime.now(timezone.utc)

def destino(url, hosts, resolver=socket.getaddrinfo):
    u = urlsplit(url)
    if u.scheme != 'https' or u.hostname not in hosts or u.username or u.password or u.port not in (None, 443):
        raise Recusa('destino_nao_permitido')
    addresses = resolver(u.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise Recusa('destino_nao_publico')
    return url

class Redirecionamentos(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        destino(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def obter(url, hosts, imagem=False):
    destino(url, hosts)
    req = Request(url, headers={'User-Agent':'RBAtacado-Consulta/0.2', 'Accept':'image/*' if imagem else 'text/html'})
    with build_opener(Redirecionamentos(hosts)).open(req, timeout=20) as r:
        destino(r.url, hosts)
        kind = r.headers.get_content_type()
        if imagem and kind not in ('image/jpeg','image/png','image/webp'):
            raise Recusa('imagem_nao_confirmada')
        if not imagem and kind not in ('text/html','application/xhtml+xml'):
            raise Recusa('pagina_nao_confirmada')
        maximum = 4_000_000 if imagem else 3_000_000
        raw = r.read(maximum + 1)
        if len(raw) > maximum:
            raise Recusa('conteudo_acima_limite')
        if imagem:
            valid = ((kind == 'image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or
                     (kind == 'image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or
                     (kind == 'image/webp' and raw[:4] == b'RIFF' and raw[8:12] == b'WEBP'))
            if not valid:
                raise Recusa('imagem_nao_confirmada')
            return raw
        return raw.decode(r.headers.get_content_charset() or 'utf-8')

class Cotacao(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.rates, self.updated = [], [], []
    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get('class','').split())
        # Only balanced container tags need state; void tags do not change ancestry.
        if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:
            self.stack.append((tag,classes))
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
    def handle_data(self, text):
        classes = set().union(*(x[1] for x in self.stack)) if self.stack else set()
        if 'cotacao-real' in classes:
            self.rates.append(text)
        if 'atualizacao-cotacao' in classes:
            self.updated.append(text)

def numero(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d+(?:\.\d{1,6})?',value):
        raise Recusa('numero_nao_confirmado')
    try:
        n=Decimal(value)
    except InvalidOperation:
        raise Recusa('numero_nao_confirmado') from None
    if not n.is_finite() or n <= 0:
        raise Recusa('numero_nao_confirmado')
    return n

def cotacao(document, now=None):
    parser=Cotacao(); parser.feed(document)
    rates=re.findall(r'R\$\s*(\d{1,2},\d{2})',' '.join(parser.rates))
    if len(set(rates)) != 1:
        raise Recusa('cotacao_ausente_ou_ambigua')
    updated=' '.join(parser.updated)
    m=re.search(r'(\d{1,2})\s+de\s+([A-Za-zçÇ]+)\s+de\s+(\d{4})',updated,re.I)
    months={'janeiro':1,'fevereiro':2,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}
    if not m or mega.normalized(m[2]) not in months:
        raise Recusa('data_cotacao_nao_confirmada')
    from zoneinfo import ZoneInfo
    today=(now or agora()).astimezone(ZoneInfo('America/Sao_Paulo')).date()
    from datetime import date
    if date(int(m[3]),months[mega.normalized(m[2])],int(m[1])) != today:
        raise Recusa('cotacao_desatualizada')
    return numero(rates[0].replace(',','.'))

def calcular(custo, base, quantidade):
    if type(quantidade) is not int or not 1 <= quantidade <= 10000:
        raise Recusa('quantidade_invalida')
    unit=(numero(custo)*numero(base)*Decimal('1.05')*Decimal('1.35')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    cents=int(unit*100)
    return cents,cents*quantidade

def fresco(timestamp, now):
    t=datetime.fromisoformat(timestamp)
    if t.tzinfo is None or not timedelta(0) <= now-t <= MAX_AGE:
        raise Recusa('consulta_expirada')

def preparar(url, quantidade, apresentacao, fetch=obter, now=None):
    now=now or agora()
    if urlsplit(url).hostname not in MEGA_HOSTS or not re.fullmatch(r'/producto/\d+/[^/]+/?',urlsplit(url).path) or urlsplit(url).query or urlsplit(url).fragment:
        raise Recusa('anuncio_invalido')
    document=fetch(url,MEGA_HOSTS)
    item=mega.extract(document,url)
    data=mega.primary_data(document,item['codigo'])
    if item['disponibilidade'] != 'disponivel':
        raise Recusa('estoque_indisponivel_ou_nao_confirmado')
    if not item['versao'] or not item['volume_ml'] or len(item['volumes_citados_ml']) != 1:
        raise Recusa('identificacao_precisa_de_confirmacao')
    if apresentacao not in ('frasco','refil','tester','kit'):
        raise Recusa('apresentacao_precisa_de_confirmacao')
    if item['apresentacao'] != 'não confirmada' and item['apresentacao'] != apresentacao:
        raise Recusa('apresentacao_divergente')
    # Require both the main product and its exact JSON-LD offer to agree on USD price.
    schema=mega.structured_product(document,item['codigo'])
    offers=schema.get('offers')
    if not isinstance(offers,dict) or offers.get('priceCurrency') != 'USD':
        raise Recusa('moeda_preco_nao_confirmada')
    cost=numero(data.get('price'))
    if cost != numero(str(offers.get('price',''))):
        raise Recusa('preco_divergente')
    base=cotacao(fetch(FX_URL,FX_HOSTS),now)
    unit,total=calcular(str(cost),str(base),quantidade)
    image_ok=False
    if item['imagem_url']:
        fetch(item['imagem_url'],mega.IMAGE_HOSTS,imagem=True)
        image_ok=True
    item['apresentacao']=apresentacao
    item['imagem_validada']=image_ok
    return {'formato':1,'estado':'pendente_de_aprovacao','produto':item,'quantidade':quantidade,
            'consultado_em_utc':now.isoformat(),'interno':{'custo_usd':str(cost),'cotacao_base':str(base),'fonte_cotacao':FX_URL,
            'preco_unitario_cents':unit,'subtotal_cents':total},'aprovacao':None}

def publico(ticket, now=None):
    now=now or agora()
    p=ticket['produto']
    approved=ticket.get('aprovacao')
    eligible=(ticket['estado']=='aprovado' and isinstance(approved,dict))
    if eligible:
        try:
            fresco(ticket['consultado_em_utc'],now)
            if now >= datetime.fromisoformat(approved['valido_ate_utc']):
                eligible=False
        except (ValueError,TypeError,KeyError):
            eligible=False
    return {'produto':{k:p.get(k) for k in ('codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url','imagem_validada')},
            'quantidade':ticket['quantidade'],'moeda':'BRL','situacao':'aprovado' if eligible else 'pendente_de_consulta_ou_aprovacao',
            'preco_unitario_cents':ticket['interno']['preco_unitario_cents'] if eligible else None,
            'subtotal_cents':ticket['interno']['subtotal_cents'] if eligible else None,
            'quantidade_em_estoque':'nao_informada','disponibilidade_na_consulta':p['disponibilidade'],
            'compra_reserva_pagamento_confirmados':False}

def aprovar(ticket, validade_minutos, consultar=preparar, now=None):
    now=now or agora()
    if type(validade_minutos) is not int or not 1 <= validade_minutos <= 1440:
        raise Recusa('validade_invalida')
    if ticket['estado'] != 'pendente_de_aprovacao':
        raise Recusa('estado_nao_aprovavel')
    fresco(ticket['consultado_em_utc'],now)
    fresh=consultar(ticket['produto']['fonte'],ticket['quantidade'],ticket['produto']['apresentacao'],now=now)
    fields=('codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url')
    if any(ticket['produto'].get(k) != fresh['produto'].get(k) for k in fields) or ticket['interno'] != fresh['interno']:
        raise Recusa('produto_preco_ou_cotacao_mudaram_prepare_novamente')
    fresh['estado']='aprovado'
    fresh['aprovacao']={'aprovado_em_utc':now.isoformat(),'valido_ate_utc':(now+timedelta(minutes=validade_minutos)).isoformat()}
    return fresh

def validar_aprovado(ticket, consultar=preparar, now=None):
    now=now or agora()
    a=ticket.get('aprovacao')
    if ticket.get('estado')!='aprovado' or not isinstance(a,dict):
        raise Recusa('orcamento_nao_aprovado')
    if now >= datetime.fromisoformat(a['valido_ate_utc']):
        raise Recusa('orcamento_expirado')
    fresh=consultar(ticket['produto']['fonte'],ticket['quantidade'],ticket['produto']['apresentacao'],now=now)
    fields=('codigo','nome','marca','versao','variante','volume_ml','apresentacao','imagem_url')
    if any(ticket['produto'].get(k) != fresh['produto'].get(k) for k in fields) or ticket['interno'] != fresh['interno']:
        raise Recusa('produto_preco_ou_cotacao_mudaram_prepare_novamente')
    fresh['estado']='aprovado'; fresh['aprovacao']=dict(a)
    return publico(fresh,now)

def gravar_novo(path, value):
    # Complete private file first; publish atomically without overwriting any receipt.
    import tempfile
    path=Path(path)
    parent=path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise Recusa('diretorio_invalido')
    fd, temporary=tempfile.mkstemp(prefix='.orcamento-',suffix='.tmp',dir=parent)
    try:
        if os.name == 'posix': os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.link(temporary,path)  # Atomic publication, FileExistsError instead of overwrite.
        if os.name == 'posix':
            parent_fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(parent_fd)
            finally: os.close(parent_fd)
    finally:
        os.unlink(temporary)

def ler(path):
    flags=os.O_RDONLY | getattr(os,'O_NOFOLLOW',0)
    fd=os.open(path,flags)
    with os.fdopen(fd,'r',encoding='utf-8') as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or (os.name=='posix' and (stat.S_IMODE(s.st_mode)!=0o600 or s.st_uid!=os.getuid())):
            raise Recusa('arquivo_nao_privado')
        return json.load(f)

def main():
    parser=argparse.ArgumentParser(description='Preparação interna; sem CRM ou WhatsApp.')
    commands=parser.add_subparsers(dest='cmd',required=True)
    s=commands.add_parser('buscar'); s.add_argument('--termo',required=True)
    p=commands.add_parser('preparar'); p.add_argument('--produto',required=True); p.add_argument('--quantidade',type=int,required=True); p.add_argument('--apresentacao',choices=['frasco','refil','tester','kit'],required=True); p.add_argument('--arquivo',required=True)
    a=commands.add_parser('aprovar'); a.add_argument('--arquivo',required=True); a.add_argument('--saida',required=True); a.add_argument('--validade-minutos',type=int,required=True)
    e=commands.add_parser('exibir'); e.add_argument('--arquivo',required=True)
    v=commands.add_parser('validar'); v.add_argument('--arquivo',required=True)
    args=parser.parse_args()
    try:
        if args.cmd=='buscar':
            mega.read_public=lambda url: obter(url,MEGA_HOSTS)
            result=mega.search(args.termo)
            result['detalhes_consultados_integralmente']=result.pop('busca_completa')
            result['cobertura_integral_catalogo']=False
            print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.cmd=='preparar':
            ticket=preparar(args.produto,args.quantidade,args.apresentacao)
            gravar_novo(args.arquivo,ticket)
            print(json.dumps(publico(ticket),ensure_ascii=False,indent=2))
        elif args.cmd=='aprovar':
            if not sys.stdin.isatty(): raise Recusa('aprovacao_exige_terminal_interativo')
            ticket=ler(args.arquivo)
            unit=ticket['interno']['preco_unitario_cents']/100
            total=ticket['interno']['subtotal_cents']/100
            print(json.dumps(publico(ticket),ensure_ascii=False,indent=2))
            print(f"Valor final: R$ {unit:.2f} por unidade; subtotal R$ {total:.2f}.")
            if input('Para aprovar, digite APROVAR: ').strip()!='APROVAR': raise Recusa('aprovacao_cancelada')
            approved=aprovar(ticket,args.validade_minutos)
            gravar_novo(args.saida,approved)
            print(json.dumps(publico(approved),ensure_ascii=False,indent=2))
        elif args.cmd=='validar':
            print(json.dumps(validar_aprovado(ler(args.arquivo)),ensure_ascii=False,indent=2))
        else:
            print(json.dumps(publico(ler(args.arquivo)),ensure_ascii=False,indent=2))
    except Exception as exc:
        reason=str(exc) if isinstance(exc,Recusa) else 'consulta_ou_operacao_nao_confirmada'
        print(json.dumps({'status':'FAIL','motivo':reason},ensure_ascii=False))
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
