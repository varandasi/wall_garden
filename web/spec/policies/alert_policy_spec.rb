require 'rails_helper'

RSpec.describe AlertPolicy do
  subject { described_class.new(user, alert) }

  let(:alert) { Alert.new(severity: 'warn', source: 'daemon', code: 'x', message: 'm') }

  context 'as an anonymous user' do
    let(:user) { nil }
    it { is_expected.to forbid_action(:acknowledge) }
  end

  context 'as a member' do
    let(:user) { build(:user) }
    it { is_expected.to permit_action(:acknowledge) }
  end
end
