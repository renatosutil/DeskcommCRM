import {describe,it,expect,vi,beforeEach} from 'vitest';
import type {McpContext} from '../../lib/mcp/types';
import {consultarEstimativa,type EstimativaRb} from '../../lib/mcp/tools/rb-atacado/cliente';
import {textoEstimativaRb,conferirEntregaRb} from '../../lib/mcp/tools/rb-atacado/entrega';
import {assinarFoto} from '../../lib/mcp/tools/rb-atacado/provas';
import {textoRespostaRb} from '../../lib/mcp/tools/rb-atacado/respostas';
const org='11111111-1111-4111-8111-111111111111',contact='22222222-2222-4222-8222-222222222222',other='33333333-3333-4333-8333-333333333333',agent='44444444-4444-4444-8444-444444444444';
const cfg={enabled:true as const,organization_id:org,contact_id:contact,agent_id:agent,authorization_token:'a'.repeat(64)};
const now=Date.parse('2026-10-12T16:00:00Z');
const base:EstimativaRb={produto:{codigo:'123',nome:'Perfume teste EDT 100 ml',marca:'Marca',versao:'EDT',variante:null,volume_ml:100,apresentacao:'não confirmada',imagem_url:'https://resource.megaeletronicos.com/teste.webp'},quantidade:null,moeda:'BRL',situacao:'estimativa',preco_unitario_cents:61328,subtotal_cents:null,quantidade_em_estoque:'nao_informada',disponibilidade_na_consulta:'disponivel',compra_reserva_pagamento_confirmados:false,fechamento_pendente_aprovacao:true,consultado_em_utc:'2026-10-12T16:00:00Z',valido_ate_utc:'2026-10-12T16:02:00Z'};
let value:unknown=base;
let row={id:contact,kind:'person',is_blocked:false,is_anonymized:false,is_personal:false};
const q={select(){return this;},eq(){return this;},async maybeSingle(){return {data:row,error:null};}};
const ctx={organizationId:org,contatoDoTurno:contact,supabase:{from:()=>q}} as unknown as McpContext;
const fetcher=vi.fn(async(_url:unknown,_init:RequestInit)=>new Response(JSON.stringify(value)));
const deps={config:async()=>cfg,fetch:fetcher as typeof fetch,now:()=>now};
beforeEach(()=>{value=base;fetcher.mockClear();row={id:contact,kind:'person',is_blocked:false,is_anonymized:false,is_personal:false};});
describe('estimativa verificada sem aprovar compra',()=>{
 it('retorna preço unitário sem presumir quantidade',async()=>{
  expect(await consultarEstimativa({codigo:'123'},ctx,deps)).toEqual(base);
  expect(JSON.parse(fetcher.mock.calls[0]![1]!.body as string)).toEqual({codigo:'123',quantidade:null});
 });
 it('calcula subtotal somente para quantidade informada',async()=>{
  value={...base,quantidade:2,subtotal_cents:122656};
  expect(await consultarEstimativa({codigo:'123',quantidade:2},ctx,deps)).toEqual(value);
 });
 it('bloqueia outro contato antes da rede',async()=>{
  expect(await consultarEstimativa({codigo:'123'},{...ctx,contatoDoTurno:other},deps)).toMatchObject({permitido:false});
  expect(fetcher).not.toHaveBeenCalled();
 });
 it('bloqueia grupo e contato pessoal antes da rede',async()=>{
  row.kind='whatsapp_group';await consultarEstimativa({codigo:'123'},ctx,deps);expect(fetcher).not.toHaveBeenCalled();
  row.kind='person';row.is_personal=true;await consultarEstimativa({codigo:'123'},ctx,deps);expect(fetcher).not.toHaveBeenCalled();
 });
 it.each([{...base,subtotal_cents:61328},{...base,quantidade:1,subtotal_cents:61328},{...base,valido_ate_utc:'2026-10-12T15:59:00Z'},{...base,compra_reserva_pagamento_confirmados:true},{...base,disponibilidade_na_consulta:'indisponivel'}])('recusa inconsistência, vencimento ou compra confirmada',async x=>{
  value=x;expect(await consultarEstimativa({codigo:'123'},ctx,deps)).toMatchObject({permitido:false});
 });
 it('legenda cabe em uma foto, inclui condições e não expõe formação do preço',()=>{
  const body=textoEstimativaRb(base);
  expect(body.length).toBeLessThanOrEqual(1024);
  expect(body).toContain('Preço estimado: R$ 613,28 por unidade.');
  expect(body).toContain('aprovação');expect(body).toContain('sua confirmação antes do fechamento');
  expect(body).not.toMatch(/Subtotal|Valor aprovado|USD|\d+\s*%|custo de compra/);
 });
 it('subtotal inclui confirmação do item e da quantidade na mesma mensagem',()=>{
  const body=textoEstimativaRb({...base,quantidade:2,subtotal_cents:122656});
  expect(body).toContain('Subtotal estimado: R$ 1.226,56');
  expect(body).toContain('Confirma este item e esta quantidade somente para o orçamento?');
  expect(body).not.toContain('Compra confirmada');
 });
 it('escolha e quantidade cabem numa pergunta com recusa explícita',()=>{
  const body=textoRespostaRb('escolher_opcao_quantidade');
  expect(body).toContain('quantas unidades');expect(body).toContain('não quiser nenhuma');
 });
 it('transporte revalida preço da legenda antes de cada tentativa',async()=>{
  const body=textoEstimativaRb(base),job='55555555-5555-4555-8555-555555555555';
  const proof=assinarFoto({org,contact,agent,conversation:other,job,code:'123',path:org+'/'+other+'/mega-123-'+job+'.webp',mime:'image/webp',body,expira:now+120000,estimativa:{preco_unitario_cents:61328}},cfg.authorization_token);
  const input={actorType:'ai_agent',actorId:agent,ctx,body,tipo:'image',grupo:false,conversationId:other,mediaPath:proof.path,mediaMime:proof.mime,metadata:{rb_foto_mega:proof}};
  const estimar=vi.fn(async()=>base);
  const guard={enabled:true,config:async()=>cfg,consultar:vi.fn(),estimar,now:()=>now};
  await expect(conferirEntregaRb(input,guard)).resolves.toBeUndefined();
  estimar.mockResolvedValue({...base,preco_unitario_cents:70000});
  await expect(conferirEntregaRb(input,guard)).rejects.toThrow();
 });
});
