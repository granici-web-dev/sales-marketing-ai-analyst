-- Нагрузочная заготовка для замера планов запросов.
--
-- Зачем синтетика: до нескольких тысяч строк postgres честно предпочитает
-- последовательный проход, и «индекс не используется» на тестовой базе не
-- значит ничего. Планы надо смотреть на объёме, а боевой базы с объёмом
-- у нас нет — у пилота порядка 1 200 заявок.
--
-- Объём выбран не «побольше», а под вопрос, на который отвечаем: продукт
-- многоарендный, и спрашивается не «быстро ли у пилота», а «не читает ли
-- кабинет одного клиента строки остальных». Отсюда 50 клиентов, у первого
-- заявок втрое с лишним больше — ровные объёмы у всех дали бы планировщику
-- картину, которой не бывает.
--
-- Перекос намеренный везде: два продавца из восьми держат половину заявок,
-- треть заявок приходится на последние полгода, шестая часть — брак.
-- На равномерном шуме планировщик видит не ту статистику.
--
--   docker run -d --name qp-pg -e POSTGRES_DB=analyst -e POSTGRES_USER=analyst \
--     -e POSTGRES_PASSWORD=dev -p 5456:5432 postgres:16-alpine
--   DATABASE_URL=postgresql+asyncpg://analyst:dev@localhost:5456/analyst alembic upgrade head
--   psql ... -f backend/scripts/load-fixture.sql
--   psql ... -c 'VACUUM ANALYZE'
--
-- Клиент из миграции 002 («sofa-belle») остаётся и попадает в заготовку
-- первым — он же самый крупный. Порядок по slug: 's' раньше 't'.
--
-- Итог: 640 000 заявок, 1 920 000 переходов, ~1.3 млн строк сводных таблиц.
-- Заполнение занимает около тридцати секунд.

-- Синтетика для замера планов. Не равномерный шум: перекос по продавцам,
-- по источникам и по жизненному циклу — планировщик считает по статистике,
-- и на равномерных данных он видит не то, что будет на боевых.

-- 50 клиентов: продукт многоарендный, и вопрос не «быстро ли у пилота»,
-- а «не читает ли кабинет одного клиента строки остальных».
INSERT INTO tenants (id, name, slug, created_at, updated_at)
SELECT gen_random_uuid(), 'Клиент ' || i, 't' || lpad(i::text, 2, '0'), now(), now()
FROM generate_series(1, 50) i;

CREATE TEMP TABLE t AS
SELECT id, row_number() OVER (ORDER BY slug) AS n FROM tenants;

-- Восемь продавцов на клиента.
INSERT INTO mefi_salespeople (id, tenant_id, created_at, updated_at, external_id, name, is_active, showroom)
SELECT gen_random_uuid(), t.id, now(), now(), s, 'Продавец ' || s, true,
       (ARRAY['Brașov','București','Cluj-Napoca'])[1 + mod(s, 3)]
FROM t, generate_series(1, 8) s;

-- Три года сводных строк.
INSERT INTO daily_kpi (id, tenant_id, created_at, updated_at, date,
                       leads_total, visits_count, offers_count, contracts_count,
                       revenue, calculated_at)
SELECT gen_random_uuid(), t.id, now(), now(), d::date,
       10 + mod(t.n * 7 + extract(doy from d)::int, 25),
       5 + mod(t.n * 3 + extract(doy from d)::int, 12),
       3 + mod(t.n + extract(doy from d)::int, 9),
       1 + mod(t.n * 2 + extract(doy from d)::int, 4),
       (2000 + mod(t.n * 137 + extract(doy from d)::int * 11, 18000))::numeric,
       now()
FROM t, generate_series(current_date - 1094, current_date, interval '1 day') d;

INSERT INTO salesperson_daily_kpi (id, tenant_id, created_at, updated_at,
                                   salesperson_external_id, date, leads_assigned,
                                   leads_contacted, visits_conducted, offers_sent,
                                   deals_won, deals_lost, revenue,
                                   avg_time_to_first_touch_minutes,
                                   data_completeness_pct, calculated_at)
SELECT gen_random_uuid(), t.id, now(), now(), s::text, d::date,
       -- Перекос: первый продавец берёт втрое больше восьмого.
       (24 - s * 2) + mod(extract(doy from d)::int, 5),
       (20 - s * 2) + mod(extract(doy from d)::int, 4),
       (10 - s) + mod(extract(doy from d)::int, 3),
       (8 - s) + mod(extract(doy from d)::int, 3),
       greatest(0, 4 - s / 2), greatest(0, 3 - s / 3),
       (1000 * (9 - s) + mod(extract(doy from d)::int * 37, 4000))::numeric,
       15 + s * 9, 70 + mod(s * 7, 30), now()
FROM t, generate_series(1, 8) s,
     generate_series(current_date - 1094, current_date, interval '1 day') d;

INSERT INTO source_daily_kpi (id, tenant_id, created_at, updated_at, source, date,
                              leads, ad_spend, cpl, visits, offers, deals_won,
                              revenue, calculated_at)
SELECT gen_random_uuid(), t.id, now(), now(), src.name, d::date,
       src.weight + mod(extract(doy from d)::int, 4),
       (src.weight * 12)::numeric, (11 + mod(src.weight, 7))::numeric,
       src.weight / 2, src.weight / 3, greatest(0, src.weight / 6),
       (src.weight * 900)::numeric, now()
FROM t,
     (VALUES ('showroom',18),('mail',9),('telefon',14),('whatsapp',11),('site',16),
             ('meta',22),('recomandare',7),('colaborare',3),('arhitect',5),
             ('client_fidel',4),('other',2)) AS src(name, weight),
     generate_series(current_date - 1094, current_date, interval '1 day') d;


-- Заявки. У первого клиента их втрое с лишним больше — это пилот, остальные
-- моложе. Ровные объёмы у всех дали бы планировщику картину, которой не бывает.
INSERT INTO raw_mefi_leads (id, tenant_id, created_at, updated_at, external_id,
                            status_id, status_name, source_id, source_name, lifecycle,
                            assigned_to_id, estimated_value, is_duplicate,
                            created_at_source, status_changed_at, showroom,
                            offer_sent_flag, utm_source, synced_at)
SELECT gen_random_uuid(), t.id, now(), now(), 'L' || t.n || '-' || i,
       (ARRAY[1,3,17,5,8,12,17,3])[1 + mod(i, 8)],
       'status ' || (1 + mod(i, 8)),
       (ARRAY[5,11,10,9,6,2,3,12,7,13,2,6,5])[1 + mod(i, 13)],
       'src',
       CASE WHEN mod(i, 100) < 15 THEN 'junk'
            WHEN mod(i, 100) < 45 THEN 'lost'
            ELSE 'active' END,
       -- Перекос по продавцам: первые двое держат половину заявок.
       CASE WHEN mod(i, 100) < 30 THEN 1
            WHEN mod(i, 100) < 50 THEN 2
            ELSE 3 + mod(i, 6) END,
       (500 + mod(i * 37, 25000))::numeric, mod(i, 50) = 0,
       -- Треть заявок за последние полгода: свежих всегда больше.
       (now() - make_interval(days => CASE WHEN mod(i, 10) < 3
                                           THEN mod(i::bigint * 7919, 180)::int
                                           ELSE mod(i::bigint * 7919, 1095)::int END))::timestamptz,
       (now() - make_interval(days => mod(i::bigint * 104729, 400)::int))::timestamptz,
       (ARRAY['Brașov','București','Cluj-Napoca'])[1 + mod(i, 3)],
       mod(i, 5) < 2,
       (ARRAY['meta','google','direct','referral'])[1 + mod(i, 4)],
       now()
FROM t, LATERAL generate_series(1, CASE WHEN t.n = 1 THEN 40000 ELSE 12000 END) i;

-- История: три перехода на заявку.
INSERT INTO mefi_lead_history (id, tenant_id, created_at, updated_at,
                               lead_external_id, from_status_id, to_status_id,
                               to_status_name, changed_at)
SELECT gen_random_uuid(), r.tenant_id, now(), now(), r.external_id,
       CASE k WHEN 1 THEN NULL ELSE (ARRAY[5,17,3])[k - 1] END,
       (ARRAY[17,3,1])[k], 'status', r.created_at_source + make_interval(days => k * 4)
FROM raw_mefi_leads r, generate_series(1, 3) k;
