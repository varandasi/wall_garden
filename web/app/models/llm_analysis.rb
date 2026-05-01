class LlmAnalysis < ApplicationRecord
  KINDS = %w[weekly_report photo anomaly digest chat].freeze

  validates :kind, inclusion: { in: KINDS }
  validates :model, :output, presence: true

  scope :recent, ->(window = 30.days) { where('ran_at >= ?', window.ago) }

  def self.month_to_date_cost_usd
    where('ran_at >= ?', Time.current.utc.beginning_of_month).sum(:cost_usd).to_f
  end

  def cache_hit_ratio
    total = (input_tokens || 0) + (cache_read_tokens || 0)
    return nil if total.zero?
    (cache_read_tokens || 0).to_f / total
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id kind model ran_at cost_usd input_tokens output_tokens cache_read_tokens]
  end

  def self.ransackable_associations(_auth_object = nil) = []
end
