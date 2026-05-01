# Seeds — idempotent. Safe to run repeatedly.

# Default user. Change the password after first sign-in.
User.find_or_create_by!(email: 'me@wallgarden.local') do |u|
  u.password = 'wallgarden'
  u.password_confirmation = 'wallgarden'
  u.role = 'admin'
end

# A few starter plant profiles you can attach to zones.
basil = PlantProfile.find_or_create_by!(common_name: 'Basil') do |p|
  p.scientific_name = 'Ocimum basilicum'
  p.notes = 'Likes warm, bright, evenly moist. Avoid letting soil dry below 35%.'
  p.ideal_moisture_min = 45
  p.ideal_moisture_max = 65
  p.ideal_lux_min = 8000
  p.ideal_temp_c_min = 18
  p.ideal_temp_c_max = 28
end

mint = PlantProfile.find_or_create_by!(common_name: 'Mint') do |p|
  p.scientific_name = 'Mentha spicata'
  p.notes = 'Tolerates wetter soil. Will take over if given the chance.'
  p.ideal_moisture_min = 50
  p.ideal_moisture_max = 75
end

PlantProfile.find_or_create_by!(common_name: 'Pothos') do |p|
  p.scientific_name = 'Epipremnum aureum'
  p.notes = 'Forgiving. Lets you get away with the longest cooldowns.'
  p.ideal_moisture_min = 30
  p.ideal_moisture_max = 60
end

# Four default zones matching daemon/config/hardware.yml.
[
  { id: 1, name: 'Top-left',  ads_channel: 0, pump_gpio: 5,  profile: basil },
  { id: 2, name: 'Top-right', ads_channel: 1, pump_gpio: 6,  profile: mint },
  { id: 3, name: 'Bot-left',  ads_channel: 2, pump_gpio: 13, profile: basil },
  { id: 4, name: 'Bot-right', ads_channel: 3, pump_gpio: 16, profile: mint },
].each do |z|
  Zone.find_or_create_by!(name: z[:name]) do |zone|
    zone.ads_address = 0x48
    zone.ads_channel = z[:ads_channel]
    zone.pump_gpio = z[:pump_gpio]
    zone.plant_profile = z[:profile]
  end
end

puts "Seeded #{User.count} user, #{PlantProfile.count} plant profiles, #{Zone.count} zones."
