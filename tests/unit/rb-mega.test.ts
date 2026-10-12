import assert from "node:assert/strict";
import { describe, it as test } from "vitest";
import { z } from "zod";
import { rbBuscarPerfumes, rbConsultarOrcamento } from "../../lib/mcp/tools/rb-atacado";
import { AGENT_TOOL_DEFS } from "../../lib/agent-engine/agent/inbound-turn";
import { consultarMega, termoDePerfume } from "../../lib/mcp/tools/rb-atacado/cliente";
import type { McpContext } from "../../lib/mcp/types";
const org = "11111111-1111-4111-8111-111111111111";
const contact = "22222222-2222-4222-8222-222222222222";
const other = "33333333-3333-4333-8333-333333333333";
const config = { enabled: true as const, organization_id: org, contact_id: contact, agent_id:'00000000-0000-4000-8000-000000000009',authorization_token: "a".repeat(64) };
let calls = 0, reads = 0;
let row: unknown = { id: contact, kind: "person", is_blocked: false, is_anonymized: false };
let dbError: unknown = null;
const chain = { select() { return this; }, eq() { return this; }, async maybeSingle() { reads++; return { data: row, error: dbError }; } };
const ctx = { organizationId: org, contatoDoTurno: contact, supabase: { from(name: string) { assert.equal(name, "contacts"); return chain; } } } as unknown as McpContext;
const now = Date.parse("2026-10-11T20:00:00Z");
const item = { fornecedor: "Mega Eletrônicos", codigo: "123", nome: "Perfume de teste EDT 100 ml", marca: "Marca", versao: "EDT", variante: null, volume_ml: 100, apresentacao: "não confirmada", imagem_url: "https://resource.megaeletronicos.com/teste.webp", fonte: "https://www.megaeletronicos.com/producto/123/teste", consultado_em_utc: "2026-10-11T20:00:00Z", disponibilidade: "disponivel", quantidade_disponivel: null, preco_final_aprovado_brl: null, situacao_preco: "pendente_de_consulta_e_aprovacao" };
const result = { status: "opcoes_disponiveis", opcoes: [item], cobertura_integral_catalogo: false, detalhes_consultados_integralmente: true };
let payload: unknown = result;
const deps = { config: async () => config, now: () => now,
  fetch: (async (url: unknown, init: RequestInit) => {
    calls++; assert.equal(url, "http://deskcommcrm-mega-vpn:40100/v1/buscar");
    assert.equal(init.redirect, "error"); assert.deepEqual(JSON.parse(String(init.body)), { perfume: "Sauvage" });
    return new Response(JSON.stringify(payload));
  }) as typeof fetch,
};
describe.sequential("RB Mega: consulta restrita sem precos", () => {
 test("allowed_contact", async () => { const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { status?: string }).status, "opcoes_disponiveis"); assert.equal(calls, 1); });
 test("other_contact_before_network_and_db", async () => { const n = calls, d = reads; const r = await consultarMega({ perfume: "Sauvage" }, { ...ctx, contatoDoTurno: other }, deps); assert.equal((r as { permitido?: boolean }).permitido, false); assert.equal(calls, n); assert.equal(reads, d); });
 test("other_tenant_before_network", async () => { const n = calls; await consultarMega({ perfume: "Sauvage" }, { ...ctx, organizationId: other }, deps); assert.equal(calls, n); });
 test("missing_trusted_contact", async () => { const n = calls; await consultarMega({ perfume: "Sauvage" }, { ...ctx, contatoDoTurno: undefined }, deps); assert.equal(calls, n); });
 test("configuration_failure_no_network", async () => { const n = calls; const r = await consultarMega({ perfume: "Sauvage" }, ctx, { ...deps, config: async () => { throw new Error("secret must never be returned"); } }); assert.equal(calls, n); assert(!JSON.stringify(r).includes("secret must")); });
 test("db_failure_no_network", async () => { const n = calls; dbError = { message: "private" }; await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal(calls, n); dbError = null; });
 for (const change of [{ kind: "whatsapp_group" }, { is_blocked: true }, { is_anonymized: true }]) test("excluded_contact_" + Object.keys(change)[0], async () => { const n = calls; row = { id: contact, kind: "person", is_blocked: false, is_anonymized: false, ...change }; await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal(calls, n); });
 row = { id: contact, kind: "person", is_blocked: false, is_anonymized: false };
 test("personal_data_rejected", () => { assert(!termoDePerfume.safeParse("email@teste.invalid").success); assert(!termoDePerfume.safeParse("+55 99 99999-9999").success); assert(!termoDePerfume.safeParse("123456789").success); assert(!termoDePerfume.safeParse("http://site").success); });
 test("extra_price_and_page_removed", async () => { payload = { ...result, pagina: "RAW PAGE", custo: 85, opcoes: [{ ...item, custo_usd: 85, margem: 35 }] }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); const s = JSON.stringify(r); assert(!s.includes("custo")); assert(!s.includes("margem")); assert(!s.includes("RAW PAGE")); assert(!s.includes(config.authorization_token)); });
 test("unapproved_price_rejected", async () => { payload = { ...result, opcoes: [{ ...item, preco_final_aprovado_brl: 1 }] }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { permitido?: boolean }).permitido, false); });
 test("unavailable_option_rejected", async () => { payload = { ...result, opcoes: [{ ...item, disponibilidade: "indisponivel" }] }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { permitido?: boolean }).permitido, false); });
 test("external_image_rejected", async () => { payload = { ...result, opcoes: [{ ...item, imagem_url: "https://example.com/a.jpg" }] }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { permitido?: boolean }).permitido, false); });
 test("stale_response_rejected", async () => { payload = { ...result, opcoes: [{ ...item, consultado_em_utc: "2026-10-10T20:00:00Z" }] }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { permitido?: boolean }).permitido, false); });
 test("network_exception_sanitized", async () => { const r = await consultarMega({ perfume: "Sauvage" }, ctx, { ...deps, fetch: (async () => { throw new Error(config.authorization_token); }) as typeof fetch }); assert(!JSON.stringify(r).includes(config.authorization_token)); assert.equal((r as { permitido?: boolean }).permitido, false); });
 test("partial_search_not_all_out_of_stock", async () => { payload = { status: "sem_estoque_nos_anuncios_verificados", opcoes: [], cobertura_integral_catalogo: false, detalhes_consultados_integralmente: false }; const r = await consultarMega({ perfume: "Sauvage" }, ctx, deps); assert.equal((r as { permitido?: boolean }).permitido, false); });
});

describe("pacote próprio de perfumes",()=>{
 test("as duas capacidades entram somente no pacote próprio",async()=>{
  const {TOOLS_RB_ATACADO}=await import("../../lib/mcp/tools/catalogo/rb-atacado");
  assert.equal(TOOLS_RB_ATACADO.length,2);
  for(const tool of TOOLS_RB_ATACADO)assert.deepEqual(tool.pacotes,["perfumes_rb"]);
 });
});


test("RB tool schemas use provider-compatible patterns without weakening server validation", () => {
 for (const schema of [z.object(rbBuscarPerfumes.inputSchema), z.object(rbConsultarOrcamento.inputSchema), AGENT_TOOL_DEFS.send_message.inputSchema]) {
  const json = z.toJSONSchema(schema);
  function visit(value: unknown): void {
   if (!value || typeof value !== "object") return;
   for (const [key, item] of Object.entries(value)) {
    if (key === "pattern" && typeof item === "string") {
     assert(!/\\[pP]\{/.test(item), "Provider cannot interpret Unicode property escapes");
    }
    visit(item);
   }
  }
  visit(json);
 }
 for (const name of ["Sauvage", "Éclat d'Arpège 100 ml", "عطر 100 ml"]) assert(termoDePerfume.safeParse(name).success);
 for (const name of ["https://site.invalid", "nome@site.invalid", "+5541999999999", "Sauvage; SELECT 1", "123456789", "Sauvage 💳"]) assert(!termoDePerfume.safeParse(name).success);
});
