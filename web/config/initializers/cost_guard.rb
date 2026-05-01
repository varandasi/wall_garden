# Read-only access to the LLM cost cap. Slice 6 wires WallGarden::CostGuard
# to enforce it; this initializer just normalises the env var.
WALLGARDEN_LLM_COST_CAP_USD = Float(ENV.fetch('MONTHLY_LLM_COST_CAP_USD', '5'))
