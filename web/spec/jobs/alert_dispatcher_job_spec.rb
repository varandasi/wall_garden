require 'rails_helper'

RSpec.describe AlertDispatcherJob do
  let(:alert) do
    Alert.create!(severity: 'critical', source: 'daemon', code: 'reservoir_empty',
                  message: 'empty')
  end

  before do
    allow_any_instance_of(WallGarden::NtfyDispatcher).to receive(:post).and_return(:ok)
  end

  it 'marks the alert as dispatched' do
    described_class.new.perform(alert.id)
    expect(alert.reload.dispatched_at).to be_present
  end

  it 'is idempotent — second run does not redispatch' do
    described_class.new.perform(alert.id)
    first = alert.reload.dispatched_at
    described_class.new.perform(alert.id)
    expect(alert.reload.dispatched_at).to eq(first)
  end

  it 'enqueues the critical mailer for critical alerts' do
    expect { described_class.new.perform(alert.id) }
      .to have_enqueued_mail(AlertMailer, :critical)
  end

  it 'does not mail for non-critical alerts' do
    a = Alert.create!(severity: 'warn', source: 'daemon', code: 'sensor_stuck', message: 'x')
    expect { described_class.new.perform(a.id) }
      .not_to have_enqueued_mail(AlertMailer, :critical)
  end
end
