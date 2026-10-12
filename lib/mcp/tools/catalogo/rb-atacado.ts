import { declararTools } from "./tipos";
export const TOOLS_RB_ATACADO = declararTools([{
  name: "rb_buscar_perfumes", category: "read", rotulo: "Consultar perfumes na Mega",
  explicacao: "Mostra variantes de perfumes com disponibilidade confirmada na Mega Eletrônicos. O cliente escolhe a versão e o volume; o preço depende da aprovação comercial.",
  oQueToca: "Perfumes e disponibilidade", risco: "seguro", pacotes: ["perfumes_rb"],
}, {
  name: "rb_consultar_orcamento", category: "read", rotulo: "Conferir orçamento aprovado",
  explicacao: "Confere o orçamento aprovado para o perfume e a quantidade exatos, incluindo validade e disponibilidade atual, sem revelar o custo de compra ao cliente.",
  oQueToca: "Orçamentos aprovados", risco: "seguro", pacotes: ["perfumes_rb"],
}]);
