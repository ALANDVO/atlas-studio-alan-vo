# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# Runtime stage — nginx serving static files as non-root
FROM nginx:alpine AS runtime
RUN addgroup -S appgroup && adduser -S -G appgroup appuser
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --spider -q http://127.0.0.1:8080/ || exit 1
CMD ["nginx", "-g", "daemon off;"]