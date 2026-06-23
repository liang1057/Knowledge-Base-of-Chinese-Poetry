/**
 * 树形控件交互逻辑
 * 两级树控件（朝代-作者）+ 诗词列表
 */

// 当前选中的作者信息
let currentAuthorId = null;
let currentAuthorName = null;
let currentDynastyId = null;
let currentDynastyName = null;
let currentPoemId = null;    // 实际存储的是诗词 title
let currentPoemAuthor = null; // 当前诗词的作者名，用于精确保存

// 初始化
$(document).ready(function() {
    initTree();
});

// 初始化 jstree（两级：朝代-作者）
function initTree() {
    $('#dynastyTree').jstree({
        'core': {
            'data': function(node, callback) {
                if (node.id === '#') {
                    // 根节点 - 加载所有朝代
                    loadDynasties(callback);
                } else if (node.original.type === 'dynasty') {
                    // 朝代节点 - 加载作者列表
                    loadAuthors(node.id, callback);
                }
            },
            'themes': {
                'name': 'default',
                'dots': true,
                'icons': true
            },
            'multiple': false,
            'animation': 200
        },
        'plugins': ['themes', 'html_data', 'ui']
    });
    
    // 点击作者节点 - 加载诗词列表
    $('#dynastyTree').on('select_node.jstree', function(e, data) {
        const node = data.node;
        if (node.original.type === 'author') {
            // 选中作者
            const authorId = node.original.id;
            const authorName = node.original.name;
            const dynastyId = node.original.dynasty_id;
            const dynastyName = node.original.dynasty_name;
            
            setCurrentAuthor(authorId, authorName, dynastyId, dynastyName);
            loadPoemList(authorId);
        }
    });
    
    // 双击展开/折叠
    $('#dynastyTree').on('dblclick.jstree', function(e) {
        // 阻止默认行为
        e.preventDefault();
    });
}

// 加载朝代列表
function loadDynasties(callback) {
    $.get('/api/dynasties', function(dynasties) {
        const nodes = dynasties.map(function(d) {
            return {
                id: d.id,
                text: d.name,
                type: 'dynasty',
                icon: 'fas fa-landmark',
                state: {
                    'opened': false,
                    'disabled': false
                },
                children: true  // 标记有子节点
            };
        });
        callback(nodes);
    });
}

// 加载作者列表
function loadAuthors(dynastyId, callback) {
    $.get('/api/authors/' + dynastyId, function(authors) {
        const nodes = authors.map(function(a) {
            return {
                id: a.id,
                text: a.name,
                type: 'author',
                icon: 'fas fa-user',
                author_name: a.name,
                dynasty_id: a.dynasty_id,
                dynasty_name: a.dynasty_name || '',
                state: {
                    'opened': false,
                    'disabled': false
                },
                children: false  // 不再有子节点，诗词在右侧列表显示
            };
        });
        callback(nodes);
    });
}

// 设置当前作者
function setCurrentAuthor(authorId, authorName, dynastyId, dynastyName) {
    currentAuthorId = authorId;
    currentAuthorName = authorName;
    currentDynastyId = dynastyId;
    currentDynastyName = dynastyName;
    
    // 更新提示
    $('#currentAuthorHint').text(dynastyName + ' - ' + authorName);
    
    // 启用添加诗词按钮
    $('#btnAddPoem').prop('disabled', false);
}

// 加载诗词列表
function loadPoemList(authorId) {
    const container = $('#poemListContainer');
    container.html('<div class="loading">加载中</div>');
    
    $.get('/api/poems/' + authorId, function(poems) {
        if (poems.length === 0) {
            container.html(`
                <div class="empty-hint">
                    <i class="fas fa-scroll"></i>
                    <p>该诗人暂无诗词</p>
                </div>
            `);
            clearPoemDetail();
            return;
        }
        
        let html = '<div class="list-group">';
        poems.forEach(function(p, index) {
            // 使用 data 属性存储 title 和 author，避免 onclick 内引号转义问题
            html += `
                <div class="poem-list-item ${index === 0 ? 'active' : ''}" 
                     data-title="${escapeAttr(p.title)}"
                     data-author="${escapeAttr(p.author || currentAuthorName || '')}"
                     onclick="selectPoem(this.dataset.title, this, this.dataset.author)">
                    <div class="poem-item-title">${escapeHtml(p.title)}</div>
                </div>
            `;
        });
        html += '</div>';
        container.html(html);
        
        // 默认选中第一首
        if (poems.length > 0) {
            const first = container.find('.poem-list-item').first();
            selectPoem(first.data('title'), first[0], first.data('author'));
        }
    }).fail(function() {
        container.html(`
            <div class="empty-hint">
                <i class="fas fa-exclamation-triangle"></i>
                <p>加载诗词列表失败</p>
            </div>
        `);
    });
}

// HTML 属性转义（防止 data-* 注入）
function escapeAttr(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// HTML 内容转义
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// 选择诗词
function selectPoem(poemTitle, element, authorName) {
    // 更新选中状态
    $('.poem-list-item').removeClass('active');
    $(element).addClass('active');
    
    // 加载诗词详情（传入作者名用于精确查询）
    loadPoemDetail(poemTitle, authorName || currentAuthorName);
}

// 加载诗词详情
function loadPoemDetail(poemTitle, authorName) {
    currentPoemId = poemTitle;
    currentPoemAuthor = authorName || currentAuthorName || '';
    
    // 使用 query string 避免标题中含特殊字符导致路由问题
    const params = $.param({ title: poemTitle, author: currentPoemAuthor });
    $.get('/api/poem/detail?' + params, function(data) {
        const poem = data.poem;
        const author = data.author;
        
        // 更新诗词信息
        $('#poemTitle').text(poem.title);
        $('#poemAuthor').text(author ? author.name : (poem.author || '-'));
        $('#poemDynasty').text(poem.dynasty || '-');
        
        // 更新正文（保留换行）
        $('#poemContent').val(poem.content || '');
        
        // 更新赏析
        $('#poemAppreciation').val(poem.appreciation || '');
        
        // 更新翻译
        $('#poemTranslation').val(poem.translation || '');
        
        // 更新属性表
        $('#attrGenre').val(poem.genre || '');
        $('#attrForm').val(poem.form || '');
        $('#attrMeter').val(poem.meter || '');
        $('#attrTheme').val(poem.theme || '');
        $('#attrStyle').val(poem.style || '');
        $('#attrEmotion').val(poem.emotion || '');
        $('#attrImagery').val(poem.imagery || '');
        $('#attrAllusions').val(poem.allusions || '');
        $('#attrKeywords').val(poem.keywords || '');
        $('#attrSeason').val(poem.season || '');
        $('#attrFestival').val(poem.festival || '');
        $('#attrPlaces').val(poem.places_involved || '');
        $('#attrPeople').val(poem.people_involved || '');
        $('#attrBackground').val(poem.background || '');
        $('#attrHistoricalContext').val(poem.historical_context || '');
        $('#attrLineCount').text(poem.line_count || '-');
        $('#attrCharCount').text(poem.char_count || '-');
        
        // 显示保存按钮
        $('#saveSection').show();
        
    }).fail(function(xhr) {
        const msg = xhr.responseJSON ? xhr.responseJSON.error : '未知错误';
        alert('加载诗词详情失败: ' + msg);
    });
}

// 清空诗词详情
function clearPoemDetail() {
    currentPoemId = null;
    $('#poemTitle').text('请选择一首诗词');
    $('#poemAuthor').text('-');
    $('#poemDynasty').text('-');
    $('#poemContent').val('');
    $('#poemAppreciation').val('');
    $('#poemTranslation').val('');
    
    // 清空属性表
    $('#attrGenre, #attrForm, #attrMeter, #attrTheme, #attrStyle').val('');
    $('#attrEmotion, #attrImagery, #attrAllusions, #attrKeywords').val('');
    $('#attrSeason, #attrFestival, #attrPlaces, #attrPeople').val('');
    $('#attrBackground, #attrHistoricalContext').val('');
    $('#attrLineCount').text('-');
    $('#attrCharCount').text('-');
    
    $('#saveSection').hide();
}

// 展开所有节点
function expandAll() {
    $('#dynastyTree').jstree('open_all');
}

// 折叠所有节点
function collapseAll() {
    $('#dynastyTree').jstree('close_all');
}

// 显示添加诗词弹窗
function showAddPoemModal() {
    if (!currentAuthorId) {
        alert('请先选择一位诗人');
        return;
    }
    
    $('#newPoemDynastyId').val(currentDynastyId);
    $('#newPoemAuthorId').val(currentAuthorId);
    $('#newPoemDynastyName').val(currentDynastyName);
    $('#newPoemAuthorName').val(currentAuthorName);
    $('#newPoemTitle').val('');
    $('#newPoemContent').val('');
    $('#newPoemAppreciation').val('');
    
    var modal = new bootstrap.Modal($('#addPoemModal'));
    modal.show();
}

// 添加诗词
function addPoem() {
    const authorId = $('#newPoemAuthorId').val();
    const title = $('#newPoemTitle').val().trim();
    
    if (!authorId || !title) {
        alert('请填写必填项');
        return;
    }
    
    $.ajax({
        url: '/api/poem/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            author_id: authorId,
            title: title,
            content: $('#newPoemContent').val(),
            appreciation: $('#newPoemAppreciation').val()
        }),
        success: function(data) {
            if (data.status === 'success') {
                alert('添加成功！');
                bootstrap.Modal.getInstance($('#addPoemModal')).hide();
                // 刷新诗词列表
                loadPoemList(authorId);
            }
        },
        error: function() {
            alert('添加失败');
        }
    });
}

// 获取当前诗词ID
function getCurrentPoemId() {
    return currentPoemId;
}
