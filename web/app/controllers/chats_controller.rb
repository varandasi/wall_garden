class ChatsController < ApplicationController
  def show
    @messages = session[:chat_messages] || []
  end

  def create
    question = params[:question].to_s.strip
    return redirect_to(chat_path) if question.blank?

    answer =
      if WallGarden::CostGuard.affordable?
        spec = Ai::Prompts::Chat.build(question: question, recent_data: build_recent_context)
        Ai::Client.new(model: spec[:model]).chat(
          prompt: spec[:prompt], system: spec[:system],
          cached_blocks: spec[:cached_blocks], kind: spec[:kind],
        )
      else
        'Monthly LLM budget exceeded — pause until next month or raise the cap.'
      end

    session[:chat_messages] = (session[:chat_messages] || []) + [
      { role: 'user', text: question, at: Time.current.iso8601 },
      { role: 'assistant', text: answer, at: Time.current.iso8601 },
    ].last(20)

    redirect_to chat_path, status: :see_other
  rescue Ai::Error => e
    redirect_to chat_path, alert: "Chat failed: #{e.message}", status: :see_other
  end

  private

  def build_recent_context
    lines = []
    Zone.order(:id).each do |z|
      m = z.latest_moisture
      lines << "Zone #{z.id} (#{z.name}): moisture #{m ? m.round(1) : '?'}%, today's water #{z.ml_today.to_i} mL"
    end
    lines << ''
    lines << "Recent alerts: #{Alert.recent(24.hours).count}, " \
             "unacknowledged: #{Alert.unacknowledged.count}"
    lines.join("\n")
  end
end
