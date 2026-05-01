class CreateLLMAnalyses < ActiveRecord::Migration[8.1]
  def change
    create_table :llm_analyses do |t|
      t.datetime :ran_at,            null: false, default: -> { 'now()' }
      t.string   :kind,              null: false
      t.string   :model,             null: false
      t.integer  :input_tokens
      t.integer  :output_tokens
      t.integer  :cache_read_tokens
      t.text     :prompt_summary
      t.text     :output,            null: false
      t.decimal  :cost_usd, precision: 8, scale: 4
    end
    add_index :llm_analyses, :ran_at, order: { ran_at: :desc }
    add_index :llm_analyses, :kind
  end
end
