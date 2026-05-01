require 'rails_helper'

RSpec.describe Ai::Client do
  it 'computes per-call cost from token counts and the model price table' do
    client = described_class.new(model: 'claude-haiku-4-5-20251001')
    cost = client.send(:compute_cost, 1_000_000, 100_000, 500_000)
    # 1M input * $1 + 100k output * $5/M + 500k cache_read * $0.10/M
    # = 1.0 + 0.5 + 0.05 = 1.55
    expect(cost).to be_within(0.001).of(1.55)
  end

  it 'translates ruby_llm errors into Ai::* equivalents' do
    client = described_class.new(model: 'claude-haiku-4-5-20251001')
    expect(client.send(:translate_error, RubyLLM::Error.new('rate_limit hit')))
      .to be_a(Ai::RateLimitError)
    expect(client.send(:translate_error, RubyLLM::Error.new('authentication failed')))
      .to be_a(Ai::AuthenticationError)
    expect(client.send(:translate_error, RubyLLM::Error.new('connection timed out')))
      .to be_a(Ai::TimeoutError)
  end
end
