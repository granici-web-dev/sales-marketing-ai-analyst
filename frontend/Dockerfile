FROM node:24-alpine

# Install pnpm globally
RUN npm install -g pnpm

WORKDIR /app

# Copy dependency files first for better layer caching
COPY package.json pnpm-lock.yaml* ./

# Install dependencies
RUN pnpm install

# Copy application source
COPY . .

EXPOSE 3000

CMD ["pnpm", "dev"]
