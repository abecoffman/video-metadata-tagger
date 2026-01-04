"""Config package facade."""

from config.loader import config_from_dict, load_config
from config.models import Config, MatchingConfig, ScanConfig, TmdbConfig, WriteConfig

__all__ = [
    "Config",
    "MatchingConfig",
    "ScanConfig",
    "TmdbConfig",
    "WriteConfig",
    "config_from_dict",
    "load_config",
]
