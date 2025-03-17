FROM node:22.12-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install --ignore-scripts

COPY . .

RUN npm run build

EXPOSE 8000

CMD ["npx", "supergateway", "--stdio", "dist/index.js"]