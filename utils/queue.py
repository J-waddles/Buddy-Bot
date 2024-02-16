
# Existing queue for random connections
user_queue = []

# New dictionary for request-based connections
# Format: {requester_id: requested_user_id}
request_queue = {}

# Add a user to the random queue
def enqueue_user(user_id):
    if user_id not in user_queue:
        user_queue.append(user_id)

# Remove a user from the random queue
def dequeue_user():
    return user_queue.pop(0) if user_queue else None

# Check if the random queue has enough users for a pair
def is_pair_available():
    return len(user_queue) >= 2

# Get the next pair from the random queue
def get_next_pair():
    if is_pair_available():
        return dequeue_user(), dequeue_user()

# Add a connection request
def add_request(requester_id, requested_user_id):
    if requester_id not in request_queue:
        request_queue[requester_id] = requested_user_id

# Check if there is a pending request for a user
def is_request_pending(user_id):
    return user_id in request_queue.values()

# Get the requester for a pending request
def get_requester(requested_user_id):
    for requester, requested in request_queue.items():
        if requested == requested_user_id:
            return requester
    return None

# Remove a request from the request queue
def remove_request(requester_id):
    if requester_id in request_queue:
        del request_queue[requester_id]
