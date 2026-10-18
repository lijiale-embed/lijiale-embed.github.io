import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createApp } from '../app.js';

async function fixture(t, options = {}) {
  const instance = createApp({ logger: () => {}, ...options });
  const server = instance.app.listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  t.after(async () => { await new Promise(resolve => server.close(resolve)); instance.close(); });
  const request = async (path, method = 'GET', data, headers = {}) => {
    const response = await fetch(`http://127.0.0.1:${server.address().port}/api/${path}`, {
      method, headers: { 'Content-Type': 'application/json', ...headers }, body: data === undefined ? undefined : JSON.stringify(data)
    });
    return { status: response.status, ...await response.json() };
  };
  return { ...instance, request, server };
}
const device = { code: 'SIM-TEST-01', name: '模拟设备', status: 'online', temperature: 25.5, humidity: 50 };

test('设备增查改删、搜索、筛选和空列表', async t => {
  const { request } = await fixture(t);
  assert.deepEqual((await request('devices')).data, []);
  const created = await request('devices', 'POST', device);
  assert.equal(created.status, 201); const { id } = created.data;
  assert.equal((await request(`devices/${id}`)).data.code, device.code);
  assert.ok(!Number.isNaN(Date.parse(created.data.updated_at)));
  assert.equal((await request('devices?q=TEST&status=online')).data.length, 1);
  assert.equal((await request('devices?q=missing')).data.length, 0);
  const updated = await request(`devices/${id}`, 'PUT', { ...device, name: '修改设备', status: 'warning', temperature: null });
  assert.equal(updated.data.temperature, null); assert.equal(updated.data.name, '修改设备');
  assert.equal((await request('devices?status=online')).data.length, 0);
  assert.equal((await request(`devices/${id}`, 'DELETE')).status, 200);
  assert.equal((await request(`devices/${id}`)).status, 404);
});
test('字段校验、唯一编号与 SQL 输入边界', async t => {
  const { request } = await fixture(t);
  for (const patch of [{ name: '' }, { code: "x';DROP TABLE devices;--" }, { status: 'broken' }, { temperature: 151 }, { humidity: -1 }, { humidity: '10' }, { name: 'a'.repeat(81) }])
    assert.equal((await request('devices', 'POST', { ...device, ...patch })).status, 400);
  assert.equal((await request('devices', 'POST', [])).status, 400);
  assert.equal((await request('devices', 'POST', device)).status, 201);
  assert.equal((await request('devices', 'POST', device)).error.code, 'DUPLICATE_CODE');
  assert.equal((await request('devices?status=bad')).status, 400);
  assert.equal((await request('devices?q=' + 'a'.repeat(101))).status, 400);
  assert.equal((await request('devices/1oops')).status, 400);
  assert.equal((await request('devices?q=%27%20OR%201%3D1')).data.length, 0);
});
test('工单创建、查询、筛选及完整状态流转', async t => {
  const { request } = await fixture(t);
  const d = (await request('devices', 'POST', device)).data;
  const result = await request('tickets', 'POST', { device_id: d.id, title: '模拟异常', description: '检查读数', priority: 'high' });
  assert.equal(result.status, 201); const { id } = result.data;
  assert.equal((await request(`tickets/${id}`)).data.device_code, d.code);
  assert.equal((await request(`tickets?device_id=${d.id}&q=异常&status=open`)).data.length, 1);
  assert.equal((await request('tickets?q=missing')).data.length, 0);
  assert.equal((await request(`tickets/${id}`, 'PATCH', { status: 'closed' })).status, 409);
  assert.equal((await request(`tickets/${id}`, 'PATCH', { status: 'in_progress' })).data.status, 'in_progress');
  const closed = await request(`tickets/${id}`, 'PATCH', { status: 'closed' });
  assert.ok(closed.data.closed_at); assert.equal(closed.data.status, 'closed');
  assert.equal((await request(`tickets/${id}`, 'PATCH', { status: 'open' })).status, 409);
  assert.equal((await request(`devices/${d.id}`, 'DELETE')).error.code, 'HAS_TICKETS');
});
test('工单关联约束、非法状态和缺失资源', async t => {
  const { request } = await fixture(t, { seed: true });
  for (const patch of [{ device_id: 999 }, { device_id: -1 }, { title: '' }, { priority: 'urgent' }, { description: 'a'.repeat(2001) }]) {
    const result = await request('tickets', 'POST', { device_id: 1, title: '测试', priority: 'medium', ...patch });
    assert.ok([400, 404].includes(result.status));
  }
  assert.equal((await request('tickets/999')).status, 404);
  assert.equal((await request('tickets/1', 'PATCH', { status: 'bad' })).status, 400);
  assert.equal((await request('tickets?device_id=no')).status, 400);
  assert.equal((await request('tickets?status=bad')).status, 400);
});
test('真实文件持久化：关闭连接后重开，关闭状态与修改均保留', async t => {
  const folder = mkdtempSync(join(tmpdir(), 'device-desk-'));
  t.after(() => rmSync(folder, { recursive: true, force: true }));
  const dbPath = join(folder, 'state.sqlite');
  const first = createApp({ dbPath, seed: true, logger: () => {} });
  first.db.prepare('UPDATE devices SET name=? WHERE id=1').run('重启前修改');
  first.db.prepare('UPDATE tickets SET status=?,closed_at=? WHERE id=1').run('closed', '2026-10-18T00:00:00Z');
  first.close();
  const second = createApp({ dbPath, seed: true, logger: () => {} });
  try {
    assert.equal(second.db.prepare('SELECT name FROM devices WHERE id=1').get().name, '重启前修改');
    assert.equal(second.db.prepare('SELECT status FROM tickets WHERE id=1').get().status, 'closed');
    assert.equal(second.db.prepare('SELECT count(*) AS n FROM devices').get().n, 3);
  } finally { second.close(); }
});
test('协议错误：畸形 JSON、请求体过大、跨源写入、未知路径', async t => {
  const { request, server } = await fixture(t);
  assert.equal((await request('devices', 'POST', device, { Origin: 'https://example.com' })).status, 403);
  assert.equal((await request('devices', 'POST', device, { 'Content-Type': 'text/plain' })).status, 415);
  assert.equal((await request('unknown')).status, 404);
  const base = `http://127.0.0.1:${server.address().port}`;
  const bad = await fetch(`${base}/api/devices`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{' });
  assert.equal(bad.status, 400); assert.equal((await bad.json()).error.code, 'INVALID_JSON');
  assert.equal((await request('devices', 'POST', { ...device, name: 'a'.repeat(20000) })).status, 413);
  const index = await fetch(base); assert.equal(index.status, 200); assert.match(await index.text(), /模拟数据/);
});
