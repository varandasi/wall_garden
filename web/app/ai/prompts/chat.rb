module Ai
  module Prompts
    class Chat
      MODEL = 'claude-haiku-4-5-20251001'

      SYSTEM = <<~MD.freeze
        You are the wall garden's caretaker assistant. The user can ask about
        any zone, plant, alert, or recent watering. Answer with concrete
        numbers from the supplied recent_data block. If asked for a manual
        watering, refuse politely and tell them to use the dashboard's "Water
        now" button (which respects safety interlocks).
      MD

      def self.build(question:, recent_data:)
        {
          system: SYSTEM,
          cached_blocks: ["<recent_data>\n#{recent_data}\n</recent_data>"],
          prompt: question,
          model: MODEL,
          kind: 'chat',
        }
      end
    end
  end
end
