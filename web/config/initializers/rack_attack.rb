# Rate limiting. LAN-only deployment, so this is mostly defensive against
# accidental loops in the dashboard polling code.
class Rack::Attack
  throttle('req/ip', limit: 300, period: 1.minute) { |req| req.ip unless req.path == '/up' }
end
