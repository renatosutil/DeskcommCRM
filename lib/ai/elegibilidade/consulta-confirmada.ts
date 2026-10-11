import type pg from 'pg';
import { decidirElegibilidadeDaConversa } from './consulta-pg';
import type { DecisaoDeElegibilidade } from './gate';

type Resultado = DecisaoDeElegibilidade & { consultaConfirmada: boolean };

/** Nenhuma falha de leitura autoriza consumo de IA. Não registra erro/identidade. */
export async function consultarElegibilidadeConfirmada(
  pool: pg.Pool,
  input: Parameters<typeof decidirElegibilidadeDaConversa>[1],
): Promise<Resultado> {
  try {
    const resultado = await decidirElegibilidadeDaConversa(pool, input);
    if (resultado !== null) return { ...resultado, consultaConfirmada: true };
  } catch {
    // Falha transitória: o drain conserva o evento para tentar novamente.
  }
  return { permite: false, motivo: 'sem_autorizacao',
    bloqueioPorAllowlist: true, consultaConfirmada: false };
}
