# Ciclo curto da RB Atacado

Mudanças de prompt são rascunhos/versionamento nativo no Deskcomm; não exigem novas imagens. Antes de publicar código, executar os testes ligados à alteração e seus efeitos, corrigir localmente e agrupar a revisão. O pipeline ainda exige os cinco checks completos do mesmo commit para autorizar publicação; nenhuma aprovação é herdada de outro código.

Para cálculo e consulta: `python3 -B integracoes/rb-atacado/coletor/test-estimativa.py` e os testes de API/política quando esses contratos mudarem. Para preço/foto/envio: executar os arquivos RB relevantes com `pnpm vitest run`, incluindo restrição de contato e revalidação antes de enviar. Ambiente de testes deve usar fixtures e nunca enviar WhatsApp real. Mudança de prompt exige prova do comportamento afetado, sem repetir build.

Cada imagem tem cache GHA próprio. Camadas sem alteração podem ser reaproveitadas; o primeiro preenchimento do cache ainda custa o build normal. Não foi implementado reaproveitamento de aprovações entre commits nem publicação seletiva com imagens de revisões diferentes.

Upload tem no máximo três tentativas e só substitui arquivos da própria revisão enquanto a release ainda é rascunho. Releases publicadas nunca são modificadas. Falha persistente mantém a release em draft e impede deploy.

Na interface GitHub: Actions → RB imagens verificadas v1.76.0 → execução → job construir → etapas de build/upload. O ganho de tempo só pode ser informado após medir execução real com cache.

Para desfazer: reverter o commit que alterou `.github/workflows/rb-release.yml` e `scripts/rb-enviar-artefatos.py`, revisar o diff e publicar pelo fluxo normal. O backup do workflow anterior está na pasta protegida de preparação; nenhum arquivo de produção foi alterado.
