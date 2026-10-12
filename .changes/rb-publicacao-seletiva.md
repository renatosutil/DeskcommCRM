---
impacto: nada_mudou
secao: adicionado
titulo: Publicação seletiva de imagens no fork RB
---
Destino: infraestrutura. Matriz de publicação reconstrói somente componentes com entradas alteradas e registra revisão real, checksum e identidade de cada imagem em manifesto verificável. Reaproveitamento exige release anterior publicada, fonte ancestral e mesmas entradas; os cinco checks completos do candidato continuam obrigatórios. Implantação e rollback preservam serviços não afetados, volumes, banco e proxy. Opção pública permite forçar rebuild de todas as bases.
