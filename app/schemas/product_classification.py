from enum import Enum


class SportType(str, Enum):
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    RUNNING = "running"
    CASUAL = "casual"


class UsageType(str, Enum):
    LIFESTYLE = "lifestyle"
    PERFORMANCE = "performance"


class StyleGroup(str, Enum):
    BASKETBALL_LIFESTYLE = "basketball_lifestyle"
    FOOTBALL_BOOTS = "football_boots"
    RUNNING_LIFESTYLE = "running_lifestyle"
    LIFESTYLE_SNEAKERS = "lifestyle_sneakers"