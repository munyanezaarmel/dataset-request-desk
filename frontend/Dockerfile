FROM node:22-alpine
WORKDIR /app
# Where the Next.js server forwards /api/* calls (baked in at build time).
ARG API_URL=http://backend:8000
ENV API_URL=$API_URL
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
