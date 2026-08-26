FROM node:24-alpine

# Install pnpm globally
RUN npm install -g pnpm@9

WORKDIR /app

# Файлы установки целиком, а не только package.json: без pnpm-lock.yaml
# установка в образе разрешает версии заново, и собранное вчера отличается
# от собранного сегодня. `--frozen-lockfile` — то же правило, что в CI:
# расхождение между списком и замком должно падать, а не молча чиниться.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy application source
COPY . .

# Непривилегированный пользователь. В образе node он уже есть (uid 1000),
# заводить свой незачем. Владение отдаётся ему целиком: `next build` пишет
# .next прямо в рабочий каталог, и без этого prod-команда упала бы на правах.
RUN chown -R node:node /app
USER node

EXPOSE 3000

CMD ["pnpm", "dev"]
