require_relative 'boot'

require 'rails'
# Pick the frameworks you want — pruning what we don't use keeps boot fast.
require 'active_model/railtie'
require 'active_job/railtie'
require 'active_record/railtie'
require 'active_storage/engine'
require 'action_controller/railtie'
require 'action_mailer/railtie'
require 'action_view/railtie'
require 'action_cable/engine'
# require 'action_text/engine'   # not used in v1
# require 'action_mailbox/engine'

require 'rails/test_unit/railtie'

Bundler.require(*Rails.groups)

module WallGarden
  class Application < Rails::Application
    config.load_defaults 8.1

    config.autoload_lib(ignore: %w[assets tasks])

    # Eager-load app/ai so the LLM client classes are available in jobs.
    config.autoload_paths << "#{root}/app/ai"
    config.eager_load_paths << "#{root}/app/ai"

    # Default time zone in UTC; the Daemon writes UTC and Rails serves locally
    # via I18n.l(format: :short).
    config.time_zone = 'UTC'
    config.active_record.default_timezone = :utc

    config.i18n.available_locales = %i[en pt]
    config.i18n.default_locale = :en
    config.i18n.fallbacks = [:en]

    # SolidQueue is the Active Job adapter (no Redis).
    config.active_job.queue_adapter = :solid_queue

    # Generators — keep things tidy for new Rails generators.
    config.generators do |g|
      g.test_framework :rspec, fixture: true, view_specs: false, helper_specs: false, routing_specs: false
      g.fixture_replacement :factory_bot, dir: 'spec/factories'
    end
  end
end
