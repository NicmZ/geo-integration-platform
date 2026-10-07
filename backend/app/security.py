# -*- coding: utf-8 -*-
"""安全：JWT、密码哈希、图片验证码、sk- 接入码"""
import base64
import io
import random
import secrets
import string
import time
from datetime import datetime, timedelta

from jose import jwt, JWTError
from passlib.context import CryptContext
from PIL import Image, ImageDraw, ImageFont

from app.config import settings

pwd_ctx = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# 验证码内存存储：captcha_token -> (code, expire_ts)，TTL 5 分钟
_CAPTCHA_STORE = {}

ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")


# ---------- 密码 ----------

def hash_password(raw: str) -> str:
    return pwd_ctx.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_ctx.verify(raw, hashed)
    except Exception:
        return False


# ---------- JWT ----------

def create_token(user_id: int) -> str:
    payload = {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=settings.TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str):
    """返回 user_id(int) 或 None"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None


# ---------- 接入码 sk- ----------

def new_geo_token() -> str:
    return "sk-geo-" + secrets.token_hex(16)


# ---------- 验证码 ----------

def gen_captcha():
    """4 位验证码（去除 O/0/I/1），返回 (captcha_token, base64_png)"""
    code = "".join(random.choice(ALPHABET) for _ in range(4))
    token = secrets.token_hex(16)
    _CAPTCHA_STORE[token] = (code, time.time() + 300)

    img = Image.new("RGB", (160, 56), (245, 247, 250))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except Exception:
        font = ImageFont.load_default()
    for i, ch in enumerate(code):
        x = 18 + i * 34 + random.randint(-3, 3)
        y = 8 + random.randint(-4, 4)
        color = (random.randint(20, 120), random.randint(30, 130), random.randint(120, 220))
        draw.text((x, y), ch, fill=color, font=font)
    for _ in range(5):  # 干扰线
        x1, y1 = random.randint(0, 160), random.randint(0, 56)
        x2, y2 = random.randint(0, 160), random.randint(0, 56)
        draw.line((x1, y1, x2, y2), fill=(random.randint(120, 220),) * 3, width=1)
    for _ in range(120):  # 噪点
        draw.point((random.randint(0, 160), random.randint(0, 56)), fill=(200, 200, 200))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return token, "data:image/png;base64," + b64


def check_captcha(token: str, code: str) -> bool:
    item = _CAPTCHA_STORE.pop(token, None)
    if not item:
        return False
    real, expire = item
    if time.time() > expire:
        return False
    return str(code).strip().upper() == real
