FROM node:22-alpine

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=8080

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY server/ server/
COPY scripts/ scripts/
COPY migrations/ migrations/
COPY seeds/ seeds/
COPY data/china-provinces.json data/china-provinces.json
COPY assets/reglens-logo.png assets/reglens-logo.png
COPY index.html app.js ui-upgrade.js trend-upgrade.js home-upgrade.js regulator-tabs.js risk-cloud.js styles.css overrides.css ./

EXPOSE 8080
CMD ["npm", "start"]
