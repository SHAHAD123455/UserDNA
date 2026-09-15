let lastKeyTime = Date.now();
let keyIntervals = [];
let mouseMovements = [];
let mouseJitter = 5;
let hasActivity = false;
let simulateAttack = false;

// ══ 1. تتبع الكتابة ══
document.addEventListener('keydown', () => {
    const now = Date.now();
    keyIntervals.push(now - lastKeyTime);
    lastKeyTime = now;
    if (keyIntervals.length > 10) keyIntervals.shift();
    hasActivity = true;

    const avgSpeed = keyIntervals.reduce((a, b) => a + b, 0) / keyIntervals.length;
    document.getElementById('m-speed').innerText = Math.round(avgSpeed);
});

// ══ 2. تتبع الماوس ══
document.addEventListener('mousemove', (e) => {
    mouseMovements.push({ x: e.clientX, y: e.clientY });
    if (mouseMovements.length > 20) mouseMovements.shift();
    hasActivity = true;

    if (mouseMovements.length > 1) {
        const last = mouseMovements[mouseMovements.length - 1];
        const prev = mouseMovements[mouseMovements.length - 2];
        mouseJitter = Math.sqrt(
            Math.pow(last.x - prev.x, 2) + Math.pow(last.y - prev.y, 2)
        );
        document.getElementById('m-jitter').innerText = Math.round(mouseJitter);
    }
});

// ══ 3. محاكاة مهاجم ══
function simulateAttacker() {
    simulateAttack = true;
    document.getElementById('m-click').innerText = "عشوائي ⚠️";
    document.getElementById('alert-box').innerText = "🎭 وضع المحاكاة: سلوك مشبوه مُحقن...";
}

// ══ 4. الإرسال الدوري ══
async function sendBehavioralData() {
    if (!hasActivity) return;

    let avgSpeed = keyIntervals.length > 0
        ? keyIntervals.reduce((a, b) => a + b, 0) / keyIntervals.length
        : 100;
    let jitter = mouseJitter;

    if (simulateAttack) {
        avgSpeed = 15 + Math.random() * 30;
        jitter = 80 + Math.random() * 120;
    }

    try {
        const response = await fetch('/analyze_behavior', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ typing_speed: avgSpeed, mouse_jitter: jitter })
        });
        if (response.ok) updateUI(await response.json());
    } catch (err) {
        console.error("Behavior analysis failed:", err);
    }
}

// ══ 5. تحديث الواجهة ══
function updateUI(data) {
    const statusText = document.getElementById('status-text');

    if (data.learning) {
        document.getElementById('learning-progress').innerText = data.progress;
        document.getElementById('progress-fill').style.width = data.progress + '%';
        statusText.innerText = "🧠 جاري تعلم نمطك السلوكي...";
        if (data.progress >= 100) {
            document.getElementById('learning-bar').style.display = 'none';
            statusText.innerText = "✅ اكتمل التعلم — النظام في وضع المراقبة";
        }
        return;
    }

    const score = data.risk_score;
    const gaugeFill = document.getElementById('gauge-fill');

    document.getElementById('risk-value').innerText = score + '%';
    gaugeFill.style.strokeDashoffset = 126 - (126 * score / 100);

    const personalApps = document.querySelectorAll('[data-app]');
    const appsStatus = document.getElementById('apps-status');
    if (data.locked_apps.length > 0) {
        personalApps.forEach(a => a.classList.add('locked'));
        appsStatus.innerText = "🔒 تم قفل التطبيقات الحساسة";
        appsStatus.style.color = 'var(--warning)';
    } else {
        personalApps.forEach(a => a.classList.remove('locked'));
        appsStatus.innerText = "جميع التطبيقات متاحة ✅";
        appsStatus.style.color = '#94a3b8';
    }

    if (score > 70) {
        gaugeFill.style.stroke = '#ef4444';
        statusText.innerText = "🚨 حالة حرجة: قفل الجهاز";
        document.getElementById('lockdown-screen').classList.remove('hidden');
        simulateAttack = false;
    } else if (score > 40) {
        gaugeFill.style.stroke = '#f59e0b';
        statusText.innerText = "⚠️ تحذير: سلوك غير معتاد";
    } else {
        gaugeFill.style.stroke = '#a855f7';
        statusText.innerText = "✅ الحالة: آمن";
    }

    document.getElementById('alert-box').innerText = data.alerts;
}

function resetLockdown() {
    document.getElementById('lockdown-screen').classList.add('hidden');
}

setInterval(sendBehavioralData, 3000);