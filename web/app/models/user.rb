class User < ApplicationRecord
  devise :database_authenticatable, :recoverable, :rememberable, :validatable

  enum :role, { member: 'member', admin: 'admin' }, default: 'member', validate: true

  def admin? = role == 'admin'
end
