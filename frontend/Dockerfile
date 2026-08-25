FROM node:22-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src

# Public API base is same-origin "/api" (see src/api/client.ts), proxied at
# the edge gateway straight to the backend -- no build-time env needed here.
RUN npm run build

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
