# build environment
FROM node:16-alpine as build
WORKDIR /app
COPY frontend/package.json .
COPY frontend/package-lock.json .
RUN npm ci
COPY frontend .
RUN npm run build

# production environment
FROM nginx:stable-alpine
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
