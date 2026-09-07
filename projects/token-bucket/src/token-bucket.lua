local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refillTokens = tonumber(ARGV[2])
local refillIntervalMs = tonumber(ARGV[3])
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local bucket = redis.call('HMGET', key, 'tokens', 'lastRefillMs')
local tokens = tonumber(bucket[1]) or capacity
local lastRefillMs = tonumber(bucket[2]) or now
local elapsedMs = math.max(0, now - lastRefillMs)
local refillCount = math.floor(elapsedMs / refillIntervalMs)

if refillCount > 0 then
  tokens = math.min(capacity, tokens + refillCount * refillTokens)
  lastRefillMs = now - elapsedMs % refillIntervalMs
end

local allowed = 0
local retryAfterMs = refillIntervalMs - (now - lastRefillMs)
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
  retryAfterMs = 0
end

redis.call('HSET', key, 'tokens', string.format('%.0f', tokens), 'lastRefillMs', string.format('%.0f', lastRefillMs))
return {allowed, tokens, retryAfterMs}
