"""
照片转大友克洋卡通画风 — 会员制收费网站
"""
import os
import hmac
import hashlib
import uuid
import json
from pathlib import Path
from functools import wraps

import requests
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash,
)
from dotenv import load_dotenv
import replicate

from config import Config
from models import db, User, Conversion
from translations import T


def t(key, **kwargs):
    """Return translation for `key` in the current session language."""
    lang = session.get("lang", "zh")
    if lang not in ("zh", "en"):
        lang = "zh"
    text = T.get(key, {}).get(lang)
    if text is None:
        text = T.get(key, {}).get("zh", key)
    if kwargs:
        text = text.format(**kwargs)
    return text


load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

# Make t() available in all Jinja2 templates
app.jinja_env.globals["t"] = t

# 初始化数据库
db.init_app(app)

# 确保上传目录和数据库目录存在
Path(Config.UPLOAD_FOLDER).mkdir(exist_ok=True)
Path("instance").mkdir(exist_ok=True)

# 确保数据库表已创建（gunicorn 启动时不会走 __main__ 分支）
with app.app_context():
    db.create_all()

# 大友克洋画风 Prompt
OTOMO_PROMPT = (
    "Akira manga style, Katsuhiro Otomo art style, "
    "hand-drawn cel animation, 1980s retro anime, "
    "bold dark ink lines, dramatic high-contrast lighting, "
    "detailed mechanical and urban background, "
    "cyberpunk aesthetic, cinematic composition, "
    "muted color palette with occasional vibrant accents, "
    "masterpiece, high quality"
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# ============================================================
# 装饰器：要求登录
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": t("login_required")}), 401
            flash(t("login_required"), "warning")
            return redirect(url_for("login"))
        # 确认用户仍然存在（数据库重置后可能不存在）
        user = db.session.get(User, session["user_id"])
        if user is None:
            session.clear()
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": t("login_required")}), 401
            flash(t("login_required"), "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ============================================================
# 全局上下文：所有模板共享
# ============================================================
@app.context_processor
def inject_user():
    """向所有模板注入当前用户信息和语言"""
    lang = session.get("lang", "zh")
    ctx = {"user_points": 0, "config": Config, "lang": lang}
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user:
            ctx["user_points"] = user.points
        else:
            # 用户已被删除（如数据库重置），清理 session
            session.clear()
            if lang:
                session["lang"] = lang
    return ctx


# ============================================================
# 公开页面路由
# ============================================================
@app.route("/")
def index():
    """首页 / 落地页"""
    return render_template("index.html")


@app.route("/pricing")
def pricing():
    """积分套餐页"""
    return render_template("pricing.html")


@app.route("/set-language/<lang>")
def set_language(lang):
    """切换界面语言"""
    if lang in ("zh", "en"):
        session["lang"] = lang
    referrer = request.referrer or url_for("index")
    return redirect(referrer)


# ============================================================
# 认证路由
# ============================================================
@app.route("/register", methods=["GET", "POST"])
def register():
    """用户注册"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        password2 = request.form.get("password2", "").strip()

        # 验证
        errors = []
        if not username or len(username) < 2:
            errors.append(t("username_too_short"))
        if not email or "@" not in email:
            errors.append(t("email_invalid"))
        if not password or len(password) < 6:
            errors.append(t("password_too_short"))
        if password != password2:
            errors.append(t("password_mismatch"))

        # 检查用户名/邮箱是否已注册
        if User.query.filter_by(username=username).first():
            errors.append(t("username_taken"))
        if User.query.filter_by(email=email).first():
            errors.append(t("email_taken"))

        if errors:
            return render_template("register.html", errors=errors, username=username, email=email)

        # 创建用户
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # 自动登录
        session["user_id"] = user.id
        session["username"] = user.username
        flash(t("register_success"), "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """用户登录"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash(t("login_failed"), "error")
            return render_template("login.html", username=username)

        session["user_id"] = user.id
        session["username"] = user.username
        flash(t("login_success"), "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """注销"""
    lang = session.get("lang")  # 保留语言偏好
    session.clear()
    if lang:
        session["lang"] = lang
    flash(t("logout_done"), "info")
    return redirect(url_for("index"))


# ============================================================
# 需要登录的页面
# ============================================================
@app.route("/dashboard")
@login_required
def dashboard():
    """会员中心"""
    user = User.query.get(session["user_id"])
    # 最近的转换记录
    recent = (
        Conversion.query
        .filter_by(user_id=user.id)
        .order_by(Conversion.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("dashboard.html", user=user, recent=recent)


# ============================================================
# API 路由
# ============================================================
def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/api/me")
@login_required
def api_me():
    """返回当前用户信息"""
    user = User.query.get(session["user_id"])
    if not user:
        return jsonify({"error": t("user_not_found")}), 404
    return jsonify(user.to_dict())


@app.route("/api/convert", methods=["POST"])
@login_required
def convert():
    """接收图片，检查点数，调用 AI 转换，扣除点数"""
    user = User.query.get(session["user_id"])
    if not user:
        return jsonify({"error": t("user_not_found")}), 404

    # 1. 检查点数
    if user.points < Config.POINTS_PER_CONVERSION:
        return jsonify({
            "error": t("points_insufficient", current=user.points, needed=Config.POINTS_PER_CONVERSION),
            "points": user.points,
            "need_points": Config.POINTS_PER_CONVERSION,
        }), 402

    # 2. 检查文件
    if "image" not in request.files:
        return jsonify({"error": t("no_file")}), 400

    file = request.files["image"]
    if file.filename == "" or file.filename is None:
        return jsonify({"error": t("no_file_selected")}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"{t('unsupported_format')}，支持: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # 3. 保存上传的图片
    ext = Path(file.filename).suffix.lower()
    safe_name = f"{uuid.uuid4().hex}{ext}"
    filepath = Path(Config.UPLOAD_FOLDER) / safe_name
    file.save(filepath)

    # 检查 API Token
    api_token = app.config.get("REPLICATE_API_TOKEN")
    if not api_token or api_token == "your_token_here":
        filepath.unlink()
        return jsonify({"error": t("no_api_token")}), 500

    try:
        # 4. 调用 Replicate API
        with open(filepath, "rb") as img_file:
            output = replicate.run(
                Config.REPLICATE_MODEL,
                input={
                    "image": img_file,
                    "prompt": OTOMO_PROMPT,
                    "go_fast": True,
                    "output_format": "png",
                    "output_quality": 95,
                },
            )

        # 5. 处理返回结果
        if output is None:
            return jsonify({"error": t("ai_failed")}), 500

        if isinstance(output, list):
            item = output[0]
        else:
            item = output

        if isinstance(item, replicate.helpers.FileOutput):
            result_url = item.url
        elif isinstance(item, str):
            result_url = item
        else:
            result_url = str(item)

        # 6. 扣除点数 + 记录转换历史（在同一个事务中）
        success = user.spend_points(Config.POINTS_PER_CONVERSION)
        if not success:
            return jsonify({"error": t("points_deduct_fail")}), 500

        conversion = Conversion(
            user_id=user.id,
            original_filename=file.filename,
            result_url=result_url,
            points_cost=Config.POINTS_PER_CONVERSION,
        )
        db.session.add(conversion)
        db.session.commit()

        # 清理临时文件
        if filepath.exists():
            filepath.unlink()

        return jsonify({
            "success": True,
            "image_url": result_url,
            "points_remaining": user.points,
            "message": t("convert_success", cost=Config.POINTS_PER_CONVERSION, remaining=user.points),
        })

    except replicate.exceptions.ReplicateError as e:
        db.session.rollback()
        if filepath.exists():
            filepath.unlink()
        return jsonify({"error": f"{t('ai_error')}: {str(e)}"}), 500
    except Exception as e:
        db.session.rollback()
        if filepath.exists():
            filepath.unlink()
        return jsonify({"error": f"{t('process_error')}: {str(e)}"}), 500


@app.route("/api/recharge", methods=["POST"])
@login_required
def recharge():
    """
    充值点数（当前为手动充值模式）
    后续接入真实支付后，此接口由支付回调调用
    """
    user = User.query.get(session["user_id"])
    if not user:
        return jsonify({"error": t("user_not_found")}), 404

    package = request.form.get("package", "10")

    # 积分套餐映射
    packages = {
        "25": 25,
        "55": 55,
        "120": 120,
    }

    points = packages.get(package)
    if not points:
        return jsonify({"error": t("invalid_package")}), 400

    # 当前为手动模式：直接加点数（后续改为支付验证）
    user.add_points(points)
    db.session.commit()

    flash(t("recharge_success", points=points), "success")
    return redirect(url_for("dashboard"))


# ============================================================
# Creem 支付
# ============================================================

def _creem_api_url():
    return "https://test-api.creem.io" if Config.CREEM_TEST_MODE else "https://api.creem.io"


@app.route("/api/checkout", methods=["POST"])
@login_required
def checkout():
    """创建 Creem Checkout，返回支付页面 URL"""
    package = request.form.get("package", "25")
    product_id = Config.CREEM_PRODUCTS.get(package)

    if not product_id:
        return jsonify({"error": t("invalid_package")}), 400

    user = User.query.get(session["user_id"])
    if not user:
        return jsonify({"error": t("user_not_found")}), 404

    api_key = app.config.get("CREEM_API_KEY")
    if not api_key:
        return jsonify({"error": "支付服务暂未配置"}), 500

    try:
        resp = requests.post(
            f"{_creem_api_url()}/v1/checkouts",
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "product_id": product_id,
                "success_url": url_for("dashboard", _external=True),
                "metadata": {
                    "user_id": str(user.id),
                    "package": package,
                },
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"error": f"创建支付链接失败: {str(e)}"}), 500

    data = resp.json()
    checkout_url = data.get("checkout_url", "")

    if not checkout_url:
        return jsonify({"error": "支付链接为空"}), 500

    return jsonify({"url": checkout_url})


@app.route("/api/webhook/creem", methods=["POST"])
def creem_webhook():
    """接收 Creem Webhook，验证签名后给用户加积分"""
    secret = app.config.get("CREEM_WEBHOOK_SECRET", "")

    # 验证签名
    if secret:
        raw_body = request.get_data()
        signature = request.headers.get("creem-signature", "")
        computed = hmac.new(
            secret.encode(), raw_body, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed, signature):
            return jsonify({"error": "签名验证失败"}), 403

    payload = request.get_json(force=True)
    event_type = payload.get("type", "")

    # 只处理支付完成事件
    if event_type != "checkout.completed":
        return jsonify({"status": "ignored"}), 200

    # 提取自定义数据
    metadata = payload.get("metadata", {})
    user_id = metadata.get("user_id")
    package = metadata.get("package", "25")

    points_map = {"25": 25, "55": 55, "120": 120}
    points = points_map.get(package, 25)

    # 给用户加积分
    user = db.session.get(User, int(user_id)) if user_id else None
    if user:
        user.add_points(points)
        db.session.commit()

    return jsonify({"status": "ok"}), 200


# ============================================================
# 错误处理
# ============================================================
@app.errorhandler(413)
def too_large(e):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": t("file_too_large")}), 413
    flash(t("file_too_large"), "error")
    return redirect(url_for("dashboard"))


@app.errorhandler(404)
def not_found(e):
    return render_template("index.html"), 404


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    # 首次运行时创建数据库表
    with app.app_context():
        db.create_all()

    token = app.config.get("REPLICATE_API_TOKEN")
    if not token or token == "your_token_here":
        print("⚠️  警告：未配置 REPLICATE_API_TOKEN")
        print("   请在 .env 文件中设置你的 Replicate API Token")
        print()

    app.run(debug=True, host="127.0.0.1", port=5000)
