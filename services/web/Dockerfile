# multi-stage: у фінальному образі немає devDependencies/білд-інструментів
FROM node:22-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /app/dist ./dist
ENV RESULTS_DIR=/data/results HOST=0.0.0.0 PORT=4321 NODE_ENV=production
EXPOSE 4321
USER 1000:1000
CMD ["node", "./dist/server/entry.mjs"]
