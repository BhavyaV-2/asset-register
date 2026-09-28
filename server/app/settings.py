import os
from datetime import datetime
from zoneinfo import ZoneInfo

def today():
    return datetime.now(ZoneInfo(os.getenv('TIME_ZONE','Asia/Kolkata'))).date()

def secret():
    value = os.environ.get('SECRET_KEY','')
    if len(value) < 32:
        raise ValueError('Set SECRET_KEY to at least 32 random characters.')
    return value

def upload_limit():
    return int(os.getenv('MAX_UPLOAD_MB','25')) * 1024 * 1024
