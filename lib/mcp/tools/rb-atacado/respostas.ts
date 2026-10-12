import { z } from 'zod';
export const RESPOSTAS_RB = {
 saudacao:'Oi! Sou o assistente virtual da RB Atacado. Você procura algum perfume?',
 perguntar_perfume:'Qual perfume você procura?',
 perguntar_marca:'Qual é a marca do perfume?',
 perguntar_versao:'Qual é a versão ou concentração: EDT, EDP, Parfum ou outra?',
 confirmar_identificacao:'Pode confirmar o nome e a versão/concentração desse perfume?',
 perguntar_ml:'Qual é o volume em ml?',
 perguntar_quantidade:'Qual quantidade você deseja?',
 pedir_foto:'Pode enviar uma foto mais nítida da frente e do verso do frasco ou da caixa, mostrando o nome e os ml?',
 escolher_opcao:'Qual dessas opções corresponde ao perfume que você procura?',
 preco_pendente:'O valor precisa de consulta e aprovação da RB Atacado antes de preparar o orçamento.',
 consulta_indisponivel:'Não consegui confirmar o valor e a disponibilidade agora. O orçamento fica pendente de consulta pela RB Atacado.',
 desconto_pendente:'Desconto e condições por quantidade dependem da avaliação da RB Atacado.',
 prazo_pendente:'Disponibilidade para a quantidade e prazo de entrega dependem de confirmação comercial.',
 pagamento_pendente:'Por enquanto, não faça o pagamento. Reserva, confirmação da compra e instruções de pagamento dependem de confirmação comercial.',
 custo_privado:'Posso informar apenas o valor final aprovado para o cliente.',
 atendimento_humano:'As condições precisam ser confirmadas por uma pessoa da RB Atacado.',
 agradecimento:'Por nada! Se precisar de um orçamento de perfumes, estou por aqui.',
 cordial:'Tudo bem!',
 optout_respeitado:'Certo. O atendimento automático ficará interrompido.',
} as const;
export const respostaRbSchema=z.enum(Object.keys(RESPOSTAS_RB) as [
 keyof typeof RESPOSTAS_RB,...(keyof typeof RESPOSTAS_RB)[],
]);
export function textoRespostaRb(input:unknown):string {
 return RESPOSTAS_RB[respostaRbSchema.parse(input)];
}
