class Admin::LlmCostsController < ApplicationController
  before_action :require_admin

  def index
    @month_to_date = LlmAnalysis.month_to_date_cost_usd
    @cap = WALLGARDEN_LLM_COST_CAP_USD
    @breakdown = LlmAnalysis.recent.group(:kind).sum(:cost_usd)
    @recent = LlmAnalysis.order(ran_at: :desc).limit(20)
  end

  private

  def require_admin
    raise Pundit::NotAuthorizedError unless current_user&.admin?
  end
end
