"""
Shared application state for ShadowX bot (local module)
Avoids using Bot object for arbitrary attributes.
"""

# In-memory user state
user_data = {}

# In-memory moderation queue (messages and university change requests)
moderation_queue = {}

# Queue manager instance (initialized on startup)
queue_manager = None


