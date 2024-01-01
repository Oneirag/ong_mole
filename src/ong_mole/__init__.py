import loguru
from ong_utils import OngConfig

_cfg = OngConfig("ong_mole", default_app_cfg={
    "server": "put your mole server here",
})

config = _cfg.config
test_config = _cfg.config_test
server = config("server")

logger = loguru.logger

