import { createApp } from './app.mjs';
import { createPool, migrate } from './db.mjs';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const pool = createPool();
if (pool) {
  await migrate(pool);
  if (process.env.SEED_ON_START !== '0') {
    const { stdout } = await promisify(execFile)(process.execPath, ['scripts/seed.mjs']);
    console.log(stdout.trim());
  }
}

const port = Number(process.env.PORT || 4173);
const server = createApp(pool).listen(port, '0.0.0.0', () => {
  console.log(`RegLens listening on port ${port}`);
});

async function shutdown() {
  server.close();
  if (pool) await pool.end();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
