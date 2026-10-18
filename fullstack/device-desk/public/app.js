const $ = id => document.getElementById(id);
const labels = { online: '在线', offline: '离线', warning: '告警', open: '待处理', in_progress: '处理中', closed: '已关闭', high: '高', medium: '中', low: '低' };
const date = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—';
function el(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}
function status(value) { return el('span', labels[value], `status ${value}`); }
function action(label, type, id, danger = false) {
  const b = el('button', label, danger ? 'danger' : '');
  b.type = 'button'; b.dataset.action = type; b.dataset.id = id; return b;
}
async function api(path, method = 'GET', body) {
  const response = await fetch(`api/${path}`, { method, headers: { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(8000) });
  const result = await response.json().catch(() => { throw new Error('接口未返回 JSON；请通过本地 Node 服务访问此页面。'); });
  if (!response.ok) throw new Error(`${result.error?.message || '请求失败'}（${response.status} / ${result.error?.code || 'UNKNOWN'}）`);
  return result.data;
}
let devices = [], busy = false;
function showError(error) {
  $('error').hidden = false;
  $('error').textContent = `${error.message}\n若服务未启动，请在 fullstack/device-desk 运行 npm start；点击“刷新数据”重试。`;
  $('message').textContent = '';
}
async function run(task, message = '') {
  if (busy) return;
  busy = true;
  document.querySelectorAll('button').forEach(b => { b.disabled = true; });
  $('error').hidden = true; $('message').textContent = '正在处理…';
  try { await task(); $('message').textContent = message || '数据已更新'; }
  catch (error) { showError(error); }
  finally { busy = false; document.querySelectorAll('button').forEach(b => { b.disabled = false; }); }
}
function query(form) { return new URLSearchParams(new FormData(form)).toString(); }
async function reload() {
  try {
    const [allDevices, allTickets, filteredDevices, filteredTickets] = await Promise.all([
      api('devices'), api('tickets'), api(`devices?${query($('device-filter'))}`), api(`tickets?${query($('ticket-filter'))}`)
    ]);
    devices = allDevices;
    $('device-count').textContent = devices.length;
    $('warning-count').textContent = devices.filter(d => d.status === 'warning').length;
    $('ticket-count').textContent = allTickets.filter(t => t.status !== 'closed').length;
    const selected = $('ticket-device').value;
    $('ticket-device').replaceChildren(new Option(devices.length ? '请选择设备' : '请先新增设备', ''));
    for (const d of devices) $('ticket-device').add(new Option(`${d.code} · ${d.name}`, d.id));
    $('ticket-device').value = selected;
    renderDevices(filteredDevices); renderTickets(filteredTickets);
  } catch (error) {
    $('device-rows').replaceChildren(); $('ticket-list').replaceChildren();
    $('device-result').textContent = '设备数据未加载'; $('ticket-result').textContent = '工单数据未加载';
    for (const name of ['device-count', 'warning-count', 'ticket-count']) $(name).textContent = '—';
    throw error;
  }
}
function renderDevices(rows) {
  $('device-rows').replaceChildren(); $('device-result').textContent = `筛选结果：${rows.length} 台设备`;
  if (!rows.length) { const tr = el('tr'), td = el('td', '暂无匹配设备。可清除筛选或新增设备。', 'empty'); td.colSpan = 5; tr.append(td); $('device-rows').append(tr); }
  for (const d of rows) {
    const tr = el('tr'), name = el('td'); name.append(el('strong', d.name), el('small', d.code));
    const state = el('td'); state.append(status(d.status));
    const reading = el('td', `${d.temperature ?? '—'} °C`); reading.append(el('small', `${d.humidity ?? '—'} % RH`));
    const controls = el('td'), actions = el('div', undefined, 'row-actions');
    actions.append(action('查看', 'device-view', d.id), action('编辑', 'device-edit', d.id), action('删除', 'device-delete', d.id, true));
    controls.append(actions); tr.append(name, state, reading, el('td', date(d.updated_at)), controls); $('device-rows').append(tr);
  }
}
function renderTickets(rows) {
  $('ticket-list').replaceChildren(); $('ticket-result').textContent = `筛选结果：${rows.length} 条工单`;
  if (!rows.length) $('ticket-list').append(el('p', '暂无匹配工单。可清除筛选或创建工单。', 'empty'));
  for (const t of rows) {
    const card = el('article', undefined, 'ticket'), head = el('div', undefined, 'ticket-head');
    head.append(el('span', `#${t.id} · ${t.device_code} · ${labels[t.priority]}优先级`), status(t.status));
    const actions = el('div', undefined, 'row-actions'); actions.append(action('查看详情', 'ticket-view', t.id));
    if (t.status !== 'closed') actions.append(action(t.status === 'open' ? '开始处理' : '关闭工单', `ticket-${t.status === 'open' ? 'start' : 'close'}`, t.id));
    card.append(head, el('h3', t.title), el('p', t.description || '暂无问题描述'), el('p', `更新于 ${date(t.updated_at)}`, 'muted'), actions); $('ticket-list').append(card);
  }
}
function resetEditor() { $('device-form').reset(); $('device-form').elements.id.value = ''; $('device-form-title').textContent = '新增设备'; }
function detail(title, pairs) {
  $('detail-title').textContent = title; $('detail-body').replaceChildren();
  for (const [key, value] of pairs) $('detail-body').append(el('dt', key), el('dd', String(value ?? '—')));
  $('detail').showModal();
}
$('close-detail').addEventListener('click', () => $('detail').close());
$('refresh').addEventListener('click', () => run(reload));
$('cancel-edit').addEventListener('click', resetEditor);
for (const name of ['device-filter', 'ticket-filter']) $(name).addEventListener('submit', e => { e.preventDefault(); run(reload); });
$('device-form').addEventListener('submit', e => {
  e.preventDefault(); const f = e.currentTarget, data = Object.fromEntries(new FormData(f));
  const { id, ...body } = data;
  body.temperature = body.temperature === '' ? null : Number(body.temperature);
  body.humidity = body.humidity === '' ? null : Number(body.humidity);
  run(async () => { await api(id ? `devices/${id}` : 'devices', id ? 'PUT' : 'POST', body); resetEditor(); await reload(); }, '设备已保存');
});
$('ticket-form').addEventListener('submit', e => {
  e.preventDefault(); const data = Object.fromEntries(new FormData(e.currentTarget)); data.device_id = Number(data.device_id);
  run(async () => { await api('tickets', 'POST', data); $('ticket-form').reset(); await reload(); }, '工单已创建');
});
document.addEventListener('click', e => {
  const b = e.target.closest('button[data-action]'); if (!b || busy) return;
  const type = b.dataset.action, id = Number(b.dataset.id);
  if (type === 'device-edit') {
    const d = devices.find(d => d.id === id); if (!d) return;
    for (const key of ['id', 'code', 'name', 'status', 'temperature', 'humidity']) $('device-form').elements[key].value = d[key] ?? '';
    $('device-form-title').textContent = `编辑设备 · ${d.code}`;
    $('device-form').scrollIntoView({ block: 'center' }); $('device-form').elements.name.focus(); return;
  }
  if (type === 'device-delete' && !confirm('确认删除此设备？有关联工单时会保留记录并拒绝删除。')) return;
  run(async () => {
    if (type === 'device-view') {
      const d = await api(`devices/${id}`);
      detail(d.name, [['设备编号', d.code], ['状态', labels[d.status]], ['模拟温度 / °C', d.temperature], ['模拟湿度 / %', d.humidity], ['更新时间', date(d.updated_at)]]);
    } else if (type === 'ticket-view') {
      const t = await api(`tickets/${id}`);
      detail(t.title, [['工单编号', t.id], ['设备', `${t.device_code} · ${t.device_name}`], ['状态', labels[t.status]], ['优先级', labels[t.priority]], ['问题描述', t.description], ['创建时间', date(t.created_at)], ['更新时间', date(t.updated_at)], ['关闭时间', date(t.closed_at)]]);
    } else if (type === 'device-delete') { await api(`devices/${id}`, 'DELETE'); if ($('device-form').elements.id.value === String(id)) resetEditor(); await reload(); }
    else { await api(`tickets/${id}`, 'PATCH', { status: type === 'ticket-start' ? 'in_progress' : 'closed' }); await reload(); }
  });
});
run(reload);
