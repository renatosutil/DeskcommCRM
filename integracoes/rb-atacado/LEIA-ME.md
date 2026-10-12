# RB Atacado — revisão privada sobre v1.76.0
Estado medido: preparar e testar; implantação depende dos cinco workflows completos do mesmo commit.
Não muda baseline, provedor/modelo, proxy, sessão WhatsApp, telefone permitido ou outras stacks.

## Comportamento e superfície
IA › Agentes › agente › Configuração: prompt, ferramentas e modelo; Histórico: versões.
Salvar grava rascunho. Publicar torna a versão ativa pelo RPC nativo.
As ferramentas rb_buscar_perfumes e rb_consultar_orcamento são selecionadas individualmente.
Não entram nos pacotes gerais nem removem ferramentas nativas.
Respostas RB são enums montados pelo servidor; texto livre deste agente não é enviado.
Fotos levam nome, concentração, ml e apresentação verificados, sem preço pendente.
Preços só são montados por ferramenta determinística com aprovação comercial válida.
Sem aprovação, sem consulta confiável ou sem versão/ml confirmados: solicitar informação ou atendimento humano.
Fora do contato privado: nenhum turno, sentimento ou derivação de mídia de IA.
O controle privado é código/configuração protegida, sem editor próprio na interface.

## Segurança
RB_ATACADO_ENABLED ausente/0 mantém o núcleo comum sem dependência nova.
Com 1, configuração ausente, erro de leitura e elegibilidade desconhecida falham fechado.
Configuração 600 contém escopo privado e autenticação da API; app tem arquivo legível apenas pelo UID de runtime.
Conversão e formação do preço ficam em pricing.json 600 exclusivamente no coletor/CLI, fora do modelo e imagem.
Arquivos de orçamento e aprovações 600, diretório 700. Aprovação interativa exige validade explícita.
Fonte de disponibilidade: página principal da Mega; JSON-LD contraditório não prevalece.
Quantidade em estoque não é conhecida. Resultado vazio dos anúncios verificados não prova todo o catálogo.
Imagem e orçamento são revalidados antes do envio e retry, sem fragmentar ou adulterar o texto aprovado.

## Publicação e reversão
O CI oficial do fork valida unidade, invariantes, E2E, desempenho e imagens.
rb-release publica arquivos OCI/checksums/identidades para a VPS AMD64 somente com todos os workflows aprovados.
Baseline tem comparação byte a byte com o commit oficial v1.76.0.
Não fazer merge da base fixada sobre main, não executar baseline/migrations, não construir imagem de produção na VPS.
Override mantém serviços, IP do app, redes e volumes originais; acrescenta somente rede do coletor.
Implantação gradual: API isolada, app, worker, scheduler. Demais serviços não são recriados.
Reversão de código: usar somente os três Compose originais e imagens oficiais já presentes.
Reversão do agente: criar rascunho copiando a versão anterior no Histórico e publicar pelo fluxo nativo.
Backup privado anterior preservado fora do Git; nunca publicar conteúdo.

## Sistema vivo e destino
Destino: núcleo opt-in + infraestrutura privada de consulta; sem ativação, operação comum preservada.
Entrada: turno nativo e mídia recebida; saída: MCP e send_message pelo ledger/before-send nativos.
Registro: mensagem, execução e ferramentas nas telas nativas; aprovações ficam no ledger privado.
Porta: IA › Agentes; conversa e timeline no Inbox. Aprovação: CLI interativo SSH, sem tela nesta revisão.
Anti-morte: recusa explícita e passagem ao humano; não promete que já contatou alguém.
Continuidade: handoff nativo e retomada nativa preservados.
Laço de retorno: revogação, validade, preço alterado e estoque desabilitam a cotação antes de cada envio.
Dívida declarada: CLI de aprovação não tem editor visual; não anunciar consulta/valor aprovado inexistente.
Prova ainda exigida: testes do novo commit, imagens CI e protocolo implantado; WhatsApp real exige mensagem do aparelho.
