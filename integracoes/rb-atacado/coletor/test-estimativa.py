import unittest,json
from unittest.mock import patch
from datetime import datetime,timezone
from decimal import Decimal
import estimativa as e
class Test(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,12,16,tzinfo=timezone.utc)
  self.item={'codigo':'123','nome':'Perfume teste EDT 100 ml','marca':'Marca','versao':'EDT','variante':None,'volume_ml':100,'apresentacao':'não confirmada','imagem_url':'https://resource.megaeletronicos.com/teste.webp','disponibilidade':'disponivel'}
  self.data={'price':'10'};self.offers={'priceCurrency':'USD','price':'10'}
  self.fx='<div class="cotacao-real">R$ 5,00</div><div class="atualizacao-cotacao">12 de outubro de 2026</div>'
 def quote(self,q=None):
  with patch.object(e.mega,'extract',return_value=self.item),patch.object(e.mega,'primary_data',return_value=self.data),patch.object(e.mega,'structured_product',return_value={'offers':self.offers}):
   return e.preparar('https://www.megaeletronicos.com/producto/123/perfume-teste',q,fetch=lambda u,h:self.fx if u==e.o.FX_URL else 'fixture',now=self.now,politica=(Decimal('1.02'),Decimal('1.20')))
 def test_unit_without_customer_quantity(self):
  x=self.quote();self.assertEqual(x['preco_unitario_cents'],6120);self.assertIsNone(x['quantidade']);self.assertIsNone(x['subtotal_cents']);self.assertEqual(x['situacao'],'estimativa')
 def test_quantity_is_only_subtotal(self):
  x=self.quote(10);self.assertEqual(x['subtotal_cents'],61200);self.assertEqual(x['quantidade_em_estoque'],'nao_informada')
 def test_no_owner_approval_or_purchase(self):
  x=self.quote(2);self.assertTrue(x['fechamento_pendente_aprovacao']);self.assertFalse(x['compra_reserva_pagamento_confirmados'])
 def test_no_private_pricing_output(self):
  text=json.dumps(self.quote())
  for key in ['custo_usd','cotacao_base','fx_multiplier','sale_multiplier','interno']:self.assertNotIn(key,text)
 def test_out_of_stock_refused(self):
  self.item['disponibilidade']='indisponivel'
  with self.assertRaises(e.o.Recusa):self.quote()
 def test_conflicting_price_refused(self):
  self.offers['price']='11'
  with self.assertRaises(e.o.Recusa):self.quote()
 def test_non_usd_refused(self):
  self.offers['priceCurrency']='BRL'
  with self.assertRaises(e.o.Recusa):self.quote()
 def test_previous_day_rate_refused(self):
  self.fx=self.fx.replace('12 de outubro','11 de outubro')
  with self.assertRaises(e.o.Recusa):self.quote()
 def test_quantity_not_invented_from_stock(self):
  self.item['stock']=1000
  self.assertIsNone(self.quote()['quantidade'])
 def test_bad_quantities_refused(self):
  for q in [0,-1,True,1.5,1001]:
   with self.subTest(q=q):
    with self.assertRaises(e.o.Recusa):self.quote(q)
if __name__=='__main__':unittest.main()
