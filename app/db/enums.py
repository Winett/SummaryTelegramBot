import enum

class AdminRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    SUPPORT = "support"