import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
test('PBOC import refuses a snapshot without matching complete-history proof',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'pboc-readiness-'));
 try {
  const source=await readFile(new URL('../seeds/pboc_penalties.csv',import.meta.url),'utf8');
  const path=join(directory,'changed.csv');await writeFile(path,source+'\n');
  const result=spawnSync(process.execPath,['scripts/seed.mjs','--regulator=pboc','--require-complete','--check'],{cwd:new URL('../',import.meta.url),env:{...process.env,SEED_FILE:path},encoding:'utf8'});
  assert.notEqual(result.status,0);assert.match(result.stderr,/pboc_complete_history|full-history manifest/);
 } finally {await rm(directory,{recursive:true,force:true})}
});
