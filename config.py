"""
应用配置
"""
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Flask
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")

    # 数据库：优先用 DATABASE_URL（如 Render PostgreSQL），否则本地 SQLite
    _db_url = os.getenv("DATABASE_URL", "")
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)
    else:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'app.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 上传
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

    # Replicate
    REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
    REPLICATE_MODEL = "qwen-edit-apps/qwen-image-edit-plus-lora-photo-to-anime"

    # 点数
    POINTS_PER_CONVERSION = 3  # 转换一张消耗的积分

    # Creem 支付
    CREEM_API_KEY = os.getenv("CREEM_API_KEY", "")
    CREEM_WEBHOOK_SECRET = os.getenv("CREEM_WEBHOOK_SECRET", "")
    CREEM_TEST_MODE = os.getenv("CREEM_TEST_MODE", "true") == "true"
    CREEM_PRODUCTS = {
        "25": os.getenv("CREEM_PRODUCT_25", ""),
        "55": os.getenv("CREEM_PRODUCT_55", ""),
        "120": os.getenv("CREEM_PRODUCT_120", ""),
    }
