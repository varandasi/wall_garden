class CreateCommands < ActiveRecord::Migration[8.1]
  def change
    create_table :commands do |t|
      t.string   :kind, null: false
      t.jsonb    :payload, null: false, default: {}
      t.string   :status,  null: false, default: 'pending'
      t.datetime :requested_at, null: false, default: -> { 'now()' }
      t.datetime :claimed_at
      t.datetime :completed_at
      t.jsonb    :result
      t.string   :requested_by
    end
    add_index :commands, %i[status requested_at], where: "status = 'pending'", name: 'idx_commands_pending'
  end
end
