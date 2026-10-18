import { createApp } from './app.js';
import { fileURLToPath } from 'node:url';
const port = Number(process.env.PORT || 3000);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT 必须为 1–65535');
const instance = createApp({
  dbPath: process.env.DB_PATH || fileURLToPath(new URL('./data/device-desk.sqlite', import.meta.url)),
  seed: process.argv.includes('--seed')
});
const server = instance.app.listen(port, '127.0.0.1', () => console.log(`Device Desk（全部为模拟数据）: http://127.0.0.1:${port}`));
server.on('error', error => { console.error(error.message); instance.close(); process.exitCode = 1; });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => { instance.close(); process.exit(0); }));
