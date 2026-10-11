"""SSH operator wizard. No real quote is approved merely by preparing this file."""
import importlib.util,json,os,sys
from pathlib import Path
import aprovacoes as a

def main():
 if not sys.stdin.isatty() or not sys.stdout.isatty():raise a.Recusa('terminal_interativo_obrigatorio')
 os.umask(0o077)
 config=a.read('/opt/rb-atacado/config.json')
 spec=importlib.util.spec_from_file_location('vpn',Path(__file__).with_name('consulta-vpn.py'))
 vpn=importlib.util.module_from_spec(spec);spec.loader.exec_module(vpn)
 consultar=lambda url,q,p,now=None:a.o.preparar(url,q,p,fetch=vpn.fetch,now=now)
 ledger=a.Ledger('/opt/rb-atacado/aprovacoes',config,consultar)
 action=input('PREPARAR, APROVAR ou REVOGAR: ').strip()
 if action=='PREPARAR':
  url=input('Link exato do perfume na Mega: ').strip();qty=int(input('Quantidade: '));presentation=input('Apresentação confirmada (frasco/refil/tester/kit): ').strip()
  ref,preview=ledger.preparar(url,qty,presentation);print(json.dumps(preview,ensure_ascii=False));print('Referência interna do rascunho: '+ref)
 elif action=='APROVAR':
  ref=input('Referência interna do rascunho: ').strip();a.uuid.UUID(ref);minutes=int(input('Validade em minutos (1–1440): '))
  record=a.read(Path('/opt/rb-atacado/aprovacoes')/('pendente-'+ref+'.json'))
  if record.get('scope')!=a.scope(config):raise a.Recusa('fora_do_teste')
  ticket=record['ticket']
  print(json.dumps({'produto':ticket['produto']['nome'],'quantidade':ticket['quantidade'],'moeda':'BRL','preco_unitario_cents':ticket['interno']['preco_unitario_cents'],'subtotal_cents':ticket['interno']['subtotal_cents']},ensure_ascii=False))
  if input('Esta aprovação é exclusiva do contato de teste. Digite APROVAR: ')!='APROVAR':raise a.Recusa('aprovacao_cancelada')
  print(json.dumps(ledger.aprovar(ref,minutes),ensure_ascii=False))
 elif action=='REVOGAR':
  code=input('Código do produto na Mega: ').strip();qty=int(input('Quantidade: '))
  if input('Digite REVOGAR: ')!='REVOGAR':raise a.Recusa('revogacao_cancelada')
  print(json.dumps(ledger.revogar(code,qty)))
 else:raise a.Recusa('acao_invalida')
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (Exception,KeyboardInterrupt):
  print('Operação não concluída. Nenhum detalhe privado será exibido.');raise SystemExit(1)
