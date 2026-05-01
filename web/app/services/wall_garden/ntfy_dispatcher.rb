module WallGarden
  # Posts an alert to ntfy.sh (or a self-hosted ntfy server).
  #
  # Topic strategy: critical alerts go to NTFY_TOPIC_CRITICAL; digests and
  # informational notifications go to NTFY_TOPIC_DIGEST.
  class NtfyDispatcher
    PRIORITIES = {
      'critical' => 5,   # max
      'warn' => 4,
      'info' => 3,
    }.freeze

    def initialize(base_url: ENV.fetch('NTFY_BASE_URL', 'https://ntfy.sh'),
                   critical_topic: ENV.fetch('NTFY_TOPIC_CRITICAL', ''),
                   digest_topic:   ENV.fetch('NTFY_TOPIC_DIGEST', ''))
      @base_url = base_url
      @critical_topic = critical_topic
      @digest_topic = digest_topic
    end

    # severity: 'info' | 'warn' | 'critical'
    # tags:     array of ntfy emoji tags (see https://docs.ntfy.sh/emojis/)
    # click:    optional URL the notification opens
    def post(title:, message:, severity: 'info', tags: [], click: nil)
      topic = severity == 'critical' ? @critical_topic : @digest_topic
      return :no_topic if topic.blank?

      Faraday.post("#{@base_url}/#{topic}") do |req|
        req.headers['Title']    = title
        req.headers['Priority'] = PRIORITIES.fetch(severity, 3).to_s
        req.headers['Tags']     = Array(tags).join(',') unless tags.empty?
        req.headers['Click']    = click if click.present?
        req.body = message
      end
      :ok
    rescue Faraday::Error => e
      Rails.logger.warn("ntfy post failed: #{e.message}")
      :error
    end
  end
end
