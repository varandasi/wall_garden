class PhotosController < ApplicationController
  # Slice 5 wires up the time-lapse view; v0 just lists the rows.
  def index
    @photos = policy_scope(Photo).recent.order(taken_at: :desc).limit(100)
  end

  def show
    @photo = Photo.find(params[:id])
    authorize @photo
    if File.exist?(@photo.path)
      send_file @photo.path, type: 'image/jpeg', disposition: 'inline'
    else
      head :not_found
    end
  end
end
