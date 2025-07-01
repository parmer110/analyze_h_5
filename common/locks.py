from redlock import Redlock

# ===============================
# Distributed lock manager
# ===============================
# We create one Redlock object pointing at our Redis server.
# Any module or view can import `redlock_instance` and use it
# to synchronize across threads, processes, or even servers.
redlock_instance = Redlock([
    { "host": "localhost", "port": 6379, "db": 0 }
])
