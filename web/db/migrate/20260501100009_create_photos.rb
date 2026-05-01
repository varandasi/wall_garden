class CreatePhotos < ActiveRecord::Migration[8.1]
  def change
    create_table :photos do |t|
      t.datetime   :taken_at, null: false
      t.string     :path, null: false
      t.references :zone, foreign_key: true
      t.bigint     :llm_analysis_id
      t.column     :embedding, 'vector(1536)'
    end
    add_index :photos, :taken_at, order: { taken_at: :desc }
  end
end
