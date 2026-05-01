class CreateWateringEvents < ActiveRecord::Migration[8.1]
  def change
    create_table :watering_events do |t|
      t.references :zone, null: false, foreign_key: true
      t.datetime :started_at, null: false
      t.datetime :ended_at
      t.integer  :planned_ml, null: false
      t.integer  :actual_ml
      t.string   :trigger,    null: false        # auto | manual | llm_suggestion
      t.decimal  :pre_moisture_pct,  precision: 5, scale: 2
      t.decimal  :post_moisture_pct, precision: 5, scale: 2
      t.string   :aborted_reason
    end
    add_index :watering_events, %i[zone_id started_at]
  end
end
