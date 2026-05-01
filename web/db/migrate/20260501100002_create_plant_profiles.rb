class CreatePlantProfiles < ActiveRecord::Migration[8.1]
  def change
    create_table :plant_profiles do |t|
      t.string  :common_name, null: false
      t.string  :scientific_name
      t.text    :notes
      t.decimal :ideal_moisture_min, precision: 5, scale: 2
      t.decimal :ideal_moisture_max, precision: 5, scale: 2
      t.integer :ideal_lux_min
      t.decimal :ideal_temp_c_min,   precision: 4, scale: 1
      t.decimal :ideal_temp_c_max,   precision: 4, scale: 1
      t.timestamps
    end
  end
end
