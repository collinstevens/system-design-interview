local key = KEYS[1]
local windowMs = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local time = redis.call('TIME')
local now = tonumber(time[1]) * 1000 + math.floor(tonumber(time[2]) / 1000)

redis.call('ZREMRANGEBYSCORE', key, '-inf', '(' .. string.format('%.0f', now - windowMs))
redis.call('ZADD', key, now, ARGV[3])
local count = redis.call('ZCARD', key)
redis.call('PEXPIRE', key, windowMs + 1)

if count <= limit then
  return {1, count}
end
return {0, count}
