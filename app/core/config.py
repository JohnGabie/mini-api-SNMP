from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SNMP_IP: str
    SNMP_PORT: int = 161
    SNMP_COMMUNITY: str
    SNMP_BASE_OID: str
    SNMP_MAC_ADDRESS: str
    SNMP_TIMEOUT: int = 5
    SNMP_RETRIES: int = 3
    MONITORING_INTERVAL: int = 30
    LOG_LEVEL: str = "INFO"


settings = Settings()
