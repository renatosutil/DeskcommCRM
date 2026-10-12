# Ciclo curto da RB Atacado

Mudanças de prompt são rascunhos/versionamento nativo no Deskcomm; não exigem novas imagens. Antes de publicar código, executar os testes ligados à alteração e seus efeitos, corrigir localmente e agrupar a revisão. O pipeline ainda exige os cinco checks completos do mesmo commit para autorizar publicação; nenhuma aprovação é herdada de outro código.

Para cálculo e consulta: `python3 -B integracoes/rb-atacado/coletor/test-estimativa.py` e os testes de API/política quando esses contratos mudarem. Para preço/foto/envio: executar os arquivos RB relevantes com `pnpm vitest run`, incluindo restrição de contato e revalidação antes de enviar. Ambiente de testes deve usar fixtures e nunca enviar WhatsApp real. Mudança de prompt exige prova do comportamento afetado, sem repetir build.

Cada imagem tem cache GHA próprio. Camadas sem alteração podem ser reaproveitadas; o primeiro preenchimento do cache ainda custa o build normal. Não foi implementado reaproveitamento de aprovações entre commits nem publicação seletiva com imagens de revisões diferentes.

Upload tem no máximo três tentativas e só substitui arquivos da própria revisão enquanto a release ainda é rascunho. Releases publicadas nunca são modificadas. Falha persistente mantém a release em draft e impede deploy.

Na interface GitHub: Actions → RB imagens verificadas v1.76.0 → execução → job construir → etapas de build/upload. O ganho de tempo só pode ser informado após medir execução real com cache.

Para desfazer: reverter o commit que alterou `.github/workflows/rb-release.yml` e `scripts/rb-enviar-artefatos.py`, revisar o diff e publicar pelo fluxo normal. O backup do workflow anterior está na pasta protegida de preparação; nenhum arquivo de produção foi alterado.

## Fluxo implementado

1. Trabalhar e agrupar mudanças em `rb-trabalho-v1.76.0`. Cada push roda apenas `RB ciclo rápido de desenvolvimento`, sem imagens ou deploy. Jobs rápidos de revisões substituídas são cancelados.
2. Planejar localmente com `python3 -B scripts/rb-ciclo-rapido.py --base origin/rb-atacado-v1.76.0`; executar no ambiente de testes com a opção `--executar`. O mapa cobre Python, ferramentas RB, fotos/envio/opt-out e conserva typecheck para alterações TS. Caminho não mapeado amplia para unidade completa e pede revisão adicional. Banco, UI e empacotamento continuam exigindo os testes específicos na candidata; o ciclo rápido não os substitui.
3. Quando os ajustes terminarem, enviar uma única candidata a `rb-atacado-v1.76.0`: `git push origin HEAD:rb-atacado-v1.76.0`. O PR roda os cinco workflows completos.
4. Só depois dos cinco PASS do mesmo SHA, publicar `HEAD:rb-publicar-v1.76.0`. A guarda existente continua impedindo publicação a partir do ciclo rápido.

GitHub → Actions → RB ciclo rápido de desenvolvimento mostra os testes selecionados. O branch de trabalho não deve ser aberto como outro PR durante a iteração: PR dispara a rodada completa. Nenhum segredo de produção é disponibilizado ao workflow rápido. Alterações de prompt continuam no fluxo nativo do CRM.

O diretório `.github` e os scripts exclusivos de CI ficam fora do contexto Docker. Assim, editar workflow/testes não copia metadados sem uso para o worker. Isso não implementa imagens de múltiplas revisões: os quatro componentes continuam com identidade verificável da candidata.

Rollback desta otimização: reverter o commit do ciclo rápido e voltar a trabalhar na branch candidata; isso não exige restart nem altera configurações do cliente.

## Publicação seletiva implementada

A release publica `rb-release.json`: candidata, revisão real, checksum, identidade e impressão das entradas de cada um dos quatro componentes. Apenas os componentes com entradas alteradas entram na matriz de build. Os demais referenciam artefatos imutáveis de uma release anterior publicada, cuja fonte precisa ser ancestral e compatível com a candidata. Nenhuma imagem recebe uma revisão nova por reaproveitamento.

A seleção é conservadora e segue COPY/ADD e o contexto dos Dockerfiles: app/worker usam COPY amplo e podem mudar juntos; scheduler e coletor usam entradas explícitas. Padrões glob não comprovados, sintaxe desconhecida, symlinks e bind mounts ampliam entradas em vez de ocultar alterações. Isso pode reconstruir mais componentes, mas nunca considera irrelevante um caminho desconhecido.

Para obrigar a reconstrução das quatro imagens, GitHub → Settings → Secrets and variables → Actions → Variables → New repository variable: nome `RB_FORCE_REBUILD`, valor `true`. Remover/desabilitar esse valor após a publicação desejada. Essa variável é uma opção pública, não uma credencial. É útil também para atualizar bases Docker quando não há mudança de código.

A implantação seletiva usa `scripts/rb-implantar-seletivo.py` no checkout da candidata. A ação `baixar --tag <release> --repo <checkout>` valida CI, manifestos, checksums, gzip e identidade OCI. `planejar --recibo <verified.json> --repo <checkout>` mostra os serviços a trocar sem recriá-los. `implantar` exige agente pausado e restrito, env 600, saúde da cobrança e recursos mínimos; cria recibo novo 600 com as imagens anteriores. `rollback --recibo <before.json> --repo <checkout>` restaura somente os serviços da sessão, preserva volumes e deixa o agente pausado para revisão. Use o recibo salvo pela mesma execução, nunca a função rollback do helper antigo, que volta às imagens oficiais e para o coletor.

A rotina só recria serviços cuja identidade de imagem mudou. Mantém IDs de contêineres não afetados, Caddy, cobrança, Redis, WAHA e VPN. Não modifica Compose existente, env, firewall, banco, volumes ou política de atendimento. Os overrides novos ficam em pasta datada exclusiva. Publicação seletiva não dispensa os cinco workflows completos aprovados do SHA candidato.

Para desfazer o pipeline seletivo, reverta o commit no GitHub; releases já publicadas continuam imutáveis. Para desfazer uma implantação, use o recibo da sessão e valide a versão do agente antes de retomar. O manifesto identifica revisões diferentes corretamente; uma imagem não reconstruída não tem a revisão da candidata.

Testes selecionados e checagem de tipos ficam em passos separados. Para execução local, `--fase testes` roda somente os testes e `--fase tipos` roda somente typecheck; sem a opção, ambas as fases são executadas. O runner GitHub usa para typecheck o mesmo `NODE_OPTIONS=--max-old-space-size=6144` do CI oficial. Não executar essa checagem pesada na VPS de produção com esse orçamento: não há alteração da RAM, swap ou dos contêineres de produção.
