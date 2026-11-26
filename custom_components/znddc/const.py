"""常量定义：智能电动车管家 (ZNDDC) 云端接口。"""

DOMAIN = "znddc"
NAME = "智能电动车管家"

# 云端接口地址（原 App 使用的正式域名，注意是 HTTP）
API_BASE = "http://znapi.uqbike.com/"
ACCOUNT_ID = 2  # 接口固定参数

# 配置项
CONF_ACCOUNT = "account"
CONF_LOGIN_TYPE = "login_type"
CONF_PASSWORD = "password"
CONF_MACHINE_NO = "machine_no"
CONF_MACHINE_NAME = "machine_name"
CONF_MAP_TYPE = "map_type"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ADDRESS_LOOKUP = "address_lookup"

LOGIN_TYPE_PHONE = "phone"
LOGIN_TYPE_EMAIL = "email"
LOGIN_TYPES = {
    LOGIN_TYPE_PHONE: "手机号",
    LOGIN_TYPE_EMAIL: "邮箱",
}
DEFAULT_LOGIN_TYPE = LOGIN_TYPE_PHONE

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 600
DEFAULT_MAP_TYPE = "2"
DEFAULT_ADDRESS_LOOKUP = True

# 控制指令（machine/terControl.do 的 type 参数）
CMD_LOCK = 1  # 加锁（断电设防）
CMD_UNLOCK = 2  # 解锁
CMD_START = 3  # 启动
CMD_STOP = 4  # 关闭（部分控制器不支持）
CMD_FIND = 5  # 寻车
CMD_SADDLE_LOCK = 6  # 鞍座上锁（协议存在，但鞍座锁是手动机械锁，集成不提供此按钮）
CMD_SADDLE_UNLOCK = 7  # 鞍座开锁（点动按钮）

CMD_NAMES = {
    CMD_LOCK: "加锁",
    CMD_UNLOCK: "解锁",
    CMD_START: "启动",
    CMD_STOP: "关闭",
    CMD_FIND: "寻车",
    CMD_SADDLE_LOCK: "鞍座上锁",
    CMD_SADDLE_UNLOCK: "鞍座开锁",
}

# 指令回执轮询参数（与原 App 一致：最多 10 次）
CMD_POLL_ATTEMPTS = 10
CMD_POLL_INTERVAL = 0.7

# 数据刷新节奏（秒）
TODAY_REFRESH_INTERVAL = 300  # 今日里程
HISTORY_REFRESH_INTERVAL = 1800  # 近 7 天里程
HISTORY_DAYS = 7
ADDRESS_REFRESH_INTERVAL = 60

PLATFORMS = ["switch", "button", "sensor", "binary_sensor", "device_tracker"]
