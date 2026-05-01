# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[8.1].define(version: 2026_05_01_100011) do
  # These are extensions that must be enabled in order to support this database
  enable_extension "pg_catalog.plpgsql"
  enable_extension "vector"

  create_table "alerts", force: :cascade do |t|
    t.datetime "acknowledged_at"
    t.string "code", null: false
    t.datetime "dispatched_at"
    t.datetime "fired_at", default: -> { "now()" }, null: false
    t.text "message", null: false
    t.string "severity", null: false
    t.string "source", null: false
    t.bigint "zone_id"
    t.index ["code"], name: "index_alerts_on_code"
    t.index ["fired_at"], name: "index_alerts_on_fired_at", order: :desc
    t.index ["zone_id"], name: "index_alerts_on_zone_id"
  end

  create_table "commands", force: :cascade do |t|
    t.datetime "claimed_at"
    t.datetime "completed_at"
    t.string "kind", null: false
    t.jsonb "payload", default: {}, null: false
    t.datetime "requested_at", default: -> { "now()" }, null: false
    t.string "requested_by"
    t.jsonb "result"
    t.string "status", default: "pending", null: false
    t.index ["status", "requested_at"], name: "idx_commands_pending", where: "((status)::text = 'pending'::text)"
  end

  create_table "daemon_heartbeats", force: :cascade do |t|
    t.datetime "beat_at", default: -> { "now()" }, null: false
    t.text "last_error"
    t.bigint "loop_count", null: false
    t.index ["beat_at"], name: "index_daemon_heartbeats_on_beat_at", order: :desc
  end

  create_table "llm_analyses", force: :cascade do |t|
    t.integer "cache_read_tokens"
    t.decimal "cost_usd", precision: 8, scale: 4
    t.integer "input_tokens"
    t.string "kind", null: false
    t.string "model", null: false
    t.text "output", null: false
    t.integer "output_tokens"
    t.text "prompt_summary"
    t.datetime "ran_at", default: -> { "now()" }, null: false
    t.index ["kind"], name: "index_llm_analyses_on_kind"
    t.index ["ran_at"], name: "index_llm_analyses_on_ran_at", order: :desc
  end

  create_table "photos", force: :cascade do |t|
    t.string "embedding", limit: 1536
    t.bigint "llm_analysis_id"
    t.string "path", null: false
    t.datetime "taken_at", null: false
    t.bigint "zone_id"
    t.index ["taken_at"], name: "index_photos_on_taken_at", order: :desc
    t.index ["zone_id"], name: "index_photos_on_zone_id"
  end

  create_table "plant_profiles", force: :cascade do |t|
    t.string "common_name", null: false
    t.datetime "created_at", null: false
    t.integer "ideal_lux_min"
    t.decimal "ideal_moisture_max", precision: 5, scale: 2
    t.decimal "ideal_moisture_min", precision: 5, scale: 2
    t.decimal "ideal_temp_c_max", precision: 4, scale: 1
    t.decimal "ideal_temp_c_min", precision: 4, scale: 1
    t.text "notes"
    t.string "scientific_name"
    t.datetime "updated_at", null: false
  end

  create_table "sensor_readings", force: :cascade do |t|
    t.string "kind", null: false
    t.integer "quality", limit: 2, default: 1, null: false
    t.decimal "raw", precision: 10, scale: 3
    t.datetime "taken_at", null: false
    t.string "unit", null: false
    t.decimal "value", precision: 10, scale: 3, null: false
    t.bigint "zone_id"
    t.index ["taken_at"], name: "index_sensor_readings_on_taken_at", order: :desc
    t.index ["zone_id", "kind", "taken_at"], name: "index_sensor_readings_on_zone_id_and_kind_and_taken_at", order: { taken_at: :desc }
    t.index ["zone_id"], name: "index_sensor_readings_on_zone_id"
  end

  create_table "users", force: :cascade do |t|
    t.datetime "created_at", null: false
    t.string "email", default: "", null: false
    t.string "encrypted_password", default: "", null: false
    t.datetime "remember_created_at"
    t.datetime "reset_password_sent_at"
    t.string "reset_password_token"
    t.string "role", default: "member", null: false
    t.datetime "updated_at", null: false
    t.index ["email"], name: "index_users_on_email", unique: true
    t.index ["reset_password_token"], name: "index_users_on_reset_password_token", unique: true
  end

  create_table "watering_events", force: :cascade do |t|
    t.string "aborted_reason"
    t.integer "actual_ml"
    t.datetime "ended_at"
    t.integer "planned_ml", null: false
    t.decimal "post_moisture_pct", precision: 5, scale: 2
    t.decimal "pre_moisture_pct", precision: 5, scale: 2
    t.datetime "started_at", null: false
    t.string "trigger", null: false
    t.bigint "zone_id", null: false
    t.index ["zone_id", "started_at"], name: "index_watering_events_on_zone_id_and_started_at"
    t.index ["zone_id"], name: "index_watering_events_on_zone_id"
  end

  create_table "zones", force: :cascade do |t|
    t.integer "ads_address", null: false
    t.integer "ads_channel", null: false
    t.integer "cooldown_minutes", default: 60, null: false
    t.datetime "created_at", null: false
    t.boolean "enabled", default: true, null: false
    t.decimal "hysteresis_pct", precision: 5, scale: 2, default: "8.0", null: false
    t.integer "max_ml_per_day", default: 200, null: false
    t.integer "max_ml_per_event", default: 50, null: false
    t.integer "moisture_dry_raw", default: 26000, null: false
    t.integer "moisture_wet_raw", default: 12000, null: false
    t.string "name", null: false
    t.bigint "plant_profile_id"
    t.integer "pump_gpio", null: false
    t.decimal "pump_ml_per_sec", precision: 6, scale: 3, default: "1.5", null: false
    t.decimal "target_moisture_pct", precision: 5, scale: 2, default: "55.0", null: false
    t.datetime "updated_at", null: false
    t.index ["plant_profile_id"], name: "index_zones_on_plant_profile_id"
  end

  add_foreign_key "alerts", "zones"
  add_foreign_key "photos", "zones"
  add_foreign_key "sensor_readings", "zones"
  add_foreign_key "watering_events", "zones"
  add_foreign_key "zones", "plant_profiles"
end
