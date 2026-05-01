class CreateSensorReadings < ActiveRecord::Migration[8.1]
  def change
    create_table :sensor_readings do |t|
      t.datetime   :taken_at, null: false
      t.references :zone, foreign_key: true
      t.string     :kind, null: false
      t.decimal    :raw,    precision: 10, scale: 3
      t.decimal    :value,  precision: 10, scale: 3, null: false
      t.string     :unit,   null: false
      t.integer    :quality, limit: 2, null: false, default: 1
    end
    add_index :sensor_readings, :taken_at, order: { taken_at: :desc }
    add_index :sensor_readings, %i[zone_id kind taken_at], order: { taken_at: :desc }
  end
end
