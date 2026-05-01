class CreateAlerts < ActiveRecord::Migration[8.1]
  def change
    create_table :alerts do |t|
      t.datetime   :fired_at, null: false, default: -> { 'now()' }
      t.string     :severity, null: false   # info | warn | critical
      t.string     :source,   null: false   # daemon | rails | llm
      t.string     :code,     null: false
      t.references :zone, foreign_key: true
      t.text       :message,  null: false
      t.datetime   :dispatched_at
      t.datetime   :acknowledged_at
    end
    add_index :alerts, :fired_at, order: { fired_at: :desc }
    add_index :alerts, :code
  end
end
