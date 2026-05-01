require 'rails_helper'

RSpec.describe WallGarden::NtfyDispatcher do
  it 'returns :no_topic when topic env vars are blank' do
    dispatcher = described_class.new(critical_topic: '', digest_topic: '')
    expect(dispatcher.post(title: 't', message: 'm', severity: 'info')).to eq(:no_topic)
  end

  it 'POSTs to the critical topic when severity=critical' do
    stub_request(:post, 'https://ntfy.sh/wg-crit')
      .with(headers: { 'Title' => 'T', 'Priority' => '5' })
      .to_return(status: 200)
    dispatcher = described_class.new(critical_topic: 'wg-crit', digest_topic: 'wg-dig')
    expect(dispatcher.post(title: 'T', message: 'm', severity: 'critical')).to eq(:ok)
  end

  it 'POSTs to the digest topic for non-critical severities' do
    stub_request(:post, 'https://ntfy.sh/wg-dig').to_return(status: 200)
    dispatcher = described_class.new(critical_topic: 'wg-crit', digest_topic: 'wg-dig')
    expect(dispatcher.post(title: 'T', message: 'm', severity: 'info')).to eq(:ok)
  end
end
