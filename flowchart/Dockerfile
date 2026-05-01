## ── Builder ──────────────────────────────────────────────────────
FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

## ── Runner ───────────────────────────────────────────────────────
FROM nginx:alpine

# Copy built static files to Nginx's default public directory
COPY --from=builder /app/dist/ /usr/share/nginx/html/

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
