/**
 * 树控件逻辑 - KBCP v2
 * 基于 jsTree 实现朝代-诗人的懒加载树
 *
 * 懒加载机制：
 *   - 初始加载根节点（朝代），标记 children: true 表示有子节点
 *   - 当朝代节点展开时，jsTree 自动调用 data 函数加载作者节点
 */

let currentAuthorId = null;
let currentPoemId = null;
let isAdmin = false;

$(document).ready(function() {
    checkAuth().then(() => {
        isAdmin = !document.getElementById('navAdmin').classList.contains('hidden');
        if (isAdmin) {
            document.getElementById('btnAddPoem')?.classList.remove('hidden');
            document.getElementById('saveSection')?.classList.remove('hidden');
            document.getElementById('tagActions')?.classList.remove('hidden');
        }
    });

    // 初始化 jsTree — 使用函数式 data 实现懒加载
    $('#dynastyTree').jstree({
        core: {
            data: function(obj, cb) {
                if (obj.id === '#') {
                    // 根节点 -> 加载朝代列表
                    $.getJSON('/api/dynasties', function(data) {
                        // 标记 children: true 告诉 jsTree 有子节点需懒加载
                        cb(data.map(function(d) {
                            d.children = true;
                            return d;
                        }));
                    }).fail(function() { cb([]); });
                } else if (obj.type === 'dynasty') {
                    // 朝代节点展开 -> 加载作者列表
                    $.getJSON('/api/authors/' + obj.id, function(data) {
                        cb(data);
                    }).fail(function() { cb([]); });
                } else {
                    cb([]);
                }
            },
            check_callback: true,
            multiple: false,
            themes: { name: 'default', dots: true, icons: true },
        },
        plugins: ['types', 'state'],
        types: {
            dynasty: { icon: 'fas fa-landmark' },
            author: { icon: 'fas fa-user' },
        },
    });

    // 选择节点
    $('#dynastyTree').on('select_node.jstree', function(e, data) {
        const node = data.node;
        if (node.type === 'author') {
            currentAuthorId = node.id;
            document.getElementById('currentAuthorHint').textContent =
                node.data?.author_name || node.text;
            loadPoemList(node.id);
        } else if (node.type === 'dynasty') {
            // 点击朝代 -> 展开/收起
            data.instance.toggle_node(node);
        }
    });
});

function expandAllTree() {
    $('#dynastyTree').jstree('open_all');
}

function collapseAllTree() {
    $('#dynastyTree').jstree('close_all');
}

// 在树中选中指定作者
function selectAuthorInTree(authorId) {
    $('#dynastyTree').jstree('deselect_all');
    $('#dynastyTree').jstree('select_node', authorId);
}

// 刷新树
function refreshTree() {
    $('#dynastyTree').jstree('refresh');
}

/* ==================== 诗词列表 ==================== */

function loadPoemList(authorId) {
    const container = document.getElementById('poemListContainer');
    container.innerHTML = '<div style="text-align:center;padding:10px;color:#999;"><i class="fas fa-spinner fa-spin"></i> 加载中...</div>';

    $.get('/api/poems/' + authorId, function(poems) {
        if (!poems || poems.length === 0) {
            container.innerHTML = '<div class="empty-hint"><i class="fas fa-scroll"></i><p>暂无诗词</p></div>';
            return;
        }

        let html = '';
        poems.forEach(function(p) {
            const active = p.poem_id === currentPoemId ? ' active' : '';
            html += `<div class="poem-list-item${active}" data-poem-id="${p.poem_id}" onclick="selectPoem('${p.poem_id}')">
                <div class="poem-item-title">${p.title}</div>
            </div>`;
        });
        container.innerHTML = html;

        // 自动选中第一首
        if (!currentPoemId || !document.querySelector(`[data-poem-id="${currentPoemId}"]`)) {
            const first = document.querySelector('.poem-list-item');
            if (first) {
                first.click();
            }
        }
    }).fail(function() {
        container.innerHTML = '<div class="empty-hint"><i class="fas fa-exclamation-circle"></i><p>加载失败</p></div>';
    });
}
