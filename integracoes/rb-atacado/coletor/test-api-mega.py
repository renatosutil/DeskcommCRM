import importlib.util,json,threading,unittest,urllib.request,urllib.error
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('bridge',__import__('pathlib').Path(__file__).with_name('api-mega.py'))
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
TOKEN='a'*64
ITEM={'fornecedor':'Mega Eletrônicos','codigo':'123','nome':'Perfume teste','marca':'Marca','versao':'EDT','variante':None,'volume_ml':100,'apresentacao':'não confirmada','imagem_url':'https://resource.megaeletronicos.com/teste.webp','fonte':'https://www.megaeletronicos.com/producto/123/teste','consultado_em_utc':'2026-10-11T20:00:00Z','disponibilidade':'disponivel','quantidade_disponivel':None,'preco_final_aprovado_brl':None,'situacao_preco':'pendente_de_consulta_e_aprovacao'}
RAW={'status':'opcoes_disponiveis','opcoes':[ITEM],'detalhes_consultados_integralmente':True}
class Test(unittest.TestCase):
 def setUp(self):
  self.server=a.Server(('127.0.0.1',0),a.Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.url='http://127.0.0.1:'+str(self.server.server_port)+'/v1/buscar'
  self.p=patch.object(a,'token_config',return_value=TOKEN);self.p.start()
  self.original_buscar=a.buscar
  self.b=patch.object(a,'buscar',return_value=a.projetar(RAW));self.mock=self.b.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.b.stop();self.p.stop()
 def request(self,data,token=TOKEN):
  req=urllib.request.Request(self.url,data=json.dumps(data).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(req,timeout=5) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_allowed(self):self.assertEqual(self.request({'perfume':'Sauvage'})[0],200);self.mock.assert_called_once_with('Sauvage')
 def test_bad_auth_no_query(self):self.assertEqual(self.request({'perfume':'Sauvage'},'wrong')[0],403);self.mock.assert_not_called()
 def test_no_extra_fields(self):self.assertEqual(self.request({'perfume':'Sauvage','contact':'private'})[0],400);self.mock.assert_not_called()
 def test_personal_data(self):
  for p in ['user@example.invalid','+55 99 99999-9999','http://example.invalid','123456789']:
   self.assertEqual(self.request({'perfume':p})[0],400)
  self.mock.assert_not_called()
 def test_private_error(self):
  self.mock.side_effect=ValueError('private detail')
  status,r=self.request({'perfume':'Sauvage'});self.assertEqual(status,503);self.assertNotIn('private detail',json.dumps(r))
 def test_busy(self):
  a.LOCK.acquire()
  try:self.assertEqual(self.request({'perfume':'Sauvage'})[0],429);self.mock.assert_not_called()
  finally:a.LOCK.release()
 def test_prices_removed(self):
  r=a.projetar({**RAW,'custo':85,'html':'raw page','opcoes':[{**ITEM,'custo_usd':85}]});s=json.dumps(r)
  self.assertNotIn('custo',s);self.assertNotIn('raw page',s)
 def test_unapproved_price_rejected(self):
  with self.assertRaises(ValueError):a.projetar({**RAW,'opcoes':[{**ITEM,'preco_final_aprovado_brl':100}]})
 def test_false_stock_rejected(self):
  with self.assertRaises(ValueError):a.projetar({**RAW,'opcoes':[{**ITEM,'disponibilidade':'indisponivel'}]})
 def test_external_url_rejected(self):
  with self.assertRaises(ValueError):a.projetar({**RAW,'opcoes':[{**ITEM,'imagem_url':'https://example.invalid/image.jpg'}]})
 def test_incomplete_stock_claim_rejected(self):
  with self.assertRaises(ValueError):a.projetar({'status':'sem_estoque_nos_anuncios_verificados','opcoes':[],'detalhes_consultados_integralmente':False})
 def test_subprocess_no_shell_no_credentials(self):
  with patch.object(a.subprocess,'run',return_value=__import__('subprocess').CompletedProcess([],0,json.dumps(RAW).encode(),b'')) as m:
   self.original_buscar('Sauvage');args,kw=m.call_args;self.assertIsInstance(args[0],list);self.assertFalse(kw.get('shell',False));self.assertNotIn('SUPABASE_SERVICE_ROLE_KEY',kw['env']);self.assertNotIn('OWNER_PASSWORD',kw['env'])
class Extra(unittest.TestCase):
 request=Test.request
 def setUp(self):
  Test.setUp(self);self.cache=a.OPTIONS.copy();a.OPTIONS.clear()
 def tearDown(self):
  a.OPTIONS.clear();a.OPTIONS.update(self.cache);Test.tearDown(self)
 def request_route(self,path,data,token=TOKEN):
  original=self.url;self.url=self.url.replace('/v1/buscar',path)
  try:return self.request(data,token)
  finally:self.url=original
 def fixture(self,body=b'\xff\xd8\xfftest'):
  a.OPTIONS['123']=(a.time.monotonic(),dict(ITEM));calls=[]
  def fetch(url,hosts,imagem=False):calls.append((url,imagem));return body if imagem else 'html only in fixture'
  return fetch,calls
 def test_photo_unknown_code_no_network(self):
  with patch.object(a,'transporte') as t:
   with self.assertRaises(ValueError):a.foto('999')
   t.assert_not_called()
 def test_photo_expired_no_network(self):
  a.OPTIONS['123']=(a.time.monotonic()-121,dict(ITEM))
  with patch.object(a,'transporte') as t:
   with self.assertRaises(ValueError):a.foto('123')
   t.assert_not_called()
 def test_original_photo_verified(self):
  fetch,calls=self.fixture()
  with patch.object(a,'transporte',return_value=fetch),patch.object(a.mega,'extract',return_value=dict(ITEM)):
   body,mime=a.foto('123');self.assertEqual(mime,'image/jpeg');self.assertTrue(body.startswith(b'\xff\xd8\xff'));self.assertEqual(calls[1],(ITEM['imagem_url'],True))
 def test_html_is_not_photo(self):
  fetch,calls=self.fixture(b'<html>error</html>')
  with patch.object(a,'transporte',return_value=fetch),patch.object(a.mega,'extract',return_value=dict(ITEM)):
   with self.assertRaises(ValueError):a.foto('123')
 def test_svg_is_not_photo(self):
  fetch,calls=self.fixture(b'<svg/>')
  with patch.object(a,'transporte',return_value=fetch),patch.object(a.mega,'extract',return_value=dict(ITEM)):
   with self.assertRaises(ValueError):a.foto('123')
 def test_unavailable_no_photo_download(self):
  fetch,calls=self.fixture()
  with patch.object(a,'transporte',return_value=fetch),patch.object(a.mega,'extract',return_value={**ITEM,'disponibilidade':'indisponivel'}):
   with self.assertRaises(ValueError):a.foto('123')
   self.assertEqual(len(calls),1)
 def test_different_variant_no_photo_download(self):
  fetch,calls=self.fixture()
  with patch.object(a,'transporte',return_value=fetch),patch.object(a.mega,'extract',return_value={**ITEM,'versao':'EDP'}):
   with self.assertRaises(ValueError):a.foto('123')
   self.assertEqual(len(calls),1)
 def test_quote_auth_before_approval_read(self):
  with patch.object(a,'orcamento') as q:
   self.assertEqual(self.request_route('/v1/orcamento',{'codigo':'123','quantidade':2},'wrong')[0],403);q.assert_not_called()
 def test_quote_error_hides_private_detail(self):
  with patch.object(a,'orcamento',side_effect=ValueError('private detail')):
   status,r=self.request_route('/v1/orcamento',{'codigo':'123','quantidade':2});self.assertEqual(status,503);self.assertNotIn('private detail',json.dumps(r))
 def test_quote_invalid_quantity_before_read(self):
  with patch.object(a,'orcamento') as q:
   self.assertEqual(self.request_route('/v1/orcamento',{'codigo':'123','quantidade':True})[0],400);q.assert_not_called()
 def test_photo_arbitrary_url_rejected(self):
  with patch.object(a,'foto') as q:
   self.assertEqual(self.request_route('/v1/foto',{'codigo':'https://example.invalid/a'})[0],400);q.assert_not_called()
 def test_photo_auth_before_network(self):
  with patch.object(a,'foto') as q:
   self.assertEqual(self.request_route('/v1/foto',{'codigo':'123'},'wrong')[0],403);q.assert_not_called()

if __name__=='__main__':unittest.main()
