module WallGarden
  # Statistical anomaly detection on sensor_readings. The LLM only
  # *describes* what statistics already flagged.
  #
  # Rule: a reading is anomalous if it falls outside (mean ± 2σ) of the prior
  # 7-day baseline for the same kind/zone. Returns one entry per anomaly.
  class AnomalyDetector
    Anomaly = Struct.new(:kind, :zone_id, :latest_value, :baseline_mean, :baseline_sd, :timestamp,
                         keyword_init: true) do
      def to_summary
        z = zone_id ? "zone #{zone_id} " : ''
        "#{kind} #{z}reading #{latest_value.round(2)} at #{timestamp} " \
          "(baseline mean #{baseline_mean.round(2)} ±#{baseline_sd.round(2)})"
      end
    end

    def initialize(window_recent: 6.hours, window_baseline: 7.days, sigma: 2.0)
      @window_recent   = window_recent
      @window_baseline = window_baseline
      @sigma           = sigma
    end

    def scan
      anomalies = []
      readings = SensorReading.good_quality.where('taken_at >= ?', @window_baseline.ago).to_a
      grouped = readings.group_by { |r| [r.kind, r.zone_id] }
      grouped.each do |(kind, zone_id), all|
        baseline = all.select { |r| r.taken_at < @window_recent.ago }.map { |r| r.value.to_f }
        next if baseline.size < 30
        recent = all.select { |r| r.taken_at >= @window_recent.ago }.map { |r| r.value.to_f }
        next if recent.empty?
        mean = baseline.sum / baseline.size
        sd = Math.sqrt(baseline.sum { |v| (v - mean)**2 } / baseline.size)
        next if sd.zero?
        latest = recent.last
        if (latest - mean).abs > @sigma * sd
          anomalies << Anomaly.new(
            kind: kind, zone_id: zone_id, latest_value: latest,
            baseline_mean: mean, baseline_sd: sd, timestamp: Time.current,
          )
        end
      end
      anomalies
    end
  end
end
