import {it,expect} from 'vitest';
import {spawnSync} from 'node:child_process';
it('não publica com CI incompleto, falho, antigo ou de outro commit',()=>{
 const r=spawnSync('python3',['-B','scripts/rb-verificar-ci.test.py'],{cwd:process.cwd(),encoding:'utf8'});
 expect(r.status,r.stderr).toBe(0);
 expect(r.stderr).toContain('Ran 9 tests');
});
