class PlantProfile < ApplicationRecord
  has_many :zones, dependent: :nullify

  validates :common_name, presence: true

  def self.ransackable_attributes(_auth_object = nil)
    %w[id common_name scientific_name created_at]
  end

  def self.ransackable_associations(_auth_object = nil) = %w[zones]
end
