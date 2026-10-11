PREPARADO, NÃO IMPLANTADO
Base: v1.76.0 / 3101682cdc9d1448304f6c613349281b2db6857d.
Guardas de elegibilidade: falha de leitura interrompe turno e adia evento.
Fotos: código da Mega retornado por consulta, imagem verificada, Storage privado e envio nativo.
Orçamento: orcamento_mega fornece código e quantidade; texto montado pelo código,
sem custo/cotação/margem. Cada chamada da borda e beforeSend reconsulta a aprovação.
Preço alterado, revogação, expiração ou indisponibilidade recusam o envio.
A mensagem do orçamento não pode ser dividida nem modificada pela cadeia nativa.
O fluxo deve ser testado com disclosure/assinatura e configurações reais.
O guard de entrega exige RB_ATACADO_ENABLED=1 no app e worker, configuração privada
600 montada em /opt/rb-atacado/config.json e API privada acessível. Nada disso
foi ativado. Nenhuma ferramenta nova foi publicada na versão atual do agente.
A defesa complementar contra preços em texto livre NÃO é prova completa contra
todos os formatos monetários ou valores escritos por extenso. Exige revisão
dos guardrails comerciais e testes adversariais antes de liberar.
PENDENTE: typecheck completo, suíte completa, E2E, revisão de todas as rotas de
envio/prospecção e publicação CI. Não implantar enquanto houver pendências.
GitHub: branch só na cópia local da VPS; nenhum push/autenticação configurados.
Nenhum segredo, .env ou estado WARP incluído.
Interface atual permanece inalterada. Novos argumentos/guardas são alteração
de código, não configuração disponível na interface. Aprovação ainda é utilitário
interativo SSH preparado; não executar antes de configurar/validar a integração.
Reversão: não implantar; versões de preparação anteriores preservadas.
