#!/usr/bin/env bash
# Redis initialisation helper
# Usage: ./scripts/setup_redis.sh [host] [port]

set -euo pipefail

REDIS_HOST="${1:-localhost}"
REDIS_PORT="${2:-6379}"

echo "Pinging Redis at ${REDIS_HOST}:${REDIS_PORT}..."
redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" PING

echo "Configuring Redis for Sovereign Cricket Analytics..."

# Set a sensible max memory policy for cache eviction
redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG SET maxmemory-policy allkeys-lru

echo "Redis setup complete."
