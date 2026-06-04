/**
 * OtomoStyle — 前端交互（上传、转换、点数管理）
 */
document.addEventListener("DOMContentLoaded", () => {
    // 只在会员中心页面运行转换逻辑
    const uploadArea = document.getElementById("uploadArea");
    if (!uploadArea) return;

    const fileInput = document.getElementById("fileInput");
    const previewSection = document.getElementById("previewSection");
    const previewImage = document.getElementById("previewImage");
    const loadingSection = document.getElementById("loadingSection");
    const resultSection = document.getElementById("resultSection");
    const resultImage = document.getElementById("resultImage");
    const errorSection = document.getElementById("errorSection");
    const errorMessage = document.getElementById("errorMessage");
    const convertBtn = document.getElementById("convertBtn");
    const resetBtn = document.getElementById("resetBtn");
    const downloadBtn = document.getElementById("downloadBtn");
    const newConvertBtn = document.getElementById("newConvertBtn");
    const errorRetryBtn = document.getElementById("errorRetryBtn");
    const buyPointsBtn = document.getElementById("buyPointsBtn");
    const resultContainer = document.getElementById("resultContainer");
    const resultPointsInfo = document.getElementById("resultPointsInfo");
    const pointsBalance = document.getElementById("pointsBalance");
    const headerPoints = document.getElementById("headerPoints");

    let selectedFile = null;

    // ===== 上传区域 =====
    uploadArea.addEventListener("click", () => fileInput.click());
    uploadArea.addEventListener("dragover", (e) => { e.preventDefault(); uploadArea.classList.add("drag-over"); });
    uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("drag-over"));
    uploadArea.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadArea.classList.remove("drag-over");
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0]);
    });

    function handleFile(file) {
        const allowed = ["image/jpeg", "image/png", "image/webp", "image/gif"];
        if (!allowed.includes(file.type)) {
            showError(window.I18N.bad_format);
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showError(window.I18N.file_too_large);
            return;
        }
        selectedFile = file;
        const reader = new FileReader();
        reader.onload = (e) => { previewImage.src = e.target.result; };
        reader.readAsDataURL(file);
        uploadArea.style.display = "none";
        previewSection.style.display = "block";
        resultSection.style.display = "none";
        loadingSection.style.display = "none";
        errorSection.style.display = "none";
        resultContainer.innerHTML = '<span>' + window.I18N.waiting + '</span>';
    }

    // ===== 转换 =====
    convertBtn.addEventListener("click", startConvert);

    function startConvert() {
        if (!selectedFile) return;
        previewSection.style.display = "none";
        loadingSection.style.display = "block";
        errorSection.style.display = "none";
        resultSection.style.display = "none";
        convertBtn.disabled = true;

        const formData = new FormData();
        formData.append("image", selectedFile);

        fetch("/api/convert", { method: "POST", body: formData })
            .then(async (res) => {
                const data = await res.json();
                if (!res.ok || data.error) {
                    const err = new Error(data.error || window.I18N.convert_failed);
                    err.status = res.status;
                    err.data = data;
                    throw err;
                }
                return data;
            })
            .then((data) => {
                loadingSection.style.display = "none";
                resultImage.src = data.image_url;
                downloadBtn.href = data.image_url;
                resultPointsInfo.textContent = data.message;
                resultSection.style.display = "block";
                convertBtn.disabled = false;
                // 更新点数显示
                updatePoints(data.points_remaining);
            })
            .catch((err) => {
                loadingSection.style.display = "none";
                convertBtn.disabled = false;
                if (err.status === 402) {
                    // 点数不足
                    showError(err.message, true);
                } else if (err.status === 401) {
                    showError(window.I18N.login_required);
                } else {
                    showError(err.message, false);
                }
            });
    }

    function updatePoints(newPoints) {
        if (pointsBalance) pointsBalance.textContent = newPoints;
        if (headerPoints) headerPoints.textContent = newPoints;
        // 也更新导航栏
        const navPoints = document.querySelector(".nav-points");
        if (navPoints) navPoints.textContent = "💰 " + window.I18N.points_format.replace("{points}", newPoints);
    }

    // ===== 重置 =====
    resetBtn.addEventListener("click", resetAll);
    newConvertBtn.addEventListener("click", resetAll);

    function resetAll() {
        selectedFile = null;
        fileInput.value = "";
        previewImage.src = "";
        resultImage.src = "";
        uploadArea.style.display = "block";
        previewSection.style.display = "none";
        loadingSection.style.display = "none";
        resultSection.style.display = "none";
        errorSection.style.display = "none";
    }

    // ===== 错误处理 =====
    errorRetryBtn.addEventListener("click", () => { if (selectedFile) startConvert(); });

    function showError(msg, isPointsIssue) {
        loadingSection.style.display = "none";
        previewSection.style.display = "none";
        errorSection.style.display = "block";
        errorMessage.textContent = msg;
        buyPointsBtn.style.display = isPointsIssue ? "inline-block" : "none";
    }
});
