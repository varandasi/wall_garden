class WateringEvent < ApplicationRecord
  belongs_to :zone

  TRIGGERS = %w[auto manual llm_suggestion].freeze

  validates :started_at, :planned_ml, presence: true
  validates :trigger, inclusion: { in: TRIGGERS }

  scope :today, -> { where('started_at >= ?', Time.current.utc.beginning_of_day) }
  scope :completed, -> { where.not(ended_at: nil) }
  scope :aborted, -> { where.not(aborted_reason: nil) }

  def in_progress? = ended_at.nil?

  def duration_s
    return nil unless ended_at
    (ended_at - started_at).to_f
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id zone_id started_at ended_at planned_ml actual_ml trigger aborted_reason]
  end

  def self.ransackable_associations(_auth_object = nil) = %w[zone]
end
