class Photo < ApplicationRecord
  belongs_to :zone, optional: true
  belongs_to :llm_analysis, optional: true

  validates :path, :taken_at, presence: true

  scope :recent, ->(window = 7.days) { where('taken_at >= ?', window.ago) }

  # The daemon writes a path on the local filesystem; Rails serves it via
  # PhotosController#show. We don't use Active Storage to keep the contract
  # simple (the daemon owns the bytes).
  # The daemon stores paths relative to its own working dir (../daemon).
  def absolute_path
    p = Pathname.new(path)
    p.absolute? ? p.to_s : Rails.root.join('..', 'daemon', path).expand_path.to_s
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id zone_id taken_at path]
  end

  def self.ransackable_associations(_auth_object = nil) = %w[zone llm_analysis]
end
