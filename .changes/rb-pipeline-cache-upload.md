---
impacto: nada_mudou
secao: corrigido
titulo: Cache de imagens e upload protegido no pipeline RB
---
Destino: infraestrutura do fork RB. Cache por componente reaproveita camadas sem dispensar as cinco aprovações do mesmo commit. Upload aceita até três tentativas, reconfirma rascunho e revisão antes de cada envio e nunca altera release publicada. Não muda runtime, baseline ou serviços do cliente.
