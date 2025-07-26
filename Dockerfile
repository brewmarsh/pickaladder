# build environment
FROM node:16-alpine as build
WORKDIR /app
COPY frontend/ .
WORKDIR /app
RUN npm ci
COPY public /app/public
WORKDIR /app
RUN npm run build && ls -R /app

# production environment
FROM nginx:stable-alpine
COPY --from=build /app/frontend/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
