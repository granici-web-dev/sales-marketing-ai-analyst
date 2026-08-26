FROM node:24-alpine

# Версия pnpm не пишется здесь числом, а берётся из поля packageManager
# в package.json. Раньше она стояла в трёх местах — образ, CI и машина
# разработчика, — и разъехалась ровно так, как разъезжается всё, что
# записано трижды. Одно место, и corepack ставит именно его.
#
# COREPACK_HOME вынесен из домашнего каталога: скачивает pnpm сборка, от root,
# а запускается контейнер от node. С домашним каталогом по умолчанию кэш
# оставался бы у root, и контейнер тянул бы pnpm из сети на каждом старте.
ENV COREPACK_HOME=/opt/corepack
RUN corepack enable pnpm

WORKDIR /app

# Файлы установки целиком, а не только package.json: без pnpm-lock.yaml
# установка в образе разрешает версии заново, и собранное вчера отличается
# от собранного сегодня. pnpm-workspace.yaml нужен не меньше — в нём живут
# настройки защиты от подмены пакетов.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# `corepack install` — здесь, а не выше: он читает packageManager из
# package.json, которого до этой строки в образе нет.
# `--frozen-lockfile` — то же правило, что в CI: расхождение между списком
# и замком должно падать, а не молча чиниться.
RUN corepack install && pnpm install --frozen-lockfile

# Copy application source
COPY . .

# Непривилегированный пользователь. В образе node он уже есть (uid 1000),
# заводить свой незачем. Владение отдаётся ему целиком: `next build` пишет
# .next прямо в рабочий каталог, и без этого prod-команда упала бы на правах.
RUN chown -R node:node /app /opt/corepack
USER node

EXPOSE 3000

CMD ["pnpm", "dev"]
