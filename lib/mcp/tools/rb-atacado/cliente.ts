import { constants } from "node:fs";
import { open } from "node:fs/promises";
import { z } from "zod";
import type { McpContext } from "../../types";

// Private read-only mount; no new mandatory env and no URL supplied by model.
const CONFIG_PATH = "/opt/rb-atacado/config.json";
const ENDPOINT = "http://deskcommcrm-mega-vpn:40100/v1/buscar";
export const termoDePerfume = z.string().min(2).max(120)
  .regex(/^[\p{L}\p{N} .'-]+$/u)
  .refine((s) => !/\d{6,}/u.test(s), "Use somente identificação do perfume.")
  .refine((s) => /\p{L}/u.test(s), "Use somente identificação do perfume.");
export const configSchema = z.object({
  enabled: z.literal(true), organization_id: z.uuid(), contact_id: z.uuid(),
  authorization_token: z.string().regex(/^[a-f0-9]{64}$/),
}).strict();
type Config = z.infer<typeof configSchema>;
const httpsMega = z.string().max(2000).refine((s) => {
  try { const u = new URL(s); return u.protocol === "https:" && !u.username && !u.password && !u.port && !u.hash &&
    ["www.megaeletronicos.com", "megaeletronicos.com", "resource.megaeletronicos.com"].includes(u.hostname); }
  catch { return false; }
});
const opcao = z.object({
  fornecedor: z.literal("Mega Eletrônicos"), codigo: z.string().regex(/^\d{1,12}$/),
  nome: z.string().min(1).max(300), marca: z.string().max(100).nullable(),
  versao: z.enum(["EDP", "EDT", "Parfum", "Elixir", "Extrait de Parfum", "EDC"]).nullable(),
  variante: z.literal("Eau Forte").nullable(), volume_ml: z.number().int().positive().max(5000).nullable(),
  apresentacao: z.enum(["kit", "tester", "refil", "ambigua", "não confirmada"]),
  imagem_url: httpsMega.nullable(), fonte: httpsMega,
  consultado_em_utc: z.iso.datetime({ offset: true }),
  disponibilidade: z.literal("disponivel"), quantidade_disponivel: z.null(),
  preco_final_aprovado_brl: z.null(), situacao_preco: z.literal("pendente_de_consulta_e_aprovacao"),
});
const resposta = z.object({
  status: z.enum(["opcoes_disponiveis", "sem_estoque_nos_anuncios_verificados", "nao_foi_possivel_confirmar"]),
  opcoes: z.array(opcao).max(20), cobertura_integral_catalogo: z.literal(false),
  detalhes_consultados_integralmente: z.boolean(),
}).superRefine((r, c) => {
  if ((r.status === "opcoes_disponiveis") !== (r.opcoes.length > 0)) c.addIssue({ code: "custom", message: "Resposta inconsistente." });
  if (r.status === "sem_estoque_nos_anuncios_verificados" && !r.detalhes_consultados_integralmente) c.addIssue({ code: "custom", message: "Cobertura não confirmada." });
});
export async function lerConfig(): Promise<Config> {
  const f = await open(CONFIG_PATH, constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const s = await f.stat();
    if (!s.isFile() || (s.mode & 0o777) !== 0o600 || s.size > 4096) throw new Error("configuracao_indisponivel");
    return configSchema.parse(JSON.parse(await f.readFile("utf8")));
  } finally { await f.close(); }
}
const recusado = (motivo: string) => ({ permitido: false, motivo, mensagem: "Não foi possível consultar esta opção agora; o valor depende da RB Atacado." });
interface Dependencias { config: () => Promise<Config>; fetch: typeof globalThis.fetch; now: () => number }
export async function consultarMega(input: { perfume: string }, ctx: McpContext,
  deps: Dependencias = { config: lerConfig, fetch: globalThis.fetch, now: Date.now }) {
  // Configuration errors, other tenants and absence of trusted contact fail closed BEFORE network.
  try {
    const c = configSchema.parse(await deps.config());
    if (ctx.organizationId !== c.organization_id || ctx.contatoDoTurno !== c.contact_id) return recusado("fora_do_teste");
    const p = termoDePerfume.safeParse(input.perfume);
    if (!p.success) return recusado("identificacao_invalida");
    const { data: contato, error } = await ctx.supabase.from("contacts")
      .select("id,kind,is_blocked,is_anonymized").eq("organization_id", ctx.organizationId)
      .eq("id", c.contact_id).maybeSingle();
    if (error || !contato || contato.id !== c.contact_id || contato.kind === "whatsapp_group" ||
      contato.is_blocked !== false || contato.is_anonymized !== false) return recusado("contato_indisponivel");
    const r = await deps.fetch(ENDPOINT, {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(120_000),
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${c.authorization_token}` },
      body: JSON.stringify({ perfume: p.data }),
    });
    if (!r.ok) return recusado("consulta_nao_confirmada");
    // Bound the stream, not only a possibly absent Content-Length.
    if (!r.body) return recusado("consulta_nao_confirmada");
    const reader = r.body.getReader(); let total = 0; const chunks: Uint8Array[] = [];
    try { while (true) {
      const x = await reader.read(); if (x.done) break;
      total += x.value.byteLength; if (total > 32_768) { await reader.cancel(); return recusado("consulta_nao_confirmada"); }
      chunks.push(x.value);
    } } finally { reader.releaseLock(); }
    const body = new Uint8Array(total); let pos = 0;
    for (const chunk of chunks) { body.set(chunk, pos); pos += chunk.length; }
    // Zod projects the allowlist: pages, raw prices and extra fields never reach the model.
    const result = resposta.parse(JSON.parse(new TextDecoder().decode(body)));
    if (result.opcoes.some((x) => {
      const age = deps.now() - Date.parse(x.consultado_em_utc); return age < -60_000 || age > 120_000;
    })) return recusado("consulta_expirada");
    return { ...result, mensagem: result.status === "sem_estoque_nos_anuncios_verificados"
      ? "Sem disponibilidade nos anúncios verificados; não comprova todo o catálogo."
      : "A disponibilidade não confirma a quantidade. Identifique a opção com o cliente; preço depende de aprovação comercial." };
  } catch { return recusado("consulta_nao_confirmada"); }
}

export const pedidoOrcamento = z.object({ codigo: z.string().regex(/^\d{1,12}$/), quantidade: z.number().int().min(1).max(1000) });
const cotacaoAprovada = z.object({
  produto: z.object({ codigo: z.string().regex(/^\d{1,12}$/), nome: z.string().min(1).max(300), marca: z.string().max(100).nullable(), versao: z.enum(["EDP", "EDT", "Parfum", "Elixir", "Extrait de Parfum", "EDC"]), variante: z.literal("Eau Forte").nullable(), volume_ml: z.number().int().positive().max(5000), apresentacao: z.enum(["frasco", "refil", "tester", "kit"]), imagem_url: httpsMega.nullable(), imagem_validada: z.boolean() }),
  quantidade: z.number().int().min(1).max(1000), moeda: z.literal("BRL"), situacao: z.literal("aprovado"),
  preco_unitario_cents: z.number().int().positive().max(1_000_000_000), subtotal_cents: z.number().int().positive().max(1_000_000_000),
  quantidade_em_estoque: z.literal("nao_informada"), disponibilidade_na_consulta: z.literal("disponivel"),
  compra_reserva_pagamento_confirmados: z.literal(false), valido_ate_utc: z.iso.datetime({ offset: true }),
});
export async function consultarOrcamento(input: { codigo: string; quantidade: number }, ctx: Pick<McpContext, 'organizationId' | 'contatoDoTurno' | 'supabase'>,
  deps: Dependencias = { config: lerConfig, fetch: globalThis.fetch, now: Date.now }) {
  try {
    const c = configSchema.parse(await deps.config());
    if (ctx.organizationId !== c.organization_id || ctx.contatoDoTurno !== c.contact_id) return recusado("fora_do_teste");
    const pedido = pedidoOrcamento.safeParse(input);
    if (!pedido.success) return recusado("identificacao_invalida");
    const { data: contato, error } = await ctx.supabase.from("contacts")
      .select("id,kind,is_blocked,is_anonymized").eq("organization_id", ctx.organizationId)
      .eq("id", c.contact_id).maybeSingle();
    if (error || !contato || contato.id !== c.contact_id || contato.kind === "whatsapp_group" || contato.is_blocked !== false || contato.is_anonymized !== false) return recusado("contato_indisponivel");
    const r = await deps.fetch("http://deskcommcrm-mega-vpn:40100/v1/orcamento", {
      method: "POST", redirect: "error", signal: AbortSignal.timeout(120_000),
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${c.authorization_token}` },
      body: JSON.stringify(pedido.data),
    });
    if (!r.ok || !r.body) return recusado("orcamento_nao_confirmado");
    const reader = r.body.getReader(); const chunks: Uint8Array[] = []; let size = 0;
    try { while (true) {
      const part = await reader.read(); if (part.done) break; size += part.value.byteLength;
      if (size > 16_384) { await reader.cancel(); return recusado("orcamento_nao_confirmado"); }
      chunks.push(part.value);
    } } finally { reader.releaseLock(); }
    const bytes = new Uint8Array(size); let offset = 0;
    for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength; }
    const v = cotacaoAprovada.parse(JSON.parse(new TextDecoder().decode(bytes)));
    if (v.produto.codigo !== pedido.data.codigo || v.quantidade !== pedido.data.quantidade ||
      v.subtotal_cents !== v.preco_unitario_cents * v.quantidade || Date.parse(v.valido_ate_utc) <= deps.now()) return recusado("orcamento_nao_confirmado");
    return v;
  } catch { return recusado("orcamento_nao_confirmado"); }
}
