ROLES = ("client", "operator", "admin")
STAFF_ROLES = ("operator", "admin")

STATUSES = ("submitted", "in_progress", "delivered", "accepted", "rejected")

QUALITIES = ("good", "usable", "bad")
ASSIGNABLE_QUALITIES = ("good", "usable")

KNOWN_ROBOTS = {"arm-01", "arm-02", "arm-03", "mobile-01", "humanoid-01"}
MAX_DURATION_SECONDS = 3600  # anything longer is treated as a data error
