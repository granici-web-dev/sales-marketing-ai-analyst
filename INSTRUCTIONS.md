# Обновление CLAUDE.md

Когда положишь файлы MEFI документации в проект, в `CLAUDE.md` нужно добавить ссылку на них.

Найди в `CLAUDE.md` секцию **"Quick Links"** в начале (после "Project Overview"):

```markdown
📖 **Полная спецификация:** [SPEC.md](./SPEC.md) — обязательно прочитай перед любой работой.
📖 **Архитектура:** [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
📖 **Стек:** [docs/STACK.md](./docs/STACK.md)
📖 **Конвенции кода:** [docs/CONVENTIONS.md](./docs/CONVENTIONS.md)
📖 **Контекст клиента:** [docs/SOFABELLE.md](./docs/SOFABELLE.md)
📖 **Интеграции:** [docs/INTEGRATIONS.md](./docs/INTEGRATIONS.md)
📖 **MEFI API reference:** [docs/api-references/mefi/](./docs/api-references/mefi/) — official MEFI API documentation (start with README.md)
```

И добавь после последней строки:

```markdown
📖 **MEFI API reference:** [docs/api-references/mefi/](./docs/api-references/mefi/) — official MEFI API documentation (start with README.md)
```

Также найди в `CLAUDE.md` секцию **"When working with external APIs"** и добавь в начало:

```markdown
For MEFI integration specifically, ALWAYS read these files first:

- `docs/api-references/mefi/README.md` — overview, auth, limits
- `docs/api-references/mefi/leads-read.md` — read endpoints (primary)
- `docs/api-references/mefi/enums.md` — status/source/user ID mappings for Sofa Belle
- `docs/api-references/mefi/custom-fields.md` — custom field structure

Note: MEFI API currently exposes ONLY lead endpoints. Deals/offers/calls/visits
must be derived from lead statuses and custom fields. See enums.md for funnel mapping.
```
