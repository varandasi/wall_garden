require 'rails_helper'

RSpec.describe ZonePolicy do
  subject { described_class.new(user, zone) }

  let(:zone) { build(:zone) }

  context 'as an anonymous user' do
    let(:user) { nil }
    it { is_expected.to forbid_actions(%i[index show update destroy]) }
  end

  context 'as a signed-in member' do
    let(:user) { build(:user, role: 'member') }
    it { is_expected.to permit_actions(%i[index show update]) }
    it { is_expected.to forbid_action(:destroy) }
  end

  context 'as an admin' do
    let(:user) { build(:user, :admin) }
    it { is_expected.to permit_actions(%i[index show update destroy]) }
  end
end
