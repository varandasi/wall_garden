module Ai
  # Convenience wrapper around Client for image-bearing prompts.
  class VisionClient
    DEFAULT_MODEL = 'claude-sonnet-4-6'

    def initialize(model: DEFAULT_MODEL)
      @client = Client.new(model: model)
    end

    def analyze(image_path:, prompt:, system: nil, cached_blocks: [])
      prepared = ImagePreparer.prepare(image_path)
      @client.chat(prompt: prompt, image: prepared, system: system,
                   cached_blocks: cached_blocks, kind: 'photo')
    end
  end
end
