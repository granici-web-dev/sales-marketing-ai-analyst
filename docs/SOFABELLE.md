# Sofa Belle — Pilot Client Context

> Контекст пилотного клиента. Важно для понимания доменной модели, метрик и AI-инсайтов.

## Company Overview

| Поле | Значение |
|---|---|
| **Название** | Sofa Belle (S.C. BELLE SOFA S.R.L.) |
| **Сайт** | [sofabelle.ro](https://sofabelle.ro) |
| **Индустрия** | Производство премиум-мебели на заказ |
| **Продукты** | Диваны, кресла, кровати, мебель под индивидуальные размеры |
| **Шоурумы** | 3: Brașov, București, Cluj-Napoca |
| **Команда продаж** | 6 продавцов |
| **Средний чек** | 20.000+ RON |
| **Цикл сделки** | 2 недели — 2 месяца (длинный, премиум-сегмент) |
| **CRM** | MEFI |
| **Телефония** | Ещё не выбрана (рекомендуем DOTRO SmartPBX) |

## Why Sofa Belle is a great pilot

- **Premium segment** — каждый потерянный лид стоит существенных денег → высокая ROI от нашего продукта
- **Clear pain point** — собственник хочет понимать дорабатывают ли продавцы лиды
- **All sources active** — Meta, Google, TikTok Ads + GA4 + Search Console уже настроены
- **Historic data** — Excel-таблица с метриками за май 2025 → май 2026 (можем сравнить YoY)
- **Multi-location** — 3 шоурума дают сложность достаточную для отработки product features
- **Willing to provide feedback** — собственник и аналитик готовы участвовать в итерациях

## Sales Funnel (specific to Sofa Belle)

```
Lead ──► Vizita ──► Oferta ──► Contract
        (в шоурум)   (отправлена)  (закрыт)
```

**Conversions to track:**
- **L→V** — Lead to Visit (визит в шоурум)
- **V→O** — Visit to Offer (отправка оферты после визита)
- **L→O** — Lead to Offer (общая)
- **O→C** — Offer to Contract (закрытие сделки)
- **L→C** — Lead to Contract (общая конверсия)

**Specifics:**
- Визит в шоурум — **критический этап**. Премиум-мебель не покупают онлайн, клиент должен увидеть и потрогать.
- Без визита почти никогда нет сделки.
- Скорость реакции на лид критична: если продавец не отвечает 4+ часов, лид может пойти к конкурентам.

## Lead Categories (как у клиента)

Клиент в MEFI размечает лиды по этим категориям:

| Категория | Описание | Откуда приходят |
|---|---|---|
| **Mail/FB/IG** | Email заявки + Facebook/Instagram Lead Ads | Meta Ads, формы на FB/IG |
| **Telefon** | Входящие звонки | Реклама с номером телефона |
| **WhatsApp** | Заявки через WhatsApp Business | Кнопка WhatsApp на сайте/в рекламе |
| **Site** | Формы на sofabelle.ro | Органика, прямые заходы, Google Ads |
| **Designer** | Заявки на услугу дизайнера интерьера | Отдельная услуга компании |
| **Alte** | Прочие источники | Рекомендации, walk-in, мероприятия |

## Marketing Channels

### Meta Ads (Facebook + Instagram)
- Lead Ads формы
- Driving traffic на sofabelle.ro
- Catalog ads для конкретных моделей
- Retargeting

### Google Ads
- Search campaigns на бренд + общие запросы ("canapele premium", "mobilă la comandă")
- Performance Max для всей экосистемы Google

### TikTok Ads
- Brand awareness, видео-контент с мебелью
- Lead generation

### Organic
- SEO (Google Search Console трекает)
- Direct traffic (узнаваемость бренда)
- Walk-in в шоурумы

## Key Metrics from Client's Excel Spreadsheet

Клиент уже трекает эти метрики вручную в Excel. **Наша задача — автоматизировать и обогатить, не выдумывать новое.**

### Бюджеты (lei)
- Buget META
- Buget Google
- Buget Tik-tok
- Buget Digital Total

### Трафик
- Trafic (sesiuni) — из GA4

### Лиды
- Leads Mail/FB/IG
- Leads Telefon
- Leads WhatsApp
- Leads Total Site (из формы сайта)
- Leads Designer
- Leads Alte
- Leads Total

### Экономика
- Cost per Lead
- Conversie site (%)

### Воронка
- Vizita (визит в шоурум)
- Oferta
- Contract

### Конверсии
- Conversie vizita (Lead → Vizita)
- Conversie Oferta (V/O) — Visit to Offer
- Conversie Oferta (L/O) — Lead to Offer
- Conversie Contract (O/C)

### Финансы
- Cost Aquisiton Contract (CAC)
- Încasări (выручка)
- Cec mediu / zi (средний чек по дням)
- ROAS
- YoY (Year over Year)

## Excel Spreadsheet (от мая 2025 до мая 2026)

Пример колонок:
```
Метрика                | Mai 2025 | Iunie 2025 | Iulie 2025 | ... | Mai 2026
Buget META (lei)       |          | 10 352     | 19 262     | ... | 10 469
Buget Google (lei)     |          | 9 122      | 20 945     | ... | 10 248
Buget Tik-tok (lei)    |          | 0          | 1 752      | ... | 2 053
Buget Digital Total    |          | 19 473     | 41 960     | ... | 22 770
Trafic (sesiuni)       | 10 501   | 14 680     | 19 382     | ... | 7 170
Leads Total            |          | 192        | 373        | ... | 146
Cost per Lead          |          | 105        | 116        | ... | 162
Conversie site         |          | 1.81%      | 1.86%      | ... | 1.96%
Vizita                 |          | 49         | 210        | ... | 143
Oferta                 | 48       |            |            | ... | 118
Conversie vizita       | 25.5%    | 25.5%      | 56.30%     | ... | 97.44%
Contract               | 10       | 20         | 54         | ... | 24
Încasări               |          | 392 183    | 333 451    | ... | 461 091
Cec mediu / zi         |          | 16 673     | 17 654     | ... | 18 917
ROAS                   |          | 1712%      | 2301%      | ... | 2025%
YoY                    |          | 194%       | 265%       | ... | 18%
```

**Используем как референс структуры дашборда** — клиент сразу узнает свои метрики в нашем UI.

## Showrooms (3 локации)

| Шоурум | Город | Особенности |
|---|---|---|
| Brașov | Brașov | Центральная Румыния, средний доход |
| București | Бухарест | Столица, высокий доход, конкуренция |
| Cluj-Napoca | Cluj | IT-хаб, молодая аудитория, высокий доход |

**Important (отложено на будущую итерацию):**
- После подключения IP-телефонии: 3 разных входящих номера = 3 шоурума
- Аналитика **по шоуруму** будет critical feature
- Marketing campaigns могут таргетиться по городам → связь канал ↔ шоурум

## Pain Points (что собственник хочет решить)

1. **"Не понимаю где теряются деньги"** — много трафика, дорогая реклама, но конверсия в контракт не растёт
2. **"Не знаю кто из продавцов лучше работает"** — нужны KPI по продавцам
3. **"Не понимаю какая реклама окупается"** — нужен CPL/CAC/ROAS по каждому каналу
4. **"Excel-таблица занимает время"** — хочет автоматизацию того что считает вручную
5. **"Хочу понимать что делать каждый день"** — хочет конкретные рекомендации, не цифры

## Specifics for AI Insights

При генерации инсайтов через Claude учитывать:

### Контекст бизнеса
- **Long sales cycle:** не паниковать если сделка не закрылась за неделю
- **High ticket:** даже 1 потерянный лид = 20.000+ RON, значимо
- **Visit-driven:** L→V конверсия критична, без визита нет сделки

### Sensitive metrics
- **Time to first touch** — главная операционная метрика (< 4 часов в рабочее время)
- **Missed call rate** — пропущенный звонок = почти потерянная сделка
- **Stuck offers** — оферта без активности > 14 дней = риск

### Tone of insights
- На румынском (основной язык)
- Business-tone, без воды
- Конкретные действия с RON-impact
- Топ-3 проблемы, не 10

## Domain Glossary (Romanian → English)

| Romanian | English | Описание |
|---|---|---|
| Canapea | Sofa | Основной продукт |
| Colțar | Corner sofa | Угловой диван |
| Fotoliu | Armchair | Кресло |
| Pat | Bed | Кровать |
| Tapițerie | Upholstery | Обивка |
| Piele naturală | Natural leather | Натуральная кожа |
| Lead / Client potențial | Lead | Лид |
| Vizita / Vizionare | Showroom visit | Визит в шоурум |
| Oferta | Quote / Offer | Коммерческое предложение |
| Contract | Deal / Contract | Закрытая сделка |
| Pâlnie de vânzări | Sales funnel | Воронка продаж |
| Vânzător / Agent | Salesperson | Продавец |
| Showroom | Showroom | Шоурум |
| Cec mediu | Average deal size | Средний чек |
| Încasări | Revenue | Выручка |

## What we DON'T do for Sofa Belle (MVP1)

- ❌ Не подключаем IP-телефонию (это они сами выбирают и подключают)
- ❌ Не настраиваем рекламу (у них есть маркетолог/агентство)
- ❌ Не пишем рекламные креативы
- ❌ Не делаем SEO-оптимизацию
- ❌ Не интегрируемся с их сайтом sofabelle.ro напрямую (только через GA4 API)
- ❌ Не управляем их MEFI настройками

**Мы — analytics layer. Не больше.**

## Future opportunities (после MVP1)

Когда Sofa Belle подключит DOTRO + MonitorAI:
- Аналитика звонков (sentiment, темы)
- Привязка звонка к шоуруму (через входящий номер)
- Аналитика "что говорят клиенты" (топ-возражения, топ-вопросы)
- Coaching продавцов на основе sentiment

## Contact (пилотный клиент)

- **Owner:** [TBD]
- **Analyst:** [TBD]
- **Marketing manager:** [TBD]
- **Контакт для пилота:** [TBD]
