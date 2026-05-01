module Ai
  # Thin wrapper around ruby_llm targeting Anthropic.
  #
  # Why a wrapper:
  # - Single place to swap models or providers.
  # - Captures token usage + cost into `llm_analyses` after each call.
  # - Maps ruby_llm errors to the Ai::* hierarchy so callers catch one root.
  # - Supports prompt caching via `with_instructions(text, cache: true)`.
  #
  # Cost model: per-MTok prices for the two Claude models we use. Update if
  # Anthropic changes pricing.
  class Client
    DEFAULT_PROVIDER = :anthropic
    DEFAULT_TEMPERATURE = 0.2

    PRICES_USD_PER_MTOK = {
      'claude-sonnet-4-6'              => { input: 3.0,  output: 15.0, cache_read: 0.30 },
      'claude-haiku-4-5-20251001'      => { input: 1.0,  output: 5.0,  cache_read: 0.10 },
    }.freeze

    attr_reader :model

    def initialize(model:, provider: DEFAULT_PROVIDER, temperature: DEFAULT_TEMPERATURE)
      @model = model
      @provider = provider
      @temperature = temperature
    end

    # Send one or more turns and return the assistant's text content.
    #
    # @param prompt [String] the user message text.
    # @param system [String, nil] cacheable system instructions.
    # @param cached_blocks [Array<String>] additional cacheable instruction blocks
    #   (e.g., plant profiles + last week's report). Each is added with cache: true.
    # @param image [String, Pathname, nil] optional path to a JPEG for vision.
    # @param kind [String] kind label persisted to llm_analyses.
    def chat(prompt:, system: nil, cached_blocks: [], image: nil, kind: 'chat')
      chat = RubyLLM.chat(model: @model, provider: @provider, assume_model_exists: true)
      chat.with_temperature(@temperature)

      chat.with_instructions(system, cache: true) if system.present?
      cached_blocks.each { |blk| chat.with_instructions(blk, cache: true) }

      response = image ? chat.ask(prompt, with: image) : chat.ask(prompt)
      record_analysis!(kind: kind, prompt: prompt, response: response)
      response.content
    rescue RubyLLM::Error => e
      raise translate_error(e)
    end

    private

    def record_analysis!(kind:, prompt:, response:)
      input  = response.input_tokens.to_i
      output = response.output_tokens.to_i
      cache_read = response.respond_to?(:cache_read_tokens) ? response.cache_read_tokens.to_i : 0
      cost = compute_cost(input, output, cache_read)
      LlmAnalysis.create!(
        kind: kind, model: @model,
        input_tokens: input, output_tokens: output, cache_read_tokens: cache_read,
        prompt_summary: prompt.to_s.truncate(500),
        output: response.content.to_s,
        cost_usd: cost,
      )
    rescue ActiveRecord::ActiveRecordError => e
      Rails.logger.warn("LlmAnalysis insert failed: #{e.class}: #{e.message}")
    end

    def compute_cost(input_tokens, output_tokens, cache_read_tokens)
      prices = PRICES_USD_PER_MTOK[@model]
      return 0.0 unless prices
      (
        input_tokens     * prices[:input]      +
        output_tokens    * prices[:output]     +
        cache_read_tokens * prices[:cache_read]
      ) / 1_000_000.0
    end

    def translate_error(err)
      msg = err.message
      case msg
      when /authentication/i, /api_key/i then Ai::AuthenticationError.new(msg)
      when /rate.?limit/i                then Ai::RateLimitError.new(msg)
      when /timeout/i, /timed.?out/i     then Ai::TimeoutError.new(msg)
      when /unreachable/i, /network/i, /connection/i then Ai::UnreachableError.new(msg)
      else Ai::Error.new(msg)
      end
    end
  end
end
