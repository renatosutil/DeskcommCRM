import { z } from "zod";
import type { McpToolDefinition } from "../types";
import { consultarMega, consultarOrcamento, termoDePerfume } from "./rb-atacado/cliente";

const shape = {
  perfume: termoDePerfume.describe("Somente o nome do perfume e marca, nunca a mensagem do cliente ou dados pessoais. Concentração e ml apenas quando conhecidos."),
};
export const rbBuscarPerfumes: McpToolDefinition<typeof shape> = {
  name: "rb_buscar_perfumes",
  description: "Consulta variantes de perfumes na Mega Eletrônicos. Retorna apenas anúncios com disponibilidade confirmada, identificação e foto original. Não revela custo, preço da loja, cotação nem percentual. Não aprova orçamento, estoque quantitativo, prazo, compra ou pagamento. Cliente escolhe a variante; nunca substitua EDP por EDT ou Parfum. Falha de consulta não significa falta de estoque. Sem preço aprovado, informe que o valor depende de consulta e aprovação da RB Atacado.",
  inputSchema: shape,
  category: "read", requiresRole: "agent", requiresScope: "mcp:read",
  redigirParaAuditoria: () => ({ consulta: "perfumes", fornecedor: "mega" }),
  motivoDoVazio: (r) => {
    if (!r || typeof r !== "object") return "consulta_nao_confirmada";
    const x = r as { status?: string; permitido?: boolean };
    return x.status === "opcoes_disponiveis" ? null : "consulta_sem_opcoes_confirmadas";
  },
  handler: (input, ctx) => consultarMega(input, ctx),
};

const quoteShape = { codigo: z.string().regex(/^\d{1,12}$/), quantidade: z.number().int().min(1).max(1000) };
export const rbConsultarOrcamento: McpToolDefinition<typeof quoteShape> = {
  name: "rb_consultar_orcamento",
  description: "Relê um orçamento aprovado pela RB Atacado para o produto exato e quantidade solicitada pelo cliente. Reconfere preço, cotação e disponibilidade, validade e revogação. Somente o preço final em reais é retornado, nunca custo, cotação ou percentual. Não aprova preço ou desconto e não confirma estoque quantitativo, compra, reserva, Pix, entrega ou pagamento. Recusa significa consulta ou aprovação comercial pendente; não invente valores ou reutilize preço de conversa anterior. Antes de enviar, a cadeia precisa reconferir a mesma aprovação.",
  inputSchema: quoteShape, category: "read", requiresRole: "agent", requiresScope: "mcp:read",
  redigirParaAuditoria: () => ({ consulta: "orcamento_aprovado", fornecedor: "mega" }),
  handler: (input, ctx) => consultarOrcamento(input, ctx),
};
