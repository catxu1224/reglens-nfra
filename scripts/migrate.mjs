import { createPool, migrate } from '../server/db.mjs';

const pool = createPool();
if (!pool) throw new Error('Set DATABASE_URL before running migrations.');
try {
  await migrate(pool);
  console.log('Database migrations complete.');
} finally {
  await pool.end();
}
