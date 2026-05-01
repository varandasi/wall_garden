require 'rails_helper'

RSpec.describe WallGarden::AnomalyDetector do
  let(:zone) { create(:zone) }

  it 'returns nothing when there is too little baseline' do
    expect(described_class.new.scan).to be_empty
  end

  it 'flags a recent reading well outside ±2σ of baseline' do
    base_time = 5.days.ago
    50.times do |i|
      zone.sensor_readings.create!(
        taken_at: base_time + i.minutes, kind: 'soil_moisture_pct',
        value: 50 + rand(-1..1), unit: 'pct', quality: 1,
      )
    end
    zone.sensor_readings.create!(
      taken_at: 1.minute.ago, kind: 'soil_moisture_pct',
      value: 95, unit: 'pct', quality: 1,
    )
    anomalies = described_class.new.scan
    expect(anomalies.first.zone_id).to eq(zone.id)
    expect(anomalies.first.kind).to eq('soil_moisture_pct')
  end
end
