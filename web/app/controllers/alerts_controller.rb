class AlertsController < ApplicationController
  def index
    scope = policy_scope(Alert).recent.order(fired_at: :desc)
    @alerts = Kaminari.paginate_array(scope.to_a).page(params[:page]).per(50)
    @unacknowledged_count = Alert.unacknowledged.count
  end

  def acknowledge
    @alert = Alert.find(params[:id])
    authorize @alert
    @alert.acknowledge!(by_user: current_user)
    redirect_back(fallback_location: alerts_path, notice: 'Alert acknowledged.')
  end
end
