from decimal import Decimal
import copy,json,os,tempfile,unittest,uuid
from datetime import datetime,timezone,timedelta
from pathlib import Path
import aprovacoes as a
class Test(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.path.chmod(0o700)
  self.config={'enabled':True,'organization_id':'11111111-1111-4111-8111-111111111111','contact_id':'22222222-2222-4222-8222-222222222222'}
  self.now=datetime(2026,10,11,20,tzinfo=timezone.utc);self.cost='10';self.rate='5';self.calls=0;self.stock=True;self.hook=None
  def consultar(url,q,p,now=None):
   self.calls+=1
   if not self.stock:raise a.o.Recusa('estoque_indisponivel_ou_nao_confirmado')
   if self.hook:self.hook()
   u,t=a.o.calcular(self.cost,self.rate,q,politica=(Decimal('1.02'),Decimal('1.20')))
   return {'formato':1,'estado':'pendente_de_aprovacao','produto':{'codigo':'123','nome':'Perfume teste EDT 100 ml','marca':'Marca','versao':'EDT','variante':None,'volume_ml':100,'apresentacao':p,'fonte':url,'imagem_url':'https://resource.megaeletronicos.com/teste.webp','imagem_validada':True,'disponibilidade':'disponivel'},'quantidade':q,'consultado_em_utc':now.isoformat(),'interno':{'custo_usd':self.cost,'cotacao_base':self.rate,'fonte_cotacao':'fonte_publica','preco_unitario_cents':u,'subtotal_cents':t},'aprovacao':None}
  self.consultar=consultar;self.ledger=a.Ledger(self.path,self.config,consultar,lambda:self.now)
  self.url='https://www.megaeletronicos.com/producto/123/perfume-teste'
 def tearDown(self):self.tmp.cleanup()
 def prepare(self):return self.ledger.preparar(self.url,2,'frasco')[0]
 def approve(self):ref=self.prepare();self.ledger.aprovar(ref,60);return ref
 def test_quote_requires_approval(self):
  self.prepare()
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_unit_rounding_then_subtotal(self):
  self.approve();v=self.ledger.validar('123',2);self.assertEqual(v['preco_unitario_cents'],6120);self.assertEqual(v['subtotal_cents'],12240)
 def test_output_hides_cost_rate_markup(self):
  self.approve();v=json.dumps(self.ledger.validar('123',2));self.assertNotIn('custo',v);self.assertNotIn('cotacao',v);self.assertNotIn('interno',v);self.assertNotIn('percentual',v)
 def test_different_quantity_not_authorized(self):
  self.approve();calls=self.calls
  with self.assertRaises(Exception):self.ledger.validar('123',1)
  self.assertEqual(self.calls,calls)
 def test_different_product_not_authorized(self):
  self.approve();calls=self.calls
  with self.assertRaises(Exception):self.ledger.validar('124',2)
  self.assertEqual(self.calls,calls)
 def test_other_tenant_rejected(self):
  self.approve();other={**self.config,'organization_id':'33333333-3333-4333-8333-333333333333'};x=a.Ledger(self.path,other,self.consultar,lambda:self.now)
  with self.assertRaises(a.Recusa):x.validar('123',2)
 def test_other_contact_rejected(self):
  self.approve();other={**self.config,'contact_id':'33333333-3333-4333-8333-333333333333'};x=a.Ledger(self.path,other,self.consultar,lambda:self.now)
  with self.assertRaises(a.Recusa):x.validar('123',2)
 def test_expired_no_query(self):
  self.approve();self.now+=timedelta(minutes=60);calls=self.calls
  with self.assertRaises(Exception):self.ledger.validar('123',2)
  self.assertEqual(self.calls,calls)
 def test_price_change_rejected(self):
  self.approve();self.cost='11'
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_exchange_change_rejected(self):
  self.approve();self.rate='6'
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_unavailable_rejected(self):
  self.approve();self.stock=False
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_revoke_no_query(self):
  self.approve();self.ledger.revogar('123',2);calls=self.calls
  with self.assertRaises(a.Recusa):self.ledger.validar('123',2)
  self.assertEqual(self.calls,calls)
 def test_revoke_during_remote_read(self):
  self.approve();self.hook=lambda:self.ledger.revogar('123',2)
  with self.assertRaises(a.Recusa):self.ledger.validar('123',2)
 def test_expire_during_remote_read(self):
  self.approve();self.hook=lambda:setattr(self,'now',self.now+timedelta(minutes=61))
  with self.assertRaises(a.Recusa):self.ledger.validar('123',2)
 def test_pending_cannot_approve_twice(self):
  ref=self.approve()
  with self.assertRaises(a.Recusa):self.ledger.aprovar(ref,60)
 def test_backup_and_record_are_private(self):
  self.approve();self.approve();self.assertTrue(list(self.path.glob('historico-*.json')))
  for p in self.path.iterdir():self.assertEqual(p.stat().st_mode&0o777,0o600)
 def test_symlink_rejected(self):
  self.approve();target=self.path/a.key('123',2);data=a.read(target);target.unlink();other=self.path/'outro.json';a.o.gravar_novo(other,data);target.symlink_to(other)
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_expiry_is_not_extended(self):
  self.approve();self.now+=timedelta(minutes=59);self.ledger.validar('123',2);self.now+=timedelta(minutes=1)
  with self.assertRaises(Exception):self.ledger.validar('123',2)
 def test_price_changed_before_approval(self):
  ref=self.prepare();self.cost='11'
  with self.assertRaises(Exception):self.ledger.aprovar(ref,60)
  self.assertFalse(list(self.path.glob('ativo-*.json')))
 def test_default_purchase_not_confirmed(self):
  self.approve();self.assertFalse(self.ledger.validar('123',2)['compra_reserva_pagamento_confirmados'])
if __name__=='__main__':unittest.main()
