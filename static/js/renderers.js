import { formatDuration, getCoverFallbackDataUrl, normalizeCoverUrl } from './utils.js';

export function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function jsArg(value) {
    return escapeHtml(JSON.stringify(String(value ?? '')));
}

function rankLabel(rank) {
    return rank === 'domestic' ? '国产' : rank === 'sv' ? 'SV' : 'UTAU';
}

export function createVideoCard(video, { hasChange = false, isSelected = false } = {}) {
    const changeClass = `${hasChange ? 'edited' : ''} ${isSelected ? 'selected' : ''}`.trim();
    const coverUrl = normalizeCoverUrl(video.cover);
    const fallbackCover = getCoverFallbackDataUrl();
    const bvid = String(video.bvid ?? '');
    const bvidArg = jsArg(bvid);

    const rankTags = (video.ranks || []).map(r =>
        `<span class="tag tag-rank-${escapeHtml(r)}">${rankLabel(r)}</span>`
    ).join('');

    const exclusionTag = video.is_examined && (video.ranks || []).length === 0
        ? '<span class="tag tag-exclusion">排除</span>'
        : '';

    const statusTag = video.is_examined
        ? '<span class="tag tag-examined">已收录</span>'
        : '<span class="tag tag-uncheck">待收录</span>';

    const republishTag = video.is_republish
        ? '<span class="tag tag-republish">转载</span>'
        : '';

    return `
        <div class="video-item ${changeClass}" data-bvid="${escapeHtml(bvid)}">
            <div class="video-select">
                <input class="video-checkbox" type="checkbox" ${isSelected ? 'checked' : ''} onchange="app.toggleVideoSelection(${bvidArg}, this.checked)">
                <div class="video-content">
                    <img class="video-cover" src="${escapeHtml(coverUrl || fallbackCover)}" alt="封面" crossorigin="anonymous" referrerpolicy="no-referrer" loading="lazy" decoding="async"
                        onerror="this.onerror=null;this.src='${escapeHtml(fallbackCover)}'"
                        onclick="window.open('https://www.bilibili.com/video/${escapeHtml(bvid)}', '_blank')">
                    <div class="video-info">
                        <div class="video-title">${escapeHtml(video.title)}</div>
                        <div class="video-meta">
                            <span class="video-meta-item">
                                <span class="video-uploader">${escapeHtml(video.uploader)}</span>
                            </span>
                            <span class="video-meta-item">⏱ ${formatDuration(video.duration || 0)}</span>
                            <span class="video-meta-item">📅 ${escapeHtml(video.pubdate)}</span>
                            <span class="video-meta-item">${escapeHtml(video.avid)}</span>
                        </div>
                        <div class="video-tags">
                            ${rankTags}
                            ${statusTag}
                            ${republishTag}
                            ${exclusionTag}
                        </div>
                        <div class="video-actions">
                            <button class="btn btn-primary btn-sm" onclick="app.openEditPanel(${bvidArg})">✏️ 编辑</button>
                            <button class="btn btn-secondary btn-sm" onclick="window.open('https://www.bilibili.com/video/${escapeHtml(bvid)}', '_blank')">🔗 跳转</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

export function createEditPanel(change, bvid) {
    const ranks = change.ranks || [];
    const bvidArg = jsArg(bvid);

    return `
        <div class="edit-panel-header">
            <div class="edit-panel-title">编辑: ${escapeHtml(bvid)}</div>
            <button class="edit-panel-close" onclick="app.closeEditPanel()">&times;</button>
        </div>
        <div class="edit-panel-body">
            <div class="form-group">
                <label class="form-label">标题</label>
                <input class="input" value="${escapeHtml(change.title)}" readonly style="width: 100%;">
            </div>
            <div class="form-group">
                <label class="form-label">UP主</label>
                <input class="input" value="${escapeHtml(change.uploader)}" readonly style="width: 100%;">
            </div>
            <div class="form-group">
                <label class="form-label">简介</label>
                <textarea class="input" readonly style="width: 100%; height: 80px; resize: vertical;">${escapeHtml(change.desc)}</textarea>
            </div>
            <div class="form-group">
                <label class="form-label">收录期刊</label>
                <div class="checkbox-group">
                    <label class="checkbox-label" id="rank-domestic">
                        <input type="checkbox" ${ranks.includes('domestic') ? 'checked' : ''} onchange="app.toggleRank('domestic')">
                        国产类
                    </label>
                    <label class="checkbox-label" id="rank-sv">
                        <input type="checkbox" ${ranks.includes('sv') ? 'checked' : ''} onchange="app.toggleRank('sv')">
                        SV类
                    </label>
                    <label class="checkbox-label" id="rank-utau">
                        <input type="checkbox" ${ranks.includes('utau') ? 'checked' : ''} onchange="app.toggleRank('utau')">
                        UTAU类
                    </label>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">搬运标记</label>
                <div class="form-row">
                    <label class="checkbox-label" id="republish-label">
                        <input type="checkbox" ${change.is_republish ? 'checked' : ''} id="isRepublish" onchange="app.updateRepublish()">
                        转载
                    </label>
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Staff信息</label>
                <input class="input" id="staffInfo" value="${escapeHtml(change.staff_info)}" style="width: 100%;">
            </div>
            <div class="form-group">
                <label class="form-label">收录状态</label>
                <div class="form-row">
                    <label class="checkbox-label">
                        <input type="checkbox" ${change.is_examined ? 'checked' : ''} id="isExamined" onchange="app.updateExamined()">
                        已完成收录
                    </label>
                </div>
            </div>
        </div>
        <div class="edit-panel-footer">
            <button class="btn btn-secondary" onclick="app.closeEditPanel()">取消</button>
            <button class="btn btn-primary" onclick="app.saveChange(${bvidArg})">保存到本地</button>
        </div>
    `;
}

export function createChangeItems(changes) {
    return changes.map(([bvid, data]) => {
        const changesDesc = [];
        if (data.ranks && data.ranks.length) changesDesc.push(`期刊: ${data.ranks.join(', ')}`);
        if ('is_examined' in data) changesDesc.push(data.is_examined ? '已收录' : '未收录');
        if ('is_republish' in data) changesDesc.push(data.is_republish ? '转载' : '自制');
        if (data.staff_info) changesDesc.push(`Staff: ${data.staff_info}`);

        return `
            <div class="change-item">
                <div class="change-item-info">
                    <div class="change-item-title">${escapeHtml(data.title || bvid)}</div>
                    <div class="change-item-desc">${escapeHtml(changesDesc.join(' | '))}</div>
                </div>
                <button class="change-item-remove" onclick="app.removeChange(${jsArg(bvid)})">&times;</button>
            </div>
        `;
    }).join('');
}

export function createPreviewContent({ data, previewRank, previewIndex }) {
    if (!data || !data.entries || data.entries.length === 0) {
        return `
            <div class="ranking-card">
                <div class="ranking-header">
                    <div class="ranking-rank">⚠️</div>
                </div>
                <div>${escapeHtml(String(previewRank).toUpperCase())} 第${escapeHtml(previewIndex)}期排行榜暂无视频数据</div>
            </div>
        `;
    }

    const stat = data.stat;
    const entries = data.entries;

    return `
        <div class="ranking-card">
            <div class="ranking-header">
                <div class="ranking-rank">📊</div>
            </div>
            <div>${escapeHtml(String(previewRank).toUpperCase())} 第${escapeHtml(previewIndex)}期排行榜</div>
            <div style="margin-top: 0.5rem; color: var(--gray-500); font-size: 0.875rem;">
                视频总数: ${Number(stat.count || 0).toLocaleString()} | 总播放: ${Number(stat.totalView || 0).toLocaleString()} | 总点赞: ${Number(stat.totalLike || 0).toLocaleString()} | 新投稿: ${Number(stat.totalNew || 0).toLocaleString()}
            </div>
        </div>
        ${entries.map(createPreviewCard).join('')}
    `;
}

export function createPreviewCard(entry) {
    const coverUrl = normalizeCoverUrl(entry.cover);
    const fallbackCover = getCoverFallbackDataUrl();
    const bvid = String(entry.bvid ?? '');
    const bvidArg = jsArg(bvid);

    return `
        <div class="ranking-card">
            <div class="ranking-header">
                <div class="ranking-rank">#${escapeHtml(entry.rank)}</div>
                <div class="ranking-score">分数: ${Number(entry.totalScore || 0).toFixed(1)}</div>
            </div>
            <div style="display: flex; gap: 1rem; margin-bottom: 0.5rem;">
                <img src="${escapeHtml(coverUrl || fallbackCover)}" style="width: 120px; height: 68px; object-fit: cover; border-radius: 4px; background: var(--gray-200); cursor: pointer;"
                    crossorigin="anonymous" referrerpolicy="no-referrer" loading="lazy" decoding="async"
                    onerror="this.onerror=null;this.src='${escapeHtml(fallbackCover)}'"
                    onclick="window.open('https://www.bilibili.com/video/${escapeHtml(bvid)}', '_blank')"
                    title="点击打开B站视频">
                <div style="flex: 1; min-width: 0;">
                    <div style="font-weight: 600; margin-bottom: 0.25rem; cursor: pointer; color: var(--primary);"
                        onclick="window.open('https://www.bilibili.com/video/${escapeHtml(bvid)}', '_blank')">
                        ${escapeHtml(entry.title || bvid)}
                    </div>
                    <div style="font-size: 0.8125rem; color: var(--gray-500); margin-bottom: 0.5rem;">
                        UP主: ${escapeHtml(entry.uploader || '未知')}
                    </div>
                    <div style="display: flex; gap: 1rem; font-size: 0.8125rem; color: var(--gray-600); flex-wrap: wrap;">
                        <span>👁 ${Number(entry.view || 0).toLocaleString()}</span>
                        <span>❤️ ${Number(entry.like || 0).toLocaleString()}</span>
                        <span>🪙 ${Number(entry.coin || 0).toLocaleString()}</span>
                        <span>⭐ ${Number(entry.favorite || 0).toLocaleString()}</span>
                        <span>📤 ${Number(entry.share || 0).toLocaleString()}</span>
                    </div>
                    ${entry.isNew ? '<span class="tag tag-rank-utau" style="margin-top: 0.5rem; display: inline-block;">新上榜</span>' : ''}
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid var(--gray-200);">
                <button class="btn btn-primary btn-sm" onclick="app.openEditPanelByBvid(${bvidArg})">✏️ 编辑</button>
                <button class="btn btn-secondary btn-sm" onclick="window.open('https://www.bilibili.com/video/${escapeHtml(bvid)}', '_blank')">🔗 跳转</button>
            </div>
        </div>
    `;
}
