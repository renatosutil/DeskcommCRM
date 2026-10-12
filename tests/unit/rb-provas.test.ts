import { describe,it,expect,vi } from 'vitest';
import type { McpContext } from '../../lib/mcp/types';
import type pg from 'pg';
import {assinarFoto,conferirFoto} from '../../lib/mcp/tools/rb-atacado/provas';
import {conferirEntregaRb} from '../../lib/mcp/tools/rb-atacado/entrega';
import {textoRespostaRb} from '../../lib/mcp/tools/rb-atacado/respostas';
import {confirmarEscopoRbAntesDaIA,confirmarEscopoRbAntesDaIASupabase} from '../../lib/mcp/tools/rb-atacado/escopo';
const config={enabled:true as const,organization_id:'00000000-0000-4000-8000-000000000001',
 contact_id:'00000000-0000-4000-8000-000000000002',agent_id:'00000000-0000-4000-8000-000000000009',authorization_token:'a'.repeat(64)};
const conversation='00000000-0000-4000-8000-000000000003',job='00000000-0000-4000-8000-000000000004';
const now=1_800_000_000_000;
const data={org:config.organization_id,contact:config.contact_id,agent:config.agent_id,conversation,job,code:'123',
 path:config.organization_id+'/'+conversation+'/mega-123-'+job+'.webp',mime:'image/webp' as const,
 body:'Perfume fixture\nConcentração: EDP. Volume: 100 ml.',expira:now+120_000};
const deps={enabled:true,config:async()=>config,consultar:vi.fn(),now:()=>now};
const ctx={organizationId:config.organization_id,contatoDoTurno:config.contact_id,supabase:{} as McpContext['supabase']};
const entrada={actorType:'ai_agent',actorId:config.agent_id,ctx,body:data.body,tipo:'image',grupo:false,
 conversationId:conversation,mediaPath:data.path,mediaMime:data.mime};
describe('envio RB aceita somente saídas verificadas',()=>{
 it('foto original atestada pode ser entregue',async()=>{
  await expect(conferirEntregaRb({...entrada,metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}},deps)).resolves.toBeUndefined();
 });
 it('revalida vencimento no retry',async()=>{
  const e={...entrada,metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}};
  await conferirEntregaRb(e,deps);
  await expect(conferirEntregaRb(e,{...deps,now:()=>now+120_001})).rejects.toThrow();
 });
 it('atestado não permite mudar legenda',async()=>{
  await expect(conferirEntregaRb({...entrada,body:'Valor aprovado: quinhentos reais',metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}},deps)).rejects.toThrow();
 });
 it('atestado não permite mudar arquivo',async()=>{
  await expect(conferirEntregaRb({...entrada,mediaPath:'outro',metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}},deps)).rejects.toThrow();
 });
 it('atestado não permite outra conversa',async()=>{
  await expect(conferirEntregaRb({...entrada,conversationId:job,metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}},deps)).rejects.toThrow();
 });
 it('assinatura adulterada é recusada',()=>{
  const proof=assinarFoto(data,config.authorization_token);
  expect(()=>conferirFoto({...proof,body:'Outro texto'},config.authorization_token,now)).toThrow();
 });
 it('assinatura com outra chave é recusada',()=>{
  expect(()=>conferirFoto(assinarFoto(data,'b'.repeat(64)),config.authorization_token,now)).toThrow();
 });
 it('atestados com prazo excessivo são recusados',()=>{
  expect(()=>conferirFoto(assinarFoto({...data,expira:now+120_001},config.authorization_token),config.authorization_token,now)).toThrow();
 });
 it.each(['Sai por seiscentos e treze','Consigo metade do valor','Entrega amanhã garantida','Compra confirmada','Mensagem livre'])(
  'texto livre nunca sai: %s',async body=>{
   await expect(conferirEntregaRb({...entrada,tipo:'text',body,metadata:{}},deps)).rejects.toThrow();
  });
 it('resposta curta autorizada não consulta modelo ou loja',async()=>{
  const body=textoRespostaRb('perguntar_ml');
  await expect(conferirEntregaRb({...entrada,tipo:'text',body,metadata:{rb_resposta:'perguntar_ml'}},deps)).resolves.toBeUndefined();
  expect(deps.consultar).not.toHaveBeenCalled();
 });
 it('modelo não pode adulterar resposta curta',async()=>{
  await expect(conferirEntregaRb({...entrada,tipo:'text',body:'Qual é o volume em ml? Custa 500.',metadata:{rb_resposta:'perguntar_ml'}},deps)).rejects.toThrow();
 });
 it('id de run diferente não permite texto livre',async()=>{
  await expect(conferirEntregaRb({...entrada,actorId:job,body:'Mensagem livre',metadata:{}},deps)).rejects.toThrow();
 });
 it('actor genérico do motor aceita somente foto atestada do agente privado',async()=>{
  await expect(conferirEntregaRb({...entrada,actorId:'agent-engine',metadata:{rb_foto_mega:assinarFoto(data,config.authorization_token)}},deps)).resolves.toBeUndefined();
 });
 it('outra organização conserva fluxo nativo',async()=>{
  await expect(conferirEntregaRb({...entrada,ctx:{...ctx,organizationId:job},body:'Mensagem livre'},deps)).resolves.toBeUndefined();
 });
});
describe('escopo privado antes de qualquer IA',()=>{
 const input={organizationId:config.organization_id,conversationId:conversation};
 const allowed={contact_id:config.contact_id,is_group:false,kind:'individual',is_blocked:false,is_anonymized:false,is_personal:false};
 const scopeDeps={enabled:true,config:async()=>config};
 const pool=(row:unknown)=>({query:vi.fn(async()=>({rows:row?[row]:[]}))});
 it('somente contato permitido passa',async()=>expect(await confirmarEscopoRbAntesDaIA(pool(allowed) as unknown as pg.Pool,input,scopeDeps)).toBe(true));
 it.each([{...allowed,contact_id:job},{...allowed,is_group:true},{...allowed,is_blocked:true},{...allowed,is_anonymized:true},{...allowed,is_personal:true},{...allowed,kind:'whatsapp_group'},null])(
  'outro contato/grupo/estado inválido é bloqueado',async row=>expect(await confirmarEscopoRbAntesDaIA(pool(row) as unknown as pg.Pool,input,scopeDeps)).toBe(false));
 it('falha de banco é bloqueada',async()=>{
  const p={query:vi.fn(async()=>{throw new Error('fixture privada');})};
  expect(await confirmarEscopoRbAntesDaIA(p as unknown as pg.Pool,input,scopeDeps)).toBe(false);
 });
 it('filtra organização e conversa na consulta',async()=>{
  const p=pool(allowed);await confirmarEscopoRbAntesDaIA(p as unknown as pg.Pool,input,scopeDeps);
  expect(p.query).toHaveBeenCalledWith(expect.stringContaining('cv.organization_id=$1 and cv.id=$2'),[input.organizationId,input.conversationId]);
 });
});

describe("escopo Supabase da derivação antes de IA",()=>{
 const input={organizationId:config.organization_id,conversationId:conversation};
 const allowed={contact_id:config.contact_id,is_group:false,contacts:{kind:"individual",is_blocked:false,is_anonymized:false,is_personal:false}};
 const deps={enabled:true,config:async()=>config};
 function admin(data:unknown,error:unknown=null){
  const q={select:vi.fn(),eq:vi.fn(),maybeSingle:vi.fn(async()=>({data,error}))};
  q.select.mockReturnValue(q);q.eq.mockReturnValue(q);
  return {from:vi.fn(()=>q)};
 }
 it("somente o contato configurado passa",async()=>{
  const a=admin(allowed);
  expect(await confirmarEscopoRbAntesDaIASupabase(a as unknown as McpContext["supabase"],input,deps)).toBe(true);
  expect(a.from().eq).toHaveBeenCalledWith("organization_id",input.organizationId);
  expect(a.from().eq).toHaveBeenCalledWith("id",input.conversationId);
 });
 it.each([null,{...allowed,contact_id:job},{...allowed,is_group:true},{...allowed,contacts:{...allowed.contacts,is_blocked:true}},{...allowed,contacts:{...allowed.contacts,is_anonymized:true}},{...allowed,contacts:{...allowed.contacts,is_personal:true}}])(
 "ausência/outro contato/grupo/recusa falha fechado",async data=>{
  expect(await confirmarEscopoRbAntesDaIASupabase(admin(data) as unknown as McpContext["supabase"],input,deps)).toBe(false);
 });
 it("erro de consulta falha fechado",async()=>{
  expect(await confirmarEscopoRbAntesDaIASupabase(admin(allowed,{code:"fixture"}) as unknown as McpContext["supabase"],input,deps)).toBe(false);
 });
 it("opt-in desligado não consulta banco ou arquivo",async()=>{
  const a=admin(null), configFn=vi.fn();
  expect(await confirmarEscopoRbAntesDaIASupabase(a as unknown as McpContext["supabase"],input,{enabled:false,config:configFn})).toBe(true);
  expect(a.from).not.toHaveBeenCalled();expect(configFn).not.toHaveBeenCalled();
 });
});


describe('escolha de perfumes sem obrigação de compra',()=>{
 it('oferece explicitamente recusar todas as opções',()=>{
  expect(textoRespostaRb('escolher_opcao')).toMatch(/não quiser nenhuma/);
  expect(textoRespostaRb('nenhuma_opcao')).toMatch(/não vou incluir essas opções/);
 });
 it('confirma versão, volume e quantidade somente como interesse',()=>{
  const body=textoRespostaRb('confirmar_interesse');
  expect(body).toMatch(/versão e volume/);
  expect(body).toMatch(/quantidade informada/);
  expect(body).toMatch(/não confirma compra/);
  expect(body).not.toMatch(/R\$|Pix|reserva confirmada|compra confirmada/);
 });
 it.each(['escolher_opcao','nenhuma_opcao','confirmar_interesse'])(
  'novo fluxo mantém a proteção no transporte: %s',async resposta=>{
   const body=textoRespostaRb(resposta);
   const message={...entrada,tipo:'text',body,metadata:{rb_resposta:resposta}};
   await expect(conferirEntregaRb(message,deps)).resolves.toBeUndefined();
   await expect(conferirEntregaRb({...message,ctx:{...ctx,contatoDoTurno:job}},deps)).rejects.toThrow();
   await expect(conferirEntregaRb({...message,grupo:true},deps)).rejects.toThrow();
   await expect(conferirEntregaRb({...message,body:body+' Compra confirmada.'},deps)).rejects.toThrow();
  });
});
