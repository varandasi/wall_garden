class DaemonHeartbeat < ApplicationRecord
  scope :recent, ->(window = 5.minutes) { where('beat_at >= ?', window.ago) }

  def self.most_recent = order(beat_at: :desc).first

  def self.stale?(window = 2.minutes)
    last = order(beat_at: :desc).limit(1).pick(:beat_at)
    return true if last.nil?
    Time.current - last > window
  end

  def self.ransackable_attributes(_auth_object = nil)
    %w[id beat_at loop_count last_error]
  end

  def self.ransackable_associations(_auth_object = nil) = []
end
