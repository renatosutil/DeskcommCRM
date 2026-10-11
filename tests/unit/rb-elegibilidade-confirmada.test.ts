import { beforeEach, describe, expect, it, vi } from 'vitest';
import type pg from 'pg';
const consulta = vi.hoisted(() => vi.fn());
vi.mock('../../lib/ai/elegibilidade/consulta-pg', () => ({
 decidirElegibilidadeDaConversa: consulta,
}));
import { consultarElegibilidadeConfirmada } from '../../lib/ai/elegibilidade/consulta-confirmada';
const pool = {} as pg.Pool;
const input = { organizationId: 'org-fixture', conversationId: 'conversation-fixture',
 agora: new Date('2026-10-11T00:00:00Z'), ttlMs: 1000 };
describe('gate confirmado antes da IA', () => {
 beforeEach(() => { consulta.mockReset(); });
 it('contato permitido conserva decisão positiva confirmada', async () => {
  consulta.mockResolvedValue({ permite: true, motivo: 'numero_de_teste', bloqueioPorAllowlist: false });
  expect(await consultarElegibilidadeConfirmada(pool,input)).toEqual({
   permite: true, motivo: 'numero_de_teste', bloqueioPorAllowlist: false, consultaConfirmada: true });
 });
 it('outro contato conserva veto confirmado', async () => {
  consulta.mockResolvedValue({ permite: false, motivo: 'fora_da_lista_de_teste', bloqueioPorAllowlist: true });
  expect(await consultarElegibilidadeConfirmada(pool,input)).toMatchObject({ permite:false, consultaConfirmada:true });
 });
 it('conversa não localizada nunca autoriza', async () => {
  consulta.mockResolvedValue(null);
  expect(await consultarElegibilidadeConfirmada(pool,input)).toMatchObject({ permite:false, consultaConfirmada:false });
 });
 it('falha de banco nunca autoriza nem reproduz o erro', async () => {
  consulta.mockRejectedValue(new Error('fixture-privada'));
  const result=await consultarElegibilidadeConfirmada(pool,input);
  expect(result).toMatchObject({ permite:false, consultaConfirmada:false });
  expect(JSON.stringify(result)).not.toContain('fixture-privada');
 });
 it('não troca organização/conversa e faz uma única leitura', async () => {
  consulta.mockResolvedValue(null);
  await consultarElegibilidadeConfirmada(pool,input);
  expect(consulta).toHaveBeenCalledTimes(1);
  expect(consulta).toHaveBeenCalledWith(pool,input);
 });
});
