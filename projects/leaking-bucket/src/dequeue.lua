local queueKey = KEYS[1]
local nextDrainKey = KEYS[2]
local leakIntervalMs = tonumber(ARGV[1])
local queueSize = redis.call('LLEN', queueKey)

if queueSize == 0 then
  return {false, 0, 0}
end

local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local nextDrainMs = tonumber(redis.call('GET', nextDrainKey)) or now

if now < nextDrainMs then
  return {false, queueSize, nextDrainMs - now}
end

local request = redis.call('LPOP', queueKey)
redis.call('SET', nextDrainKey, string.format('%.0f', now + leakIntervalMs),
  'PX', string.format('%.0f', leakIntervalMs))
queueSize = queueSize - 1
local retryAfterMs = 0
if queueSize > 0 then
  retryAfterMs = leakIntervalMs
end
return {request, queueSize, retryAfterMs}
