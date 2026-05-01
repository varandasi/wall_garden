class AlertMailer < ApplicationMailer
  def critical
    @alert = params[:alert]
    mail(
      to: ENV.fetch('ALERT_EMAIL_TO', ''),
      subject: "[Wall Garden] #{@alert.severity.upcase}: #{@alert.code}",
    )
  end

  def digest
    @body = params[:body]
    mail(
      to: ENV.fetch('ALERT_EMAIL_TO', ''),
      subject: '[Wall Garden] Daily digest',
    )
  end
end
