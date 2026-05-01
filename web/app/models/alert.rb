class Alert < ApplicationRecord
  belongs_to :zone, optional: true

  SEVERITIES = %w[info warn critical].freeze
  SOURCES    = %w[daemon rails llm].freeze

  validates :severity, inclusion: { in: SEVERITIES }
  validates :source,   inclusion: { in: SOURCES }
  validates :code, :message, presence: true

  scope :unacknowledged, -> { where(acknowledged_at: nil) }
  scope :critical, -> { where(severity: 'critical') }
  scope :recent, ->(window = 7.days) { where('fired_at >= ?', window.ago) }
  scope :pending_dispatch, -> { where(dispatched_at: nil) }

  def acknowledge!(by_user: nil)
    update!(acknowledged_at: Time.current)
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id severity source code zone_id fired_at dispatched_at acknowledged_at]
  end

  def self.ransackable_associations(_auth_object = nil) = %w[zone]
end
