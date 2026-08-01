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

# Listen on 8081 (not 80) — all services share elemes-ts network
# namespace, where port 80 is taken by velxio. Tailscale serve strips
# the /flowchart/ mount point before proxying here.
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8081
CMD ["nginx", "-g", "daemon off;"]
