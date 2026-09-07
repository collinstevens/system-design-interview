local key = KEYS[1]
local windowMs = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)
local resetAfterMs = windowMs - now % windowMs
local windowStartMs = now - now % windowMs
local previousWindowStartMs = tonumber(redis.call('HGET', key, 'windowStartMs'))

if previousWindowStartMs ~= windowStartMs then
  redis.call('HSET', key, 'windowStartMs', string.format('%.0f', windowStartMs), 'count', 0)
end

local count = redis.call('HINCRBY', key, 'count', 1)
redis.call('PEXPIRE', key, string.format('%.0f', resetAfterMs))

if count <= limit then
  return {1, count, 0}
end
return {0, count, resetAfterMs}
