class ZonePolicy < ApplicationPolicy
  # Single-household app: any signed-in user can read & control zones.
  # Destruction is admin-only (zones rarely get deleted; safety bias).
  def update? = user.present?
  def destroy? = user&.admin?

  class Scope < Scope
    def resolve = scope.all
  end
end
