class Command < ApplicationRecord
  STATUSES = %w[pending claimed done failed].freeze
  KINDS = %w[water_zone toggle_lamp snapshot recalibrate].freeze

  validates :kind, presence: true, inclusion: { in: KINDS }
  validates :status, inclusion: { in: STATUSES }

  scope :pending, -> { where(status: 'pending') }
  scope :recent, ->(window = 24.hours) { where('requested_at >= ?', window.ago) }

  def self.ransackable_attributes(_auth_object = nil)
    %w[id kind status requested_at completed_at requested_by]
  end

  def self.ransackable_associations(_auth_object = nil) = []
end
