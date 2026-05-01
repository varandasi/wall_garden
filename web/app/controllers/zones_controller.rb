class ZonesController < ApplicationController
  before_action :set_zone, only: %i[show edit update water enable disable]

  def index
    @zones = policy_scope(Zone).includes(:plant_profile).order(:name)
  end

  def show
    authorize @zone
    @recent_readings = @zone.sensor_readings
                            .where(kind: 'soil_moisture_pct').good_quality
                            .where('taken_at >= ?', 24.hours.ago)
                            .order(taken_at: :desc).limit(500)
    @recent_events = @zone.watering_events.order(started_at: :desc).limit(20)
  end

  def edit
    authorize @zone
  end

  def update
    authorize @zone
    if @zone.update(zone_params)
      redirect_to @zone, notice: 'Zone updated.', status: :see_other
    else
      render :edit, status: :unprocessable_content
    end
  end

  # POST /zones/:id/water — enqueue a manual water command for the daemon.
  def water
    authorize @zone, :update?
    Command.create!(
      kind: 'water_zone',
      payload: { zone_id: @zone.id }.merge(water_payload),
      requested_by: 'web',
    )
    redirect_to root_path, notice: "Watering #{@zone.name} queued.", status: :see_other
  end

  def enable
    authorize @zone, :update?
    @zone.update!(enabled: true)
    redirect_back(fallback_location: zone_path(@zone))
  end

  def disable
    authorize @zone, :update?
    @zone.update!(enabled: false)
    redirect_back(fallback_location: zone_path(@zone))
  end

  private

  def set_zone
    @zone = Zone.find(params[:id])
  end

  def zone_params
    params.expect(zone: %i[
      name target_moisture_pct hysteresis_pct max_ml_per_day
      max_ml_per_event cooldown_minutes pump_ml_per_sec
      moisture_dry_raw moisture_wet_raw enabled plant_profile_id
    ])
  end

  def water_payload
    return {} unless params[:ml].present?
    { ml_override: params[:ml].to_i }
  end
end
