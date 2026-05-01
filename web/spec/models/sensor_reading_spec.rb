require 'rails_helper'

RSpec.describe SensorReading, type: :model do
  let(:zone) { create(:zone) }

  it 'rejects unknown kinds' do
    r = SensorReading.new(taken_at: Time.current, kind: 'wrong', value: 1, unit: 'x')
    expect(r).not_to be_valid
  end

  describe '.latest' do
    it 'returns the most recent reading of a kind, optionally per-zone' do
      SensorReading.create!(taken_at: 5.minutes.ago, kind: 'air_temp_c', value: 20, unit: 'c')
      SensorReading.create!(taken_at: 1.minute.ago,  kind: 'air_temp_c', value: 22, unit: 'c')
      expect(SensorReading.latest(kind: 'air_temp_c').value.to_f).to eq(22.0)
    end
  end

  describe '.good_quality' do
    it 'excludes implausible readings' do
      SensorReading.create!(taken_at: Time.current, kind: 'air_temp_c', value: 22, unit: 'c', quality: 1)
      SensorReading.create!(taken_at: Time.current, kind: 'air_temp_c', value: 999, unit: 'c', quality: 0)
      expect(SensorReading.good_quality.count).to eq(1)
    end
  end
end
