# Register the pgvector `vector` type with the Postgres adapter so that
# reflecting on vector columns doesn't log "unknown OID" warnings.
# We map it to a plain String — model code uses `Pgvector.encode/decode`
# (or the `neighbor` gem) for round-tripping vectors.
module PgvectorTypeRegistration
  def initialize_type_map(m)
    super
    register_class_with_limit(m, 'vector', ActiveRecord::Type::String)
  end
end

ActiveSupport.on_load(:active_record_postgresqladapter) do
  ActiveRecord::ConnectionAdapters::PostgreSQLAdapter
    .singleton_class.prepend(PgvectorTypeRegistration)
end
