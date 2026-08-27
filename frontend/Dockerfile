## ── Builder ──────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npx svelte-kit sync && npm run build

## ── Runner ───────────────────────────────────────────────────────
FROM node:20-slim

ENV NODE_ENV=production
ENV NODE_OPTIONS="--require /app/node-polyfill.cjs"
WORKDIR /app

# Only production deps for the adapter-node server
COPY package.json package-lock.json node-polyfill.cjs ./
RUN npm ci --omit=dev 2>/dev/null || true

# Copy built output from builder
COPY --from=builder /app/build ./build

EXPOSE 3000
CMD ["node", "build/index.js"]
