// Матрица доступа: реальные операции под учебными пользователями.
// Креды приходят через env MATRIX_USERS (JSON, задаётся из Ansible vault).
// Allow-пробы пишут ТОЛЬКО в собственные документы с маркером _matrix_probe
// (уникальный код за прогон) и проверяют результат операции (insertedCount/modifiedCount).
// Deny-пробы бьют по реальным документам напрямую — отказ сервера (код 13) ничего не меняет.
// Ошибка входа выделяется отдельным вердиктом auth-failed (не путается с deny).
// Формат вывода: user;операция;expected=allow|deny;got=...;OK|FAIL, в конце MATRIX: OK|FAIL
const users = JSON.parse(process.env.MATRIX_USERS);
const runId = Date.now();

const rows = [
  { user: 'frontdesk01', op: 'insert', coll: 'appointments', expect: 'allow' },
  { user: 'frontdesk01', op: 'update', coll: 'appointments', expect: 'allow' },
  { user: 'frontdesk01', op: 'update', coll: 'services',   expect: 'deny'  },
  { user: 'curator01',   op: 'insert', coll: 'services',   expect: 'allow' },
  { user: 'curator01',   op: 'find',   coll: 'appointments', expect: 'deny'  },
  { user: 'cards01',     op: 'find',   coll: 'clients',     expect: 'allow' },
  { user: 'cards01',     op: 'find',   coll: 'appointments', expect: 'deny'  },
];

const realCode = { appointments: 'a-0001', services: 'back-60', masters: 'm-01', clients: 'c-01' };

const attempt = (r) => {
  const u = users[r.user];
  let conn;
  try {
    conn = new Mongo(`mongodb://${encodeURIComponent(u.user)}:${encodeURIComponent(u.password)}@127.0.0.1:27017/?authSource=spa`);
  } catch (e) {
    return 'auth-failed';
  }
  const dbi = conn.getDB('spa');
  try {
    if (r.op === 'find') {
      dbi[r.coll].findOne({ code: { $exists: true } });
      return 'allow';
    }
    if (r.op === 'insert') {
      const probe = { code: `matrix-probe-${runId}-${r.user}-${r.coll}`, _matrix_probe: true };
      const res = dbi[r.coll].insertOne(probe);
      return res.insertedId ? 'allow' : 'no-effect';
    }
    if (r.op === 'update') {
      if (r.expect === 'allow') {
        // собственная проба: вставили — обновили — проверили modifiedCount
        const probeCode = `matrix-probe-${runId}-${r.user}-${r.coll}`;
        dbi[r.coll].insertOne({ code: probeCode, _matrix_probe: true });
        const res = dbi[r.coll].updateOne({ code: probeCode }, { $set: { status: 'updated' } });
        return res.modifiedCount === 1 ? 'allow' : 'no-effect';
      }
      // deny-проба: прямой апдейт реального документа — отклонится, ничего не изменит;
      // маркер на реальные документы не ставим, чтобы чистка не удалила чужие данные
      dbi[r.coll].updateOne({ code: realCode[r.coll] }, { $set: { status: 'unchanged' } });
      return 'allow';
    }
    return 'unknown-op';
  } catch (e) {
    return e.code === 13 ? 'deny' : 'err(' + (e.code || '?') + ')';
  }
};

let fails = 0;
rows.forEach((r) => {
  const got = attempt(r);
  const verdict = got === r.expect ? 'OK' : 'FAIL';
  if (verdict === 'FAIL') fails += 1;
  print(`${r.user};${r.op} ${r.coll};expected=${r.expect};got=${got};${verdict}`);
});

// Чистка: удаляем только пробные документы этого прогона (код matrix-probe-<runId>-…);
// реальные документы никогда не содержат такой код, поэтому не могут быть удалены чисткой
const adm = new Mongo(`mongodb://${encodeURIComponent(users.spaAdmin.user)}:${encodeURIComponent(users.spaAdmin.password)}@127.0.0.1:27017/?authSource=admin`).getDB('spa');
['appointments', 'services', 'masters', 'clients'].forEach((c) => {
  adm[c].deleteMany({ code: { $regex: `^matrix-probe-${runId}-` } });
});

const total = rows.length;
print('MATRIX: ' + (fails ? `FAIL ${fails}` : `OK ${total}/${total}`));
if (fails) quit(1);
