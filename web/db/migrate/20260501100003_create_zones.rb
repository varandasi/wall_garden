class CreateZones < ActiveRecord::Migration[8.1]
  def change
    create_table :zones do |t|
      t.string     :name, null: false
      t.references :plant_profile, foreign_key: true
      t.integer    :ads_address,   null: false
      t.integer    :ads_channel,   null: false
      t.integer    :pump_gpio,     null: false
      t.decimal    :pump_ml_per_sec,      precision: 6, scale: 3, null: false, default: 1.5
      t.integer    :moisture_dry_raw,  null: false, default: 26000
      t.integer    :moisture_wet_raw,  null: false, default: 12000
      t.decimal    :target_moisture_pct, precision: 5, scale: 2, null: false, default: 55.0
      t.decimal    :hysteresis_pct,      precision: 5, scale: 2, null: false, default: 8.0
      t.integer    :max_ml_per_day,      null: false, default: 200
      t.integer    :max_ml_per_event,    null: false, default: 50
      t.integer    :cooldown_minutes,    null: false, default: 60
      t.boolean    :enabled, null: false, default: true
      t.timestamps
    end
  end
end
