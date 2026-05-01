class SensorReading < ApplicationRecord
  belongs_to :zone, optional: true

  KINDS = %w[soil_moisture_pct air_temp_c air_rh_pct lux reservoir].freeze

  validates :kind, presence: true, inclusion: { in: KINDS }
  validates :value, presence: true
  validates :taken_at, presence: true

  scope :good_quality, -> { where(quality: 1) }
  scope :recent, ->(window = 24.hours) { where('taken_at >= ?', window.ago) }
  scope :of_kind, ->(kind) { where(kind: kind) }

  # Latest reading of a given kind, optionally per zone.
  def self.latest(kind:, zone_id: nil)
    rel = where(kind: kind)
    rel = rel.where(zone_id: zone_id) if zone_id
    rel.order(taken_at: :desc).first
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id zone_id kind value unit quality taken_at]
  end

  def self.ransackable_associations(_auth_object = nil) = %w[zone]
end
