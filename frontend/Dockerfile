# Dockerfile for React frontend
FROM node:18-alpine as build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build
FROM node:18-alpine as prod
WORKDIR /app
COPY --from=build /app .
CMD ["npm", "run", "dev", "--", "--host"]
