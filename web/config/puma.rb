# Puma listens on :3100 to match culinari's convention.
threads_count = ENV.fetch('RAILS_MAX_THREADS', 3)
threads threads_count, threads_count

port ENV.fetch('PORT', 3100)
environment ENV.fetch('RAILS_ENV', 'development')

# Single-process — fine for a Pi. Bump workers in production if needed.
workers ENV.fetch('WEB_CONCURRENCY', 0)

plugin :solid_queue if ENV['SOLID_QUEUE_IN_PUMA']
plugin :tmp_restart
