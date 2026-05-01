FactoryBot.define do
  factory :plant_profile do
    sequence(:common_name) { |n| "Plant #{n}" }
    ideal_moisture_min { 40 }
    ideal_moisture_max { 65 }
  end

  factory :zone do
    sequence(:name) { |n| "Zone #{n}" }
    plant_profile
    ads_address { 0x48 }
    sequence(:ads_channel) { |n| n % 4 }
    sequence(:pump_gpio)   { |n| 5 + n }
    pump_ml_per_sec { 1.5 }
    moisture_dry_raw { 26000 }
    moisture_wet_raw { 12000 }
    target_moisture_pct { 55.0 }
    hysteresis_pct { 8.0 }
    max_ml_per_day { 200 }
    max_ml_per_event { 50 }
    cooldown_minutes { 60 }
  end
end
