## ── Builder ──────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

## ── Runner ───────────────────────────────────────────────────────
FROM node:20-slim

ENV NODE_ENV=production
WORKDIR /app

# Only production deps for the adapter-node server
COPY package.json ./
RUN npm install --omit=dev 2>/dev/null || true

# Copy built output from builder
COPY --from=builder /app/build ./build

EXPOSE 3000
CMD ["node", "build/index.js"]
