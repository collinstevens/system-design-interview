local key = KEYS[1]
local windowMs = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local elapsedMs = now % windowMs
local windowStartMs = now - elapsedMs
local state = redis.call('HMGET', key, 'windowStartMs', 'currentCount', 'previousCount')
local storedWindowStartMs = tonumber(state[1])
local currentCount = tonumber(state[2]) or 0
local previousCount = tonumber(state[3]) or 0

if storedWindowStartMs ~= windowStartMs then
  if storedWindowStartMs == windowStartMs - windowMs then
    previousCount = currentCount
  else
    previousCount = 0
  end
  currentCount = 0
end

local estimatedCount = currentCount + math.floor(previousCount * ((windowMs - elapsedMs) / windowMs))
local allowed = 0
if estimatedCount < limit then
  currentCount = currentCount + 1
  estimatedCount = estimatedCount + 1
  allowed = 1
end

redis.call('HSET', key,
  'windowStartMs', string.format('%.0f', windowStartMs),
  'currentCount', string.format('%.0f', currentCount),
  'previousCount', string.format('%.0f', previousCount))
redis.call('PEXPIRE', key, string.format('%.0f', 2 * windowMs - elapsedMs))
return {allowed, estimatedCount}
