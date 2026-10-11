import { z } from 'zod';
import { consultarOrcamento, lerConfig, configSchema } from './cliente';
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
 return { referencia, body:textoOrcamentoRb(cotacao) };
}
type Entrada = { actorType:string; ctx:Contexto; body:string; tipo:string;
 grupo:boolean; metadata?:Record<string,unknown> };
type Deps={enabled:boolean;config:typeof lerConfig;consultar:typeof consultarOrcamento};
/** Guarda opt-in privada, reexecutada antes de CADA tentativa do transporte. */
export async function conferirEntregaRb(input:Entrada,deps:Deps={
 enabled:process.env.RB_ATACADO_ENABLED==='1',config:lerConfig,consultar:consultarOrcamento
}):Promise<void> {
 if (!deps.enabled || input.actorType!=='ai_agent') return;
 try {
  const config=configSchema.parse(await deps.config());
  if(input.ctx.organizationId!==config.organization_id)return;
  if(input.grupo || input.ctx.contatoDoTurno!==config.contact_id)throw new EntregaRbRecusada();
  const referencia=input.metadata?.rb_orcamento;
  if(referencia!==undefined){
   if(input.tipo!=='text')throw new EntregaRbRecusada();
   const atual=await prepararOrcamentoRb(input.ctx,referencia,deps.consultar);
   if(input.body!==atual.body)throw new EntregaRbRecusada();
  }else{
   // Defesa adicional. Não substitui a revisão dos outros guardrails comerciais.
   if(input.tipo==='template' ||
    /(?:R\s*\$|US\s*\$|\b(?:BRL|USD|reais|d[oó]lares)\b|\d+[.,]\d{2}\b|\d+\s*%)/iu.test(input.body)){
     throw new EntregaRbRecusada();
   }
  }
 }catch{throw new EntregaRbRecusada();}
}
