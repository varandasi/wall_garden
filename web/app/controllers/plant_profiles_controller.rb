class PlantProfilesController < ApplicationController
  before_action :set_profile, only: %i[show edit update destroy]

  def index
    @profiles = policy_scope(PlantProfile).order(:common_name)
  end

  def show
    authorize @profile
  end

  def new
    @profile = PlantProfile.new
    authorize @profile
  end

  def create
    @profile = PlantProfile.new(profile_params)
    authorize @profile
    if @profile.save
      redirect_to plant_profiles_path, notice: 'Profile created.', status: :see_other
    else
      render :new, status: :unprocessable_content
    end
  end

  def edit
    authorize @profile
  end

  def update
    authorize @profile
    if @profile.update(profile_params)
      redirect_to plant_profiles_path, notice: 'Profile updated.', status: :see_other
    else
      render :edit, status: :unprocessable_content
    end
  end

  def destroy
    authorize @profile
    @profile.destroy
    redirect_to plant_profiles_path, notice: 'Profile removed.', status: :see_other
  end

  private

  def set_profile
    @profile = PlantProfile.find(params[:id])
  end

  def profile_params
    params.expect(plant_profile: %i[
      common_name scientific_name notes
      ideal_moisture_min ideal_moisture_max ideal_lux_min
      ideal_temp_c_min ideal_temp_c_max
    ])
  end
end
