class Zone < ApplicationRecord
  belongs_to :plant_profile, optional: true
  has_many :sensor_readings, dependent: :destroy
  has_many :watering_events, dependent: :destroy
  has_many :alerts, dependent: :nullify

  validates :name, presence: true, uniqueness: true
  validates :ads_address, :ads_channel, :pump_gpio, presence: true
  validates :target_moisture_pct, numericality: { greater_than_or_equal_to: 0, less_than_or_equal_to: 100 }
  validates :hysteresis_pct, numericality: { greater_than: 0, less_than_or_equal_to: 30 }
  validates :max_ml_per_day, :max_ml_per_event, numericality: { greater_than: 0 }
  validates :cooldown_minutes, numericality: { greater_than_or_equal_to: 0 }
  validates :pump_ml_per_sec, numericality: { greater_than: 0 }

  scope :enabled, -> { where(enabled: true) }

  # Latest soil_moisture_pct reading (or nil if none).
  def latest_moisture
    sensor_readings.where(kind: 'soil_moisture_pct').order(taken_at: :desc).limit(1).pick(:value)&.to_f
  end

  # Today's water total (UTC day).
  def ml_today
    watering_events.where('started_at >= ?', Time.current.utc.beginning_of_day)
                   .where.not(actual_ml: nil)
                   .sum(:actual_ml)
  end

  # Last completed watering event (or nil).
  def last_watering
    watering_events.where.not(ended_at: nil).order(ended_at: :desc).first
  end

  def thirsty?
    m = latest_moisture
    return false unless m
    m < (target_moisture_pct - hysteresis_pct / 2)
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id name target_moisture_pct enabled created_at updated_at]
  end

  def self.ransackable_associations(_auth_object = nil)
    %w[plant_profile sensor_readings watering_events alerts]
  end
end
