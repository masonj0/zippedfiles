import json

try:
    with open("config_settings.json", "r") as f:
        config = json.load(f)

    schema_version = config.get("SCHEMA_VERSION")
    data_sources_count = len(config.get("DATA_SOURCES_V2", {}))

    print(f"Verification successful.")
    print(f"Schema Version: {schema_version}")
    print(f"Number of V2 Data Sources: {data_sources_count}")

except Exception as e:
    print(f"Verification failed: {e}")
