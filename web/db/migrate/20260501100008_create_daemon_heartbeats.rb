class CreateDaemonHeartbeats < ActiveRecord::Migration[8.1]
  def change
    create_table :daemon_heartbeats do |t|
      t.datetime :beat_at, null: false, default: -> { 'now()' }
      t.bigint   :loop_count, null: false
      t.text     :last_error
    end
    add_index :daemon_heartbeats, :beat_at, order: { beat_at: :desc }
  end
end
