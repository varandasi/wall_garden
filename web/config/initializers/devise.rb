# Devise — minimal configuration. The full generated initializer has hundreds
# of comments; for this single-household app the defaults plus a few overrides
# are enough.
Devise.setup do |config|
  config.mailer_sender = ENV.fetch('ALERT_EMAIL_FROM', 'wallgarden@example.com')
  require 'devise/orm/active_record'

  config.case_insensitive_keys = [:email]
  config.strip_whitespace_keys = [:email]

  config.skip_session_storage = [:http_auth]

  config.stretches = Rails.env.test? ? 1 : 11
  config.reconfirmable = true
  config.expire_all_remember_me_on_sign_out = true

  config.password_length = 8..128
  config.email_regexp = /\A[^@\s]+@[^@\s]+\z/

  config.reset_password_within = 6.hours
  config.sign_out_via = :delete

  config.responder.error_status = :unprocessable_content
  config.responder.redirect_status = :see_other
end
