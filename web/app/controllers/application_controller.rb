class ApplicationController < ActionController::Base
  include Pundit::Authorization

  before_action :authenticate_user!
  before_action :set_locale

  rescue_from Pundit::NotAuthorizedError, with: :user_not_authorized

  private

  def set_locale
    requested = params[:locale] || session[:locale]
    I18n.locale = if I18n.available_locales.map(&:to_s).include?(requested.to_s)
                    requested.to_s
                  else
                    I18n.default_locale
                  end
  end

  def user_not_authorized
    flash[:alert] = t('errors.messages.not_authorized')
    redirect_back(fallback_location: root_path)
  end
end
