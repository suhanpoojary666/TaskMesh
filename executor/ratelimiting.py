from .redis_client import redis_client

#common function that takes the identifer and checks the limit for that id
def allow_request(identifier, limit):
    redis_key = f"rate_limit:{identifier}:TaskMesh"

    current_count = redis_client.get(redis_key)

    if current_count is None: #first request from past 60sec
        redis_client.set(redis_key, 1, ex=60)
        return True

    current_count = int(current_count)

    if current_count >= limit:
        return False

    redis_client.incr(redis_key)
    return True

#retrive the api_key from the request
def allow_api_key_request(request, limit):
    identifier = f"api_key:{request.auth.id}"
    return allow_request(identifier, limit)

#retrive the user_id from the request
def allow_user_request(request, limit):
    identifier = f"user:{request.user.id}"
    return allow_request(identifier, limit)

#retrive the ip address from the request
def allow_ip_request(request, limit):
    ip_address = request.META.get("REMOTE_ADDR")
    identifier = f"ip:{ip_address}"
    return allow_request(identifier, limit)