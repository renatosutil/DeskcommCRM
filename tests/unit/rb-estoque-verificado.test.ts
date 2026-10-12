import {it,expect,vi} from 'vitest';
import type {McpContext} from '../../lib/mcp/types';
import {prepararSemEstoqueRb,TEXTO_SEM_ESTOQUE} from '../../lib/mcp/tools/rb-atacado/entrega';
const ctx={organizationId:'fixture-org',contatoDoTurno:'fixture-contact',supabase:{} as McpContext['supabase']};
const vazio={mensagem:'fixture pública',status:'sem_estoque_nos_anuncios_verificados' as const,opcoes:[],cobertura_integral_catalogo:false as const,detalhes_consultados_integralmente:true};
it('informa falta somente nos anúncios verificados',async()=>{
 expect(await prepararSemEstoqueRb(ctx,{perfume:'Sauvage EDP 100'},vi.fn(async()=>vazio))).toEqual({referencia:{perfume:'Sauvage EDP 100'},body:TEXTO_SEM_ESTOQUE});
});
it('consulta incompleta não prova falta de estoque',async()=>{
 await expect(prepararSemEstoqueRb(ctx,{perfume:'Sauvage'},vi.fn(async()=>({...vazio,detalhes_consultados_integralmente:false})))).rejects.toThrow();
});
it('erro não é falta de estoque',async()=>{
 await expect(prepararSemEstoqueRb(ctx,{perfume:'Sauvage'},vi.fn(async()=>({...vazio,status:'nao_foi_possivel_confirmar' as const})))).rejects.toThrow();
});
it('opção disponível impede a declaração de falta',async()=>{
 await expect(prepararSemEstoqueRb(ctx,{perfume:'Sauvage'},vi.fn(async()=>({...vazio,status:'opcoes_disponiveis' as const})))).rejects.toThrow();
});
it('não aceita URL livre ou telefone como pesquisa',async()=>{
 const buscar=vi.fn(async()=>vazio);
 await expect(prepararSemEstoqueRb(ctx,{perfume:'https://fixture.invalid'},buscar)).rejects.toThrow();
 expect(buscar).not.toHaveBeenCalled();
});
