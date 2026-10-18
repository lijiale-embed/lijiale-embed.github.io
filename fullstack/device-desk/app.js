import express from 'express';
import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const deviceStates = ['online', 'offline', 'warning'];
const priorities = ['low', 'medium', 'high'];
const transitions = { open: ['in_progress'], in_progress: ['closed'], closed: [] };
class ApiError extends Error {
  constructor(status, code, message) { super(message); Object.assign(this, { status, code }); }
}
const fail = (status, code, message) => { throw new ApiError(status, code, message); };
function object(value) {
  if (!value || Array.isArray(value) || typeof value !== 'object') fail(400, 'VALIDATION', '请求体必须是 JSON 对象');
  return value;
}
function text(value, label, max, optional = false) {
  if (optional && value === undefined) return '';
  if (typeof value !== 'string' || (!optional && !value.trim()) || value.trim().length > max)
    fail(400, 'VALIDATION', `${label}必填且最长 ${max} 字符`);
  return value.trim();
}
function choice(value, values, label) {
  if (!values.includes(value)) fail(400, 'VALIDATION', `${label}应为 ${values.join(' / ')}`);
  return value;
}
function sensor(value, label, min, max) {
  if (value === null || value === undefined) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max)
    fail(400, 'VALIDATION', `${label}应为 ${min} 到 ${max} 的数字或 null`);
  return value;
}
function id(value) {
  if (!/^[1-9]\d*$/.test(String(value)) || !Number.isSafeInteger(Number(value))) fail(400, 'VALIDATION', '编号应为正整数');
  return Number(value);
}
function deviceInput(body) {
  const b = object(body);
  const code = text(b.code, '设备编号', 32);
  if (!/^[A-Za-z0-9_-]+$/.test(code)) fail(400, 'VALIDATION', '设备编号只能使用字母、数字、下划线和连字符');
  return [code, text(b.name, '设备名称', 80), choice(b.status, deviceStates, '设备状态'),
    sensor(b.temperature, '模拟温度', -50, 150), sensor(b.humidity, '模拟湿度', 0, 100)];
}

export function createApp({ dbPath = ':memory:', seed = false, logger = console.log } = {}) {
  if (dbPath !== ':memory:') mkdirSync(dirname(dbPath), { recursive: true });
  const db = new DatabaseSync(dbPath);
  db.exec(`PRAGMA foreign_keys = ON; PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS devices (
      id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('online','offline','warning')),
      temperature REAL CHECK(temperature BETWEEN -50 AND 150),
      humidity REAL CHECK(humidity BETWEEN 0 AND 100), updated_at TEXT NOT NULL
    ) STRICT;
    CREATE TABLE IF NOT EXISTS tickets (
      id INTEGER PRIMARY KEY, device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE RESTRICT,
      title TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL CHECK(priority IN ('low','medium','high')),
      status TEXT NOT NULL CHECK(status IN ('open','in_progress','closed')),
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, closed_at TEXT
    ) STRICT;
    CREATE INDEX IF NOT EXISTS tickets_device_idx ON tickets(device_id);`);
  if (seed && db.prepare('SELECT count(*) AS n FROM devices').get().n === 0) {
    db.exec('BEGIN');
    try {
      const insert = db.prepare('INSERT INTO devices(code,name,status,temperature,humidity,updated_at) VALUES(?,?,?,?,?,?)');
      const now = new Date().toISOString();
      const first = insert.run('SIM-ESP32-01', '环境采集节点（模拟）', 'warning', 38.6, 62, now).lastInsertRowid;
      insert.run('SIM-STM32-02', '温控控制器（模拟）', 'online', 26.4, 48, now);
      insert.run('SIM-GATEWAY-03', '串口网关（模拟）', 'offline', null, null, now);
      db.prepare('INSERT INTO tickets(device_id,title,description,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)')
        .run(first, '模拟温度偏高，检查采样配置', '人工创建的练习工单；未连接真实传感器。', 'high', 'open', now, now);
      db.exec('COMMIT');
    } catch (error) { db.exec('ROLLBACK'); db.close(); throw error; }
  }
  const app = express();
  app.disable('x-powered-by');
  app.use((req, res, next) => {
    const start = Date.now();
    res.set('X-Content-Type-Options', 'nosniff');
    if (req.path.startsWith('/api/')) res.set('Cache-Control', 'no-store');
    res.on('finish', () => logger(JSON.stringify({ method: req.method, path: req.path, status: res.statusCode, ms: Date.now() - start })));
    // The demo binds to loopback. Block browser cross-origin writes; no authentication is claimed.
    if (!['GET', 'HEAD', 'OPTIONS'].includes(req.method) && req.get('origin') && req.get('origin') !== `${req.protocol}://${req.get('host')}`)
      return next(new ApiError(403, 'ORIGIN', '仅允许同源写入'));
    next();
  });
  app.use(express.json({ limit: '16kb', strict: false }));
  app.use('/api', (req, res, next) => {
    if (['POST', 'PUT', 'PATCH'].includes(req.method) && !req.is('application/json'))
      return next(new ApiError(415, 'CONTENT_TYPE', '请使用 application/json'));
    next();
  });
  const ok = (res, data, status = 200) => res.status(status).json({ data });
  const getDevice = (value) => {
    const row = db.prepare('SELECT * FROM devices WHERE id=?').get(id(value));
    return row || fail(404, 'NOT_FOUND', '设备不存在');
  };
  const getTicket = (value) => {
    const row = db.prepare('SELECT t.*, d.code AS device_code, d.name AS device_name FROM tickets t JOIN devices d ON d.id=t.device_id WHERE t.id=?').get(id(value));
    return row || fail(404, 'NOT_FOUND', '工单不存在');
  };
  function filters(req, states) {
    const q = text(req.query.q ?? '', '搜索词', 100, true);
    const status = req.query.status ?? '';
    if (status !== '') choice(status, states, '筛选状态');
    return { q: q.toLowerCase(), status };
  }
  app.get('/api/health', (req, res) => ok(res, { status: 'ok', simulated: true }));
  app.get('/api/devices', (req, res) => {
    const { q, status } = filters(req, deviceStates);
    ok(res, db.prepare('SELECT * FROM devices ORDER BY id DESC').all().filter(d =>
      (!status || d.status === status) && `${d.name} ${d.code}`.toLowerCase().includes(q)));
  });
  app.post('/api/devices', (req, res) => {
    const result = db.prepare('INSERT INTO devices(code,name,status,temperature,humidity,updated_at) VALUES(?,?,?,?,?,?)')
      .run(...deviceInput(req.body), new Date().toISOString());
    ok(res, getDevice(result.lastInsertRowid), 201);
  });
  app.get('/api/devices/:id', (req, res) => ok(res, getDevice(req.params.id)));
  app.put('/api/devices/:id', (req, res) => {
    const d = getDevice(req.params.id);
    db.prepare('UPDATE devices SET code=?,name=?,status=?,temperature=?,humidity=?,updated_at=? WHERE id=?')
      .run(...deviceInput(req.body), new Date().toISOString(), d.id);
    ok(res, getDevice(d.id));
  });
  app.delete('/api/devices/:id', (req, res) => {
    const d = getDevice(req.params.id);
    if (db.prepare('SELECT id FROM tickets WHERE device_id=? LIMIT 1').get(d.id)) fail(409, 'HAS_TICKETS', '设备有关联工单，保留历史记录，无法删除');
    db.prepare('DELETE FROM devices WHERE id=?').run(d.id);
    ok(res, { id: d.id, deleted: true });
  });
  app.get('/api/tickets', (req, res) => {
    const { q, status } = filters(req, Object.keys(transitions));
    const deviceId = req.query.device_id === undefined ? null : id(req.query.device_id);
    ok(res, db.prepare('SELECT t.*,d.code AS device_code,d.name AS device_name FROM tickets t JOIN devices d ON d.id=t.device_id ORDER BY t.id DESC').all()
      .filter(t => (!status || t.status === status) && (deviceId === null || t.device_id === deviceId) && `${t.title} ${t.device_code} ${t.description}`.toLowerCase().includes(q)));
  });
  app.post('/api/tickets', (req, res) => {
    const b = object(req.body), d = getDevice(b.device_id);
    const title = text(b.title, '工单标题', 120), description = text(b.description, '描述', 2000, true);
    const priority = choice(b.priority, priorities, '优先级'), now = new Date().toISOString();
    const result = db.prepare('INSERT INTO tickets(device_id,title,description,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)')
      .run(d.id, title, description, priority, 'open', now, now);
    ok(res, getTicket(result.lastInsertRowid), 201);
  });
  app.get('/api/tickets/:id', (req, res) => ok(res, getTicket(req.params.id)));
  app.patch('/api/tickets/:id', (req, res) => {
    const t = getTicket(req.params.id), b = object(req.body);
    choice(b.status, Object.keys(transitions), '工单状态');
    if (!transitions[t.status].includes(b.status)) fail(409, 'INVALID_TRANSITION', '工单只能从待处理 → 处理中 → 已关闭，不可跳过或重开');
    const now = new Date().toISOString();
    db.prepare('UPDATE tickets SET status=?,updated_at=?,closed_at=? WHERE id=?').run(b.status, now, b.status === 'closed' ? now : null, t.id);
    ok(res, getTicket(t.id));
  });
  app.use('/api', (req, res) => fail(404, 'NOT_FOUND', '接口不存在'));
  app.use(express.static(fileURLToPath(new URL('./public/', import.meta.url))));
  app.use((req, res) => fail(404, 'NOT_FOUND', '页面不存在'));
  app.use((error, req, res, next) => {
    let { status = 500, code = 'INTERNAL', message } = error;
    if (error.type === 'entity.parse.failed') { status = 400; code = 'INVALID_JSON'; message = 'JSON 格式错误'; }
    if (error.type === 'entity.too.large') { status = 413; code = 'TOO_LARGE'; message = '请求体超过 16 KB'; }
    if (error.message?.includes('UNIQUE constraint failed: devices.code')) { status = 409; code = 'DUPLICATE_CODE'; message = '设备编号已存在'; }
    if (status >= 500) { logger(JSON.stringify({ error: error.message, path: req.path })); message = '服务内部错误，请查看服务日志'; }
    res.status(status).json({ error: { code, message } });
  });
  return { app, db, close: () => db.close() };
}
