FROM node:20-slim

WORKDIR /app

# package-lock.json is committed, so use npm's reproducible installer rather
# than requiring a pnpm lockfile that is not part of this repository.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
