import { textoRespostaRb } from './respostas';
import { conferirFoto } from './provas';
import { z } from 'zod';
import { consultarOrcamento, consultarMega, termoDePerfume, lerConfig, configSchema } from './cliente';
import type { McpContext } from '../../types';

export const referenciaRb = z.object({
 codigo: z.string().regex(/^\d{1,12}$/),
 quantidade: z.number().int().min(1).max(1000),
}).strict();
type Contexto = Pick<McpContext, 'organizationId' | 'contatoDoTurno' | 'supabase'>;
type Cotacao = Awaited<ReturnType<typeof consultarOrcamento>>;

export class EntregaRbRecusada extends Error {
 readonly terminal = true;
 constructor() { super('Orçamento não confirmado para envio.'); this.name='EntregaRbRecusada'; }
}
function reais(cents: number): string {
 return 'R$ ' + new Intl.NumberFormat('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(cents/100);
}
/** Renderiza SOMENTE o preço final; modelo não calcula ou escreve a cotação. */
export function textoOrcamentoRb(cotacao: Cotacao): string {
 if (!('situacao' in cotacao) || cotacao.situacao !== 'aprovado') throw new EntregaRbRecusada();
 const p=cotacao.produto;
 return [
  cotacao.quantidade + ' unidade(s) de ' + p.nome + ' — ' + p.versao +
   (p.variante ? ' / ' + p.variante : '') + ', ' + p.volume_ml + ' ml, ' + p.apresentacao + '.',
  'Valor aprovado: ' + reais(cotacao.preco_unitario_cents) + ' por unidade.',
  'Subtotal: ' + reais(cotacao.subtotal_cents) + '.',
  'A loja informa disponibilidade, sem confirmar quantidade em estoque.',
  'Prazo, reserva, pagamento e confirmação da compra dependem da RB Atacado.',
 ].join('\n');
}
export async function prepararOrcamentoRb(ctx:Contexto,input:unknown,
 consultar=consultarOrcamento) {
 const referencia=referenciaRb.parse(input);
 const cotacao=await consultar(referencia,ctx);
 if (!('situacao' in cotacao) || cotacao.situacao !== 'aprovado') throw new EntregaRbRecusada();
 return { referencia, body:textoOrcamentoRb(cotacao), cotacao };
}
export const pesquisaSemEstoque=z.object({perfume:termoDePerfume}).strict();
export const TEXTO_SEM_ESTOQUE='Essa pesquisa está sem estoque nos anúncios verificados da Mega Eletrônicos. Posso mostrar outras versões?';
export async function prepararSemEstoqueRb(ctx:Contexto,input:unknown,consultar=consultarMega){
 const pedido=pesquisaSemEstoque.parse(input);
 const resultado=await consultar(pedido,ctx);
 if(!('status' in resultado)||resultado.status!=='sem_estoque_nos_anuncios_verificados'||
  !resultado.detalhes_consultados_integralmente||resultado.opcoes.length!==0)throw new EntregaRbRecusada();
 return {referencia:pedido,body:TEXTO_SEM_ESTOQUE};
}
type Entrada = { actorType:string; actorId:string; ctx:Contexto; body:string; tipo:string;
 conversationId?:string; mediaPath?:string; mediaMime?:string;
 grupo:boolean; metadata?:Record<string,unknown> };
type Deps={enabled:boolean;config:typeof lerConfig;consultar:typeof consultarOrcamento;now?:()=>number;buscar?:typeof consultarMega};
/** Guarda opt-in privada, reexecutada antes de CADA tentativa do transporte. */
export async function conferirEntregaRb(input:Entrada,deps:Deps={
 enabled:process.env.RB_ATACADO_ENABLED==='1',config:lerConfig,consultar:consultarOrcamento
}):Promise<void> {
 if (!deps.enabled || input.actorType!=='ai_agent') return;
 try {
  const config=configSchema.parse(await deps.config());
  if(input.ctx.organizationId!==config.organization_id)return;
  if(input.grupo || input.ctx.contatoDoTurno!==config.contact_id)throw new EntregaRbRecusada();
  // Nesta organização de teste não há bypass por id de run/ator: somente saídas verificadas.
  const referencia=input.metadata?.rb_orcamento;
  if(referencia!==undefined){
   if(input.tipo!=='text')throw new EntregaRbRecusada();
   const atual=await prepararOrcamentoRb(input.ctx,referencia,deps.consultar);
   if(input.body!==atual.body)throw new EntregaRbRecusada();
  }else if(input.metadata?.rb_sem_estoque!==undefined){
   if(input.tipo!=='text')throw new EntregaRbRecusada();
   const atual=await prepararSemEstoqueRb(input.ctx,input.metadata.rb_sem_estoque,deps.buscar??consultarMega);
   if(input.body!==atual.body)throw new EntregaRbRecusada();
  }else if(input.metadata?.rb_foto_mega!==undefined){
   const foto=conferirFoto(input.metadata.rb_foto_mega,config.authorization_token,deps.now?.()??Date.now());
   if(input.tipo!=='image'||foto.org!==input.ctx.organizationId||foto.contact!==input.ctx.contatoDoTurno||
    foto.agent!==config.agent_id||foto.conversation!==input.conversationId||
    foto.path!==input.mediaPath||foto.mime!==input.mediaMime||foto.body!==input.body)throw new EntregaRbRecusada();
  }else{
   // Nenhum texto livre sai deste agente; não depende de reconhecer moedas/números.
   if(input.tipo!=='text'||input.body!==textoRespostaRb(input.metadata?.rb_resposta))
    throw new EntregaRbRecusada();
  }
 }catch{throw new EntregaRbRecusada();}
}
