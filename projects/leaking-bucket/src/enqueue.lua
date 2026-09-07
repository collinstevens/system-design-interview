local queueKey = KEYS[1]
local nextDrainKey = KEYS[2]
local capacity = tonumber(ARGV[1])
local leakIntervalMs = tonumber(ARGV[2])
local queueSize = redis.call('LLEN', queueKey)

if queueSize >= capacity then
  return {0, queueSize}
end

if queueSize == 0 then
  local time = redis.call('TIME')
  local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
  redis.call('SET', nextDrainKey, string.format('%.0f', now + leakIntervalMs),
    'NX', 'PX', string.format('%.0f', leakIntervalMs))
end

queueSize = redis.call('RPUSH', queueKey, ARGV[3])
return {1, queueSize}
