# Use a Node.js base image that supports bun installation
FROM node:18-alpine AS builder

# Install bun
RUN npm install -g bun

# Set the working directory
WORKDIR /app

# Copy package and lock files
COPY package.json bun.lock ./

# Install dependencies using bun
RUN bun install

# Copy the rest of the application
COPY . .

# Build the application
RUN bun run build

# Copy the entrypoint script
COPY entrypoint.sh /entrypoint.sh

# Ensure the script is executable
RUN chmod +x /entrypoint.sh

# Set the correct working directory for execution
WORKDIR /app

# Set the entrypoint
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
