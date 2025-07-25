# build environment
FROM node:16-alpine as build
WORKDIR /app
COPY frontend .
WORKDIR /app/frontend
RUN npm ci
COPY frontend/public /app/public
WORKDIR /app/frontend
RUN ls -R /app
RUN ls -R /app/frontend
RUN npm run build

# production environment
FROM nginx:stable-alpine
COPY --from=build /app/frontend/build /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
