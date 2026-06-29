/**
 * 编辑器 + 标签管理逻辑 - KBCP v2
 */

// isAdmin 在页面加载后通过 checkAuth 设置，此处先用 false
let currentPoemDetail = null;
let currentTags = [];

/* ==================== 选中诗词 ==================== */

function selectPoem(poemId) {
    console.log('[selectPoem] called with poemId:', poemId);
    currentPoemId = poemId;

    // 高亮列表项
    document.querySelectorAll('.poem-list-item').forEach(function(el) {
        el.classList.toggle('active', el.dataset.poemId === poemId);
    });

    // 显示详情区
    document.getElementById('poemEmptyHint').style.display = 'none';
    document.getElementById('poemDetail').style.display = '';

    // 加载中
    document.getElementById('poemTitle').textContent = '加载中...';
    document.getElementById('poemAuthor').textContent = '';
    document.getElementById('poemContent').value = '';
    document.getElementById('poemAppreciation').value = '';
    document.getElementById('poemTranslation').value = '';
    document.getElementById('poemMeta').textContent = '';

    // 请求详情
    $.get('/api/poem/detail', {poem_id: poemId}, function(data) {
        console.log('[selectPoem] API success:', data);
        var poem = data.poem;
        var author = data.author;

        currentPoemDetail = poem;
        currentTags = data.tags || [];

        document.getElementById('poemTitle').textContent = poem.title || '-';
        document.getElementById('poemAuthor').textContent = (author && author.name) || '';
        document.getElementById('poemContent').value = poem.content || '';
        document.getElementById('poemAppreciation').value = poem.appreciation || '';
        document.getElementById('poemTranslation').value = poem.translation || '';
        document.getElementById('poemMeta').textContent =
            (data.dynasty_name || '') + ' · ' + (poem.line_count || '?') + '行';

        renderTags(currentTags);
    }).fail(function(jqXHR, textStatus, errorThrown) {
        console.error('[selectPoem] API failed:', textStatus, errorThrown, jqXHR.responseText);
        document.getElementById('poemTitle').textContent = '加载失败: ' + (jqXHR.responseJSON ? jqXHR.responseJSON.error : textStatus);
    });
}

/* ==================== 保存修改 ==================== */

function savePoem() {
    if (!currentPoemId) return;

    $.ajax({
        url: '/api/poem/save',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            poem_id: currentPoemId,
            content: document.getElementById('poemContent').value,
            appreciation: document.getElementById('poemAppreciation').value,
            translation: document.getElementById('poemTranslation').value,
        }),
        success: function(res) {
            if (res.status === 'success') {
                alert('保存成功');
            }
        },
        error: function() {
            alert('保存失败');
        }
    });
}

// 标签类别英文 → 中文 映射
var CATEGORY_NAMES = {
    theme: '主题',
    style: '风格',
    emotion: '情感',
    imagery: '意象',
    genre: '体裁',
    form: '形式',
    meter: '格律',
    language_style: '语言风格',
    season: '季节',
    festival: '节令',
    review_status: '审核状态',
    allusion: '典故',
};

/* ==================== 标签渲染 ==================== */

function renderTags(tags) {
    var container = document.getElementById('tagList');
    var tagContainer = document.getElementById('tagContainer');
    var emptyHint = document.getElementById('tagEmptyHint');

    if (!tags || tags.length === 0) {
        emptyHint.style.display = 'block';
        tagContainer.style.display = 'none';
        return;
    }

    emptyHint.style.display = 'none';
    tagContainer.style.display = 'block';

    // 按 category 分组
    var grouped = {};
    tags.forEach(function(t) {
        var cat = t.category || t.tag_type;
        if (!grouped[cat]) grouped[cat] = [];
        grouped[cat].push(t);
    });

    var navAdmin = document.getElementById('navAdmin');
    var showRemove = navAdmin && !navAdmin.classList.contains('hidden');

    var html = '';
    for (var cat in grouped) {
        if (!grouped.hasOwnProperty(cat)) continue;
        var catName = CATEGORY_NAMES[cat] || cat;
        html += '<div class="tag-category-label"># ' + catName + '</div><div>';
        grouped[cat].forEach(function(t) {
            var removeBtn = showRemove
                ? '<span class="tag-remove" onclick="removeTag(\'' + t.vocab_id + '\')" title="删除">×</span>'
                : '';
            html += '<span class="tag-badge">' + t.label + removeBtn + '</span>';
        });
        html += '</div>';
    }
    container.innerHTML = html;
}

/* ==================== 标签操作 ==================== */

function removeTag(vocabId) {
    if (!currentPoemId || !vocabId) return;

    $.ajax({
        url: '/api/poem/tag/remove',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({poem_id: currentPoemId, vocab_id: vocabId}),
        success: function(res) {
            if (res.status === 'success') {
                currentTags = currentTags.filter(function(t) { return t.vocab_id !== vocabId; });
                renderTags(currentTags);
            }
        }
    });
}

function clearAllTags() {
    if (!currentPoemId) return;
    if (!confirm('确定清除本诗的所有标签吗？')) return;

    $.ajax({
        url: '/api/poem/tag/clear',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({poem_id: currentPoemId}),
        success: function(res) {
            if (res.status === 'success') {
                currentTags = [];
                renderTags(currentTags);
            }
        }
    });
}

/* ==================== 增加标签 Modal ==================== */

var selectedTagVocabIds = [];

function showAddTagModal() {
    if (!currentPoemId) return;

    var existingIds = new Set(currentTags.map(function(t) { return t.vocab_id; }));
    selectedTagVocabIds = [];

    $.get('/api/vocab/categories', function(categories) {
        var html = '';

        categories.forEach(function(cat, idx) {
            html += '<div class="tag-selector-category" id="tagCat_' + idx + '">'
                + '<h6>' + (CATEGORY_NAMES[cat] || cat) + '</h6>'
                + '<div class="d-flex flex-wrap" id="tagCatItems_' + idx + '">'
                + '<span class="text-muted small"><i class="fas fa-spinner fa-spin"></i> 加载中...</span>'
                + '</div></div>';
        });

        document.getElementById('tagSelectorContent').innerHTML = html;

        categories.forEach(function(cat, idx) {
            $.get('/api/vocab/' + cat, function(items) {
                var catHtml = '';
                items.forEach(function(item) {
                    var disabled = existingIds.has(item.vocab_id);
                    catHtml += '<div>'
                        + '<input type="checkbox" id="tag_' + item.vocab_id + '" value="' + item.vocab_id + '"'
                        + (disabled ? ' disabled' : '')
                        + ' onchange="onTagCheckboxChange(this)">'
                        + '<label for="tag_' + item.vocab_id + '"'
                        + (disabled ? ' style="color:#ccc;cursor:not-allowed;"' : '') + '>'
                        + item.label + (disabled ? ' (已存在)' : '')
                        + '</label></div>';
                });
                document.getElementById('tagCatItems_' + idx).innerHTML = catHtml || '<span class="text-muted small">无词条</span>';
            });
        });

        var modal = new bootstrap.Modal(document.getElementById('addTagModal'));
        modal.show();
    });
}

function onTagCheckboxChange(el) {
    if (el.checked) {
        selectedTagVocabIds.push(el.value);
    } else {
        selectedTagVocabIds = selectedTagVocabIds.filter(function(v) { return v !== el.value; });
    }
}

function confirmAddTags() {
    if (selectedTagVocabIds.length === 0) {
        alert('请至少选择一个标签');
        return;
    }

    $.ajax({
        url: '/api/poem/tag/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            poem_id: currentPoemId,
            vocab_ids: selectedTagVocabIds,
        }),
        success: function(res) {
            if (res.status === 'success') {
                bootstrap.Modal.getInstance(document.getElementById('addTagModal')).hide();
                $.get('/api/poem/tags', {poem_id: currentPoemId}, function(tags) {
                    currentTags = tags;
                    renderTags(currentTags);
                });
            }
        }
    });
}

/* ==================== 添加诗词 (首页) ==================== */

function showAddPoemModal() {
    if (!currentAuthorId) {
        alert('请先在左侧选择一位作者');
        return;
    }
    document.getElementById('newPoemTitle').value = '';
    document.getElementById('newPoemContent').value = '';
    document.getElementById('newPoemAppreciation').value = '';
    var modal = new bootstrap.Modal(document.getElementById('addPoemModal'));
    modal.show();
}

function addPoem() {
    var title = document.getElementById('newPoemTitle').value.trim();
    if (!title) { alert('请输入标题'); return; }

    $.ajax({
        url: '/api/poem/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            author_id: currentAuthorId,
            title: title,
            content: document.getElementById('newPoemContent').value,
            appreciation: document.getElementById('newPoemAppreciation').value,
        }),
        success: function(res) {
            if (res.status === 'success') {
                alert('添加成功');
                bootstrap.Modal.getInstance(document.getElementById('addPoemModal')).hide();
                loadPoemList(currentAuthorId);
            }
        },
        error: function(xhr) {
            var msg = '添加失败';
            try { msg = xhr.responseJSON.error || msg; } catch(e) {}
            alert(msg);
        }
    });
}
