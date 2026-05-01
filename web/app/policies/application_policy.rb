class ApplicationPolicy
  attr_reader :user, :record

  def initialize(user, record)
    @user = user
    @record = record
  end

  def index? = user.present?
  def show? = user.present?
  def create? = user.present?
  def new? = create?
  def update? = user.present?
  def edit? = update?
  def destroy? = user&.admin?

  class Scope
    def initialize(user, scope)
      @user = user
      @scope = scope
    end

    attr_reader :user, :scope

    def resolve = scope.all
  end
end
