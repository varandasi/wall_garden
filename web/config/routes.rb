Rails.application.routes.draw do
  devise_for :users, controllers: { sessions: 'users/sessions' }

  authenticate :user do
    root 'dashboard#index'

    resources :zones, only: %i[index show edit update] do
      member do
        post :water
        patch :enable
        patch :disable
      end
    end

    resources :alerts, only: %i[index] do
      member do
        post :acknowledge
      end
    end

    resources :plant_profiles
    resources :photos, only: %i[index show]

    resource :chat, only: %i[show create]   # ad-hoc Q&A with Claude (Slice 6)

    namespace :admin do
      get :llm_costs, to: 'llm_costs#index', as: :llm_costs
    end

    mount MissionControl::Jobs::Engine, at: '/jobs'
  end

  # Health check (Kamal / load balancer probe).
  get 'up', to: 'rails/health#show', as: :rails_health_check
end
