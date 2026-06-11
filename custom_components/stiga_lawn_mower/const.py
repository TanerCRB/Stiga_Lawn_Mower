DOMAIN = "stiga_lawn_mower"
MANUFACTURER = "Stiga"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Firebase auth (from reverse-engineered Stiga app)
FIREBASE_API_KEY = "AIzaSyCPtRBU_hwWZYsguHp9ucGrfNac0kXR6ug"
FIREBASE_AUTH_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword"

# Stiga cloud API
STIGA_API_BASE_URL = "https://connectivity-production.stiga.com"

# MQTT broker config
MQTT_USERNAME = "firebaseauth|connectivity-production.stiga.com"
MQTT_PORT = 8883
MQTT_BROKER_FORMAT = "robot-mqtt-{broker_id}.stiga.com"
MQTT_BROKER_FALLBACK = "robot-mqtt-broker.stiga.com"  # works when broker_id-specific host times out
MQTT_RECONNECT_INTERVAL = 5

# Robot operation status types (from StigaAPIElements.js)
ROBOT_STATUS = {
    0: "waiting_for_command",
    1: "mowing",
    2: "going_home",
    3: "charging",
    4: "docked",
    5: "updating",
    6: "blocked",
    8: "lid_open",
    18: "calibration",
    20: "blades_calibration",
    25: "docking_calibration",
    27: "storing_data",
    28: "planning",
    29: "reaching_first_point",
    30: "navigating_to_area",
    32: "cutting_border",
    252: "startup_required",
    255: "error",
}

# Robot command IDs (from StigaAPIElements.js ROBOT_COMMAND_IDS)
ROBOT_CMD_STOP = 0
ROBOT_CMD_START = 1
ROBOT_CMD_GO_HOME = 4
ROBOT_CMD_CALIBRATE_BLADES = 26
ROBOT_CMD_STATUS_REQUEST = 28  # requests robot to publish {mac}/LOG/STATUS

# LOG_STATUS protobuf field indices (from StigaAPIDeviceConnector.js)
STATUS_FIELD_VALID = 1
STATUS_FIELD_TYPE = 3
STATUS_FIELD_ERROR = 4
STATUS_FIELD_FLAG = 5
STATUS_FIELD_BATTERY = 17
STATUS_FIELD_MOWING = 18
STATUS_FIELD_LOCATION = 19
STATUS_FIELD_NETWORK = 20

# Battery sub-message field indices
BATTERY_FIELD_CAPACITY = 1
BATTERY_FIELD_PERCENT = 2

# Mowing sub-message field indices
MOWING_FIELD_ZONE = 1
MOWING_FIELD_ZONE_COMPLETED = 2
MOWING_FIELD_GARDEN_COMPLETED = 3

# Additional STATUS field indices (from StigaAPIElements.js)
STATUS_FIELD_INFO    = 10   # info code sub-message
STATUS_FIELD_DOCKING = 13   # docking status sub-message

# Info codes (ROBOT_STATUS_INFO_CODES in StigaAPIElements.js)
INFO_CODE_LID_SENSOR   = 0x01A2   # 418
INFO_CODE_RAIN_SENSOR  = 0x01A9   # 425
INFO_CODE_LIFT_SENSOR  = 0x01B0   # 432
INFO_CODE_BUMP_SENSOR  = 0x01B1   # 433
INFO_CODE_SLOPE_SENSOR = 0x01B2   # 434

# Location sub-message field indices (STATUS field 19)
LOCATION_COVERAGE    = 1
LOCATION_SATELLITES  = 2
LOCATION_RTK_QUALITY = 5

# Network sub-message field indices (STATUS field 20 → inner field 3)
NETWORK_INNER = 3
NETWORK_RSSI  = 7
NETWORK_RSRP  = 10
NETWORK_SQ    = 11
NETWORK_RSRQ  = 12

# Settings command IDs (from ROBOT_COMMAND_IDS in StigaAPIElements.js)
ROBOT_CMD_SETTINGS_REQUEST = 17
ROBOT_CMD_SETTINGS_UPDATE  = 18

# Settings message field indices (from decodeRobotSettings in StigaAPIElements.js)
SETTINGS_FIELD_RAIN                   = 1    # sub-message {1: enabled, 2: delay_idx}
SETTINGS_FIELD_KEYBOARD_LOCK          = 2    # varint bool
SETTINGS_FIELD_ZONE_HEIGHT            = 4    # sub-message {1: enabled, 2: height_idx}
SETTINGS_FIELD_ANTI_THEFT             = 6    # varint bool
SETTINGS_FIELD_SMART_CUT              = 7    # varint bool
SETTINGS_FIELD_LONG_EXIT              = 8    # sub-message {1: distance_idx}
SETTINGS_FIELD_PUSH_NOTIFICATIONS     = 14   # sub-message {1: enabled}
SETTINGS_FIELD_OBSTACLE_NOTIFICATIONS = 15   # sub-message {1: enabled}

# Cutting height index → mm (getCuttingHeightsMap in StigaAPIElements.js)
CUTTING_HEIGHT_MAP    = {20: 0, 25: 1, 30: 2, 35: 3, 40: 4, 45: 5, 50: 6, 55: 7, 60: 8}
CUTTING_HEIGHT_BY_IDX = {0: 20, 1: 25, 2: 30, 3: 35, 4: 40, 5: 45, 6: 50, 7: 55, 8: 60}

# Rain delay index → hours (getRainDelaysMap in StigaAPIElements.js)
RAIN_DELAY_MAP    = {4: 0, 8: 1, 12: 2}
RAIN_DELAY_BY_IDX = {0: 4, 1: 8, 2: 12}

# Operation codes that indicate the robot is docked/at station
OPERATION_DOCKED   = {3, 4}    # 3=charging, 4=docked
OPERATION_CHARGING = {3}        # 3=charging
OPERATION_ERROR    = {6, 252, 255}  # 6=blocked, 252=startup_required, 255=error
OPERATION_LID_OPEN = {8}
