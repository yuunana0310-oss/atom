/**
 * Prompt Generator Studio - メインJS
 */

// ============================================================
// 状態管理
// ============================================================
const State = {
    currentSlide: 0,
    totalSlides: 0,
    generatedData: null,
    charImagePath: null,
};

// ============================================================
// 初期化
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    initSlideInputs();
    initEventListeners();
    initCharUpload();
});

function initEventListeners() {
    // 生成ボタン
    document.getElementById('generateBtn').addEventListener('click', handleGenerate);

    // 枚数変更
    document.getElementById('countDown').addEventListener('click', () => changeCount(-1));
    document.getElementById('countUp').addEventListener('click', () => changeCount(1));
    document.getElementById('countInput').addEventListener('change', () => {
        initSlideInputs();
    });

    // フォーマット切替
    document.querySelectorAll('input[name="outputFormat"]').forEach(r => {
        r.addEventListener('change', (e) => {
            document.getElementById('formatIndividual').classList.toggle('active', e.target.value === 'individual');
            document.getElementById('formatGrid').classList.toggle('active', e.target.value === 'grid');
        });
    });

    // ジャンルカスタム
    document.getElementById('genreSelect').addEventListener('change', (e) => {
        document.getElementById('genreCustom').classList.toggle('hidden', e.target.value !== 'custom');
    });

    // スライドナビ
    document.getElementById('prevSlideBtn').addEventListener('click', () => navigateSlide(-1));
    document.getElementById('nextSlideBtn').addEventListener('click', () => navigateSlide(1));

    // コピーボタン
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('copy-btn')) {
            const targetId = e.target.dataset.target;
            const el = document.getElementById(targetId);
            if (el) copyText(el.textContent, e.target);
        }
    });

    // エクスポート
    document.getElementById('exportAllBtn').addEventListener('click', handleExport);
}

// ============================================================
// スライド入力の動的生成
// ============================================================
function initSlideInputs() {
    const count = parseInt(document.getElementById('countInput').value) || 5;
    const container = document.getElementById('slidesContainer');
    const existing = container.querySelectorAll('.slide-input-item');

    // 既存のテキストを保存
    const savedData = [];
    existing.forEach(item => {
        savedData.push({
            title: item.querySelector('.slide-title-input')?.value || '',
            text: item.querySelector('.slide-text-input')?.value || '',
        });
    });

    container.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const div = document.createElement('div');
        div.className = 'slide-input-item';
        div.innerHTML = `
            <div class="slide-input-header">
                <span class="slide-num">#${i + 1}</span>
                <button class="slide-collapse-btn" data-index="${i}">▼</button>
            </div>
            <div class="slide-input-body" id="slideBody_${i}">
                <input type="text" class="slide-title-input" placeholder="表題（タイトル）" 
                       value="${savedData[i]?.title || ''}">
                <textarea class="slide-text-input" placeholder="具体的なテキスト・内容の説明" 
                          rows="2">${savedData[i]?.text || ''}</textarea>
            </div>
        `;
        container.appendChild(div);
    }

    // 折りたたみ
    container.querySelectorAll('.slide-collapse-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const idx = e.target.dataset.index;
            const body = document.getElementById(`slideBody_${idx}`);
            body.classList.toggle('hidden');
            e.target.textContent = body.classList.contains('hidden') ? '▶' : '▼';
        });
    });
}

function changeCount(delta) {
    const input = document.getElementById('countInput');
    const val = Math.max(1, Math.min(10, (parseInt(input.value) || 1) + delta));
    input.value = val;
    initSlideInputs();
}

// ============================================================
// キャラクター画像アップロード
// ============================================================
function initCharUpload() {
    const area = document.getElementById('charUploadArea');
    const input = document.getElementById('charFileInput');
    const preview = document.getElementById('charPreview');
    const prompt = document.getElementById('charUploadPrompt');
    const img = document.getElementById('charPreviewImg');
    const removeBtn = document.getElementById('charRemoveBtn');

    area.addEventListener('click', () => input.click());
    area.addEventListener('dragover', (e) => { e.preventDefault(); area.classList.add('dragover'); });
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            uploadCharImage(e.dataTransfer.files[0]);
        }
    });

    input.addEventListener('change', () => {
        if (input.files.length) uploadCharImage(input.files[0]);
    });

    removeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        State.charImagePath = null;
        preview.classList.add('hidden');
        prompt.classList.remove('hidden');
        img.src = '';
    });
}

async function uploadCharImage(file) {
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            State.charImagePath = data.url;
            document.getElementById('charPreviewImg').src = data.url;
            document.getElementById('charPreview').classList.remove('hidden');
            document.getElementById('charUploadPrompt').classList.add('hidden');
        }
    } catch (e) {
        console.error('Upload failed:', e);
    }
}

// ============================================================
// プロンプト生成
// ============================================================
async function handleGenerate() {
    const btn = document.getElementById('generateBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="generate-icon spin">⏳</span> 生成中...';

    // フォームから設定収集
    const slides = [];
    document.querySelectorAll('.slide-input-item').forEach(item => {
        slides.push({
            title: item.querySelector('.slide-title-input')?.value || '',
            text: item.querySelector('.slide-text-input')?.value || '',
        });
    });

    const config = {
        purpose: document.getElementById('purposeSelect').value,
        aspect_ratio: document.getElementById('aspectSelect').value,
        count: parseInt(document.getElementById('countInput').value) || 1,
        genre: document.getElementById('genreSelect').value,
        genre_custom: document.getElementById('genreCustom').value,
        structure: document.getElementById('structureSelect').value,
        style: document.getElementById('styleSelect').value,
        output_format: document.querySelector('input[name="outputFormat"]:checked').value,
        slides: slides,
        character: {
            description: document.getElementById('charDescription').value,
            image_path: State.charImagePath || '',
        },
    };

    try {
        const res = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        const data = await res.json();

        if (data.error) {
            addChatMessage('assistant', `⚠️ エラー: ${data.error}`);
            return;
        }

        State.generatedData = data;
        State.totalSlides = data.prompts.length;
        State.currentSlide = 0;

        displayPrompts();
        
        // 成功を小さく通知（オプション）
        console.log(`✅ ${State.totalSlides}枚分のプロンプトを生成しました！`);

    } catch (e) {
        console.error(e);
        alert(`⚠️ 生成エラー: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="generate-icon">⚡</span> プロンプト生成';
    }
}

// ============================================================
// プロンプト表示
// ============================================================
function displayPrompts() {
    const data = State.generatedData;
    if (!data) return;

    document.getElementById('outputEmpty').classList.add('hidden');
    document.getElementById('promptCards').classList.remove('hidden');

    // グリッドセクション
    const gridSection = document.getElementById('gridSection');
    if (data.output_format === 'grid' && data.grid_prompt) {
        gridSection.classList.remove('hidden');
        document.getElementById('gridMjText').textContent = data.grid_prompt.midjourney || '';
        document.getElementById('gridSdPosText').textContent = data.grid_prompt.sd_positive || '';
        document.getElementById('gridSdNegText').textContent = data.grid_prompt.sd_negative || '';
        document.getElementById('gridNb2PosText').textContent = data.grid_prompt.nb2_positive || '';
        document.getElementById('gridNb2NegText').textContent = data.grid_prompt.nb2_negative || '';
        document.getElementById('gridDalleText').textContent = data.grid_prompt.dalle || '';
    } else {
        gridSection.classList.add('hidden');
    }

    // 個別スライド表示
    showSlide(State.currentSlide);
    updateSlideCounter();
}

function showSlide(index) {
    const data = State.generatedData;
    if (!data || !data.prompts[index]) return;

    const p = data.prompts[index];

    document.getElementById('slideTitle').textContent = `📄 ${p.title || `スライド ${index + 1}`}`;
    document.getElementById('slideMjText').textContent = p.midjourney || '';
    document.getElementById('slideSdPosText').textContent = p.sd_positive || '';
    document.getElementById('slideSdNegText').textContent = p.sd_negative || '';
    document.getElementById('slideNb2PosText').textContent = p.nb2_positive || '';
    document.getElementById('slideNb2NegText').textContent = p.nb2_negative || '';
    document.getElementById('slideDalleText').textContent = p.dalle || '';

    // SD設定
    const settings = p.sd_settings || {};
    let settingsText = `${settings.width}×${settings.height} | Steps: ${settings.steps} | CFG: ${settings.cfg_scale} | ${settings.sampler} | Model: ${settings.model}`;
    if (settings.controlnet_image) {
        settingsText += `\n[Image Source / CNet]: ${settings.controlnet_image}`;
    }
    document.getElementById('slideSdSettings').textContent = settingsText;
}

function navigateSlide(delta) {
    if (!State.generatedData) return;
    const newIdx = State.currentSlide + delta;
    if (newIdx >= 0 && newIdx < State.totalSlides) {
        State.currentSlide = newIdx;
        showSlide(newIdx);
        updateSlideCounter();
    }
}

function updateSlideCounter() {
    document.getElementById('slideCounter').textContent =
        State.totalSlides > 0 ? `${State.currentSlide + 1} / ${State.totalSlides}` : '-';
}

// ============================================================
// コピー機能
// ============================================================
function copyText(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const orig = btn.textContent;
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
            btn.textContent = orig;
            btn.classList.remove('copied');
        }, 1500);
    });
}

// ============================================================
// エクスポート
// ============================================================
async function handleExport() {
    if (!State.generatedData) return;

    try {
        const res = await fetch('/api/export/prompts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(State.generatedData),
        });
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'prompts_export.txt';
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('Export failed:', e);
    }
}

