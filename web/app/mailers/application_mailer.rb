class ApplicationMailer < ActionMailer::Base
  default from: ENV.fetch('ALERT_EMAIL_FROM', 'wallgarden@example.com')
  layout 'mailer'
end
