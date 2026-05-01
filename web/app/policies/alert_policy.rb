class AlertPolicy < ApplicationPolicy
  def acknowledge? = user.present?

  class Scope < Scope
    def resolve = scope.all
  end
end
