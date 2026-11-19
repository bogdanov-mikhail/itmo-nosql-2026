// Наполнение учебных данных салона массажа (идемпотентно: $setOnInsert по code)
// Подключение — от имени spaAdmin; креды приходят через env SEED_CREDS (JSON)
const creds = JSON.parse(process.env.SEED_CREDS);
const spaConn = new Mongo(`mongodb://${encodeURIComponent(creds.user)}:${encodeURIComponent(creds.password)}@127.0.0.1:27017/?authSource=admin`);
const spa = spaConn.getDB('spa');
let inserted = 0;
const upsertByCode = (coll, doc) => {
  const r = coll.updateOne({ code: doc.code }, { $setOnInsert: doc }, { upsert: true });
  inserted += r.upsertedCount;
};

const services = [
  { code: 'back-60',  title: 'Классический массаж спины',        minutes: 60, price: 3500, active: true },
  { code: 'neck-30',  title: 'Массаж шейно-воротниковой зоны',   minutes: 30, price: 2200, active: true },
  { code: 'sport-90', title: 'Спортивный массаж',                minutes: 90, price: 4800, active: true },
  { code: 'aroma-60', title: 'Ароматерапевтический массаж',       minutes: 60, price: 4000, active: true },
  { code: 'foot-45',  title: 'Массаж стоп',                      minutes: 45, price: 2800, active: true },
  { code: 'kids-30',  title: 'Детский массаж',                   minutes: 30, price: 1900, active: true },
];
services.forEach(s => upsertByCode(spa.services, s));

const masters = [
  { code: 'm-01', name: 'Анна Соколова',   specialty: 'Классический массаж',          rating: 4.9 },
  { code: 'm-02', name: 'Дмитрий Орлов',   specialty: 'Спортивный массаж',            rating: 4.8 },
  { code: 'm-03', name: 'Мария Ветрова',   specialty: 'Ароматерапия',                 rating: 4.7 },
  { code: 'm-04', name: 'Игорь Лебедев',   specialty: 'Массаж стоп, рефлексология',   rating: 4.9 },
];
masters.forEach(m => upsertByCode(spa.masters, m));

const clients = [
  { code: 'c-01', name: 'Ольга Никитина',  phone: '+7-911-200-30-40', card_no: 'SPA-1001' },
  { code: 'c-02', name: 'Павел Ерёмин',    phone: '+7-912-345-67-89', card_no: 'SPA-1002' },
  { code: 'c-03', name: 'Анна Кузьмина',   phone: '+7-921-450-11-22', card_no: 'SPA-1003' },
  { code: 'c-04', name: 'Сергей Плотников',phone: '+7-931-560-33-44', card_no: 'SPA-1004' },
  { code: 'c-05', name: 'Марина Зайцева',  phone: '+7-941-670-55-66', card_no: 'SPA-1005' },
  { code: 'c-06', name: 'Илья Сорокин',    phone: '+7-951-780-77-88', card_no: 'SPA-1006' },
  { code: 'c-07', name: 'Вера Мельник',    phone: '+7-961-890-99-00', card_no: 'SPA-1007' },
  { code: 'c-08', name: 'Артём Гусев',     phone: '+7-971-012-34-56', card_no: 'SPA-1008' },
];
clients.forEach(c => upsertByCode(spa.clients, c));

const appointments = [
  { code: 'a-0001', client_code: 'c-01', master_code: 'm-01', service_code: 'back-60',  starts_at: ISODate('2026-11-18T10:00:00Z'), status: 'booked', price: 3500 },
  { code: 'a-0002', client_code: 'c-02', master_code: 'm-02', service_code: 'sport-90', starts_at: ISODate('2026-11-18T12:30:00Z'), status: 'done',   price: 4800 },
  { code: 'a-0003', client_code: 'c-03', master_code: 'm-03', service_code: 'aroma-60', starts_at: ISODate('2026-11-19T14:00:00Z'), status: 'booked', price: 4000 },
  { code: 'a-0004', client_code: 'c-04', master_code: 'm-04', service_code: 'foot-45',  starts_at: ISODate('2026-11-19T16:00:00Z'), status: 'booked', price: 2800 },
  { code: 'a-0005', client_code: 'c-05', master_code: 'm-01', service_code: 'neck-30',  starts_at: ISODate('2026-11-20T11:00:00Z'), status: 'done',   price: 2200 },
];
appointments.forEach(a => upsertByCode(spa.appointments, a));

const analytics = spaConn.getDB('spa_analytics');
const dailyLoad = [
  { date: ISODate('2026-11-11T00:00:00Z'), appointments_count: 9,  revenue: 26400 },
  { date: ISODate('2026-11-12T00:00:00Z'), appointments_count: 12, revenue: 38900 },
  { date: ISODate('2026-11-13T00:00:00Z'), appointments_count: 10, revenue: 31200 },
  { date: ISODate('2026-11-14T00:00:00Z'), appointments_count: 14, revenue: 45500 },
  { date: ISODate('2026-11-15T00:00:00Z'), appointments_count: 8,  revenue: 19800 },
  { date: ISODate('2026-11-16T00:00:00Z'), appointments_count: 11, revenue: 33400 },
  { date: ISODate('2026-11-17T00:00:00Z'), appointments_count: 13, revenue: 41700 },
];
// daily_load идентифицируется по date, а не по code — отдельный upsert
let insertedDaily = 0;
dailyLoad.forEach(d => {
  const r = analytics.daily_load.updateOne({ date: d.date }, { $setOnInsert: d }, { upsert: true });
  insertedDaily += r.upsertedCount;
});

print('seed: inserted=' + inserted + ' inserted_daily=' + insertedDaily +
      ' services=' + spa.services.countDocuments() +
      ' masters=' + spa.masters.countDocuments() +
      ' clients=' + spa.clients.countDocuments() +
      ' appointments=' + spa.appointments.countDocuments({ load_probe: { $ne: true } }) +
      ' daily_load=' + analytics.daily_load.countDocuments());
