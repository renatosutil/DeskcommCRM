"""Seleciona testes de desenvolvimento; não autoriza publicação nem acessa credenciais."""
import argparse,json,os,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
PIPELINE_TESTS=['scripts/rb-ciclo-rapido.test.py','scripts/rb-enviar-artefatos.test.py','scripts/rb-verificar-ci.test.py']
COLLECTOR_TESTS=['integracoes/rb-atacado/coletor/test-'+n+'.py' for n in ('aprovacoes','api-mega','politica','estimativa')]
RB_TESTS=['tests/unit/rb-'+n+'.test.ts' for n in ('elegibilidade-confirmada','entrega','estimativa','estoque-verificado','foto','mega','orcamento','provas','publicacao-verificada','sentimento')]
SEND_TESTS=['tests/unit/'+n+'.test.ts' for n in ('before-send-chain-shape','opt-out-deteccao','pre-go-live-novos-canais','branding')]

def planejar(paths):
    paths=sorted(set(paths));python=set();ts=set();related=[];full=False;critical=False
    for p in paths:
        if p.startswith(('docs/','.changes/')) or p.endswith('.md'):continue
        if p.startswith(('scripts/rb-ciclo-rapido','scripts/rb-enviar-artefatos','scripts/rb-verificar-ci')) or p in ('.github/workflows/rb-rapido.yml','.github/workflows/rb-release.yml'):
            python.update(PIPELINE_TESTS)
        elif p.startswith('integracoes/rb-atacado/coletor/'):
            python.update(COLLECTOR_TESTS)
        elif p.startswith(('lib/mcp/tools/rb-atacado','tests/unit/rb-')) and p.endswith(('.ts','.tsx')):
            ts.update(RB_TESTS);ts.add('tests/unit/branding.test.ts')
        elif p in ('lib/agent-engine/agent/inbound-turn.ts','edge/crm/send-message.ts'):
            ts.update(RB_TESTS+SEND_TESTS);related.append(p);critical=True
        elif p in ('.dockerignore','integracoes/rb-atacado/Dockerfile.coletor'):
            python.update(PIPELINE_TESTS+COLLECTOR_TESTS);critical=True
        else:
            # Caminho sem mapa não ganha verde parcial: inclui unidade completa e sinaliza revisão ampliada.
            full=True;critical=True
            if p.startswith(('supabase/','Dockerfile','docker/','hostgator-setup-kit/')) or p.startswith('docker-compose'):
                python.update(PIPELINE_TESTS)
            if p.endswith(('.ts','.tsx')):related.append(p)
    commands=[['python3','-B',p] for p in sorted(python)]
    if full:commands.append(['pnpm','test:unit'])
    elif ts:commands.append(['pnpm','vitest','run',*sorted(ts)])
    if related:commands.append(['pnpm','vitest','related','--run',*related])
    if ts or related or full:commands.append(['pnpm','typecheck'])
    return {'commands':commands,'needs_node':bool(ts or related or full),'requires_expanded_review':critical,'publication_authorized':False,'changed_files':paths}

def changed(base):
    sha=subprocess.check_output(['git','rev-parse','--verify','--end-of-options',base+'^{commit}'],cwd=ROOT,text=True).strip()
    raw=subprocess.check_output(['git','diff','--name-only','-z',sha,'--'],cwd=ROOT)
    return [p for p in raw.decode().split('\0') if p]

def execute(plan,run=subprocess.run):
    for cmd in plan['commands']:
        result=run(cmd,cwd=ROOT)
        if result.returncode:raise SystemExit(result.returncode)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--base',default='origin/rb-atacado-v1.76.0');ap.add_argument('--executar',action='store_true');ap.add_argument('--github-output',action='store_true');args=ap.parse_args()
    plan=planejar(changed(args.base))
    if args.github_output:
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('needs_node='+str(plan['needs_node']).lower()+'\n')
    print(json.dumps(plan,ensure_ascii=False),flush=True)
    if args.executar:execute(plan)
    print('CICLO_RAPIDO: não substitui validação completa nem autoriza deploy.',flush=True)
