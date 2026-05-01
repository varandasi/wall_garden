FactoryBot.define do
  factory :user do
    sequence(:email) { |n| "user#{n}@wallgarden.local" }
    password { 'password123' }
    role { 'member' }

    trait :admin do
      role { 'admin' }
    end
  end
end
