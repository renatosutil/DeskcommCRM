import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { McpContext } from '../../lib/mcp/types';
import { conferirEntregaRb, prepararOrcamentoRb, textoOrcamentoRb } from '../../lib/mcp/tools/rb-atacado/entrega';
const config={enabled:true as const,organization_id:'00000000-0000-4000-8000-000000000001',
 contact_id:'00000000-0000-4000-8000-000000000002',agent_id:'00000000-0000-4000-8000-000000000009',authorization_token:'a'.repeat(64)};
const cotacao={
 produto:{codigo:'123',nome:'Perfume fixture',marca:'Fixture',versao:'EDP' as const,
 variante:null,volume_ml:100,apresentacao:'frasco' as const,imagem_url:null,imagem_validada:false},
 quantidade:2,moeda:'BRL' as const,situacao:'aprovado' as const,
 preco_unitario_cents:7088,subtotal_cents:14176,quantidade_em_estoque:'nao_informada' as const,
 disponibilidade_na_consulta:'disponivel' as const,compra_reserva_pagamento_confirmados:false as const,
 valido_ate_utc:'2099-01-01T00:00:00Z',
};
const ctx={organizationId:config.organization_id,contatoDoTurno:config.contact_id,
 supabase:{} as McpContext['supabase']};
const consultar=vi.fn(async()=>cotacao);
const deps={enabled:true,config:vi.fn(async()=>config),consultar};
const entrada=()=>({actorType:'ai_agent',actorId:config.agent_id,ctx,body:textoOrcamentoRb(cotacao),tipo:'text',
 grupo:false,metadata:{rb_orcamento:{codigo:'123',quantidade:2}}});
describe('orçamento conferido no envio e retry',()=>{
 beforeEach(()=>{vi.clearAllMocks();consultar.mockImplementation(async()=>cotacao);deps.config.mockImplementation(async()=>config);});
 it('envia somente texto determinístico do valor aprovado',async()=>{
  const p=await prepararOrcamentoRb(ctx,{codigo:'123',quantidade:2},consultar);
  expect(p.body).toContain('R$ 70,88');expect(p.body).toContain('R$ 141,76');
  expect(p.body).not.toMatch(/custo|35%|5%/);
  await expect(conferirEntregaRb(entrada(),deps)).resolves.toBeUndefined();
 });
 it('reconsulta em cada tentativa',async()=>{
  await conferirEntregaRb(entrada(),deps);await conferirEntregaRb(entrada(),deps);
  expect(consultar).toHaveBeenCalledTimes(2);
 });
 it('veta valor alterado depois da primeira tentativa',async()=>{
  const e=entrada();await conferirEntregaRb(e,deps);
  consultar.mockImplementation(async()=>({...cotacao,preco_unitario_cents:8000,subtotal_cents:16000}));
  await expect(conferirEntregaRb(e,deps)).rejects.toThrow('Orçamento não confirmado');
 });
 it('veta erro de fonte ou aprovação revogada',async()=>{
  consultar.mockRejectedValue(new Error('fixture-privada'));
  await expect(conferirEntregaRb(entrada(),deps)).rejects.toThrow('Orçamento não confirmado');
 });
 it('veta alteração do texto pelo modelo',async()=>{
  const e=entrada();e.body+=' Desconto aprovado.';
  await expect(conferirEntregaRb(e,deps)).rejects.toThrow();
 });
 it('outro contato bloqueado antes da consulta',async()=>{
  const e=entrada();e.ctx={...ctx,contatoDoTurno:'00000000-0000-4000-8000-000000000003'};
  await expect(conferirEntregaRb(e,deps)).rejects.toThrow();expect(consultar).not.toHaveBeenCalled();
 });
 it('grupo bloqueado antes da consulta',async()=>{
  await expect(conferirEntregaRb({...entrada(),grupo:true},deps)).rejects.toThrow();
  expect(consultar).not.toHaveBeenCalled();
 });
 it('preço livre sem referência aprovado é recusado',async()=>{
  await expect(conferirEntregaRb({...entrada(),metadata:{},body:'Custa R$ 55,00'},deps)).rejects.toThrow();
 });
 it('conversa sem preço não exige consultar loja',async()=>{
  await expect(conferirEntregaRb({...entrada(),metadata:{rb_resposta:'perguntar_ml'},body:'Qual é o volume em ml?'},deps)).resolves.toBeUndefined();
  expect(consultar).not.toHaveBeenCalled();
 });
 it('template não contorna orçamento',async()=>{
  await expect(conferirEntregaRb({...entrada(),tipo:'template'},deps)).rejects.toThrow();
 });
 it('humano permanece no fluxo nativo',async()=>{
  await expect(conferirEntregaRb({...entrada(),actorType:'user'},deps)).resolves.toBeUndefined();
  expect(consultar).not.toHaveBeenCalled();
 });
 it('falha na configuração fecha o envio sem revelar erro',async()=>{
  deps.config.mockRejectedValue(new Error('fixture-privada'));
  await expect(conferirEntregaRb(entrada(),deps)).rejects.toThrow('Orçamento não confirmado');
 });
 it('outra organização conserva o fluxo nativo',async()=>{
  await expect(conferirEntregaRb({...entrada(),ctx:{...ctx,organizationId:'outra-org'}},deps)).resolves.toBeUndefined();
  expect(consultar).not.toHaveBeenCalled();
 });
});
