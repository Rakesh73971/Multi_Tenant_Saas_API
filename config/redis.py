import redis
from django.conf import settings

def get_redis_client():
    """
    Returns a Redis client instance configured with settings.REDIS_URL.
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
