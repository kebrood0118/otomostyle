"""
数据库模型
"""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(128), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # 关联
    transactions = db.relationship(
        "PointTransaction", backref="user", lazy="dynamic", order_by="PointTransaction.created_at.desc()"
    )
    conversions = db.relationship(
        "Conversion", backref="user", lazy="dynamic", order_by="Conversion.created_at.desc()"
    )

    def set_password(self, password: str):
        """设置密码（存哈希，不存明文）"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """验证密码"""
        return check_password_hash(self.password_hash, password)

    def add_points(self, amount: int) -> int:
        """充值点数"""
        self.points += amount
        txn = PointTransaction(
            user_id=self.id,
            amount=amount,
            type="purchase",
            balance_after=self.points,
        )
        db.session.add(txn)
        return self.points

    def spend_points(self, amount: int) -> bool:
        """
        消费点数。返回 True 表示扣款成功，False 表示余额不足。
        """
        if self.points < amount:
            return False
        self.points -= amount
        txn = PointTransaction(
            user_id=self.id,
            amount=-amount,
            type="convert",
            balance_after=self.points,
        )
        db.session.add(txn)
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "points": self.points,
            "is_admin": self.is_admin,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PointTransaction(db.Model):
    __tablename__ = "point_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # 正=充值, 负=消费
    type = db.Column(db.String(20), nullable=False)  # "purchase" / "convert"
    balance_after = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class Conversion(db.Model):
    __tablename__ = "conversions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_filename = db.Column(db.String(256), nullable=False)
    result_url = db.Column(db.String(1024), nullable=False)
    points_cost = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
