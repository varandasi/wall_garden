require 'rails_helper'

RSpec.describe Zone, type: :model do
  subject(:zone) { build(:zone) }

  it 'is valid with the factory' do
    expect(zone).to be_valid
  end

  it 'requires a unique name' do
    create(:zone, name: 'Top-left')
    expect(build(:zone, name: 'Top-left')).not_to be_valid
  end

  describe '#latest_moisture' do
    it 'returns the most recent soil_moisture_pct value' do
      zone.save!
      zone.sensor_readings.create!(taken_at: 1.minute.ago, kind: 'soil_moisture_pct',
                                   value: 40.0, unit: 'pct')
      zone.sensor_readings.create!(taken_at: 10.seconds.ago, kind: 'soil_moisture_pct',
                                   value: 55.0, unit: 'pct')
      expect(zone.latest_moisture).to eq(55.0)
    end
  end

  describe '#thirsty?' do
    before { zone.save! }

    it 'is true when moisture sits below the lower dead-band' do
      zone.sensor_readings.create!(taken_at: Time.current, kind: 'soil_moisture_pct',
                                   value: 40.0, unit: 'pct')
      expect(zone).to be_thirsty
    end

    it 'is false inside the dead-band' do
      zone.sensor_readings.create!(taken_at: Time.current, kind: 'soil_moisture_pct',
                                   value: 53.0, unit: 'pct')
      expect(zone).not_to be_thirsty
    end
  end

  describe '#ml_today' do
    it 'sums actual_ml across today\'s completed events' do
      zone.save!
      zone.watering_events.create!(started_at: 6.hours.ago, ended_at: 6.hours.ago + 10.seconds,
                                    planned_ml: 30, actual_ml: 30, trigger: 'auto')
      zone.watering_events.create!(started_at: 2.hours.ago, ended_at: 2.hours.ago + 10.seconds,
                                    planned_ml: 20, actual_ml: 20, trigger: 'auto')
      zone.watering_events.create!(started_at: 30.hours.ago, ended_at: 30.hours.ago + 10.seconds,
                                    planned_ml: 50, actual_ml: 50, trigger: 'auto')
      expect(zone.ml_today).to eq(50)
    end
  end
end
