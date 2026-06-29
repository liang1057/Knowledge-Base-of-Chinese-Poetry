/**
 * 管理后台 JS - KBCP v2
 * 处理 朝代/作者/诗词/受控词表/用户 的 CRUD
 */

// ==================== 朝代管理 ====================

function showAddDynastyModal() {
    document.getElementById('dynastyModalTitle').innerHTML = '<i class="fas fa-landmark"></i> 添加朝代';
    document.getElementById('editDynastyId').value = '';
    document.getElementById('dynastyName').value = '';
    document.getElementById('dynastyAnotherName').value = '';
    document.getElementById('dynastyStart').value = '';
    document.getElementById('dynastyEnd').value = '';
    document.getElementById('dynastyNote').value = '';
    new bootstrap.Modal(document.getElementById('dynastyModal')).show();
}

function editDynasty(dynastyId) {
    // 目前 API 不支持按 ID 获取单条，从表格行中读取
    const row = $(`#dynastyTableBody tr:has(td:first-child:text("${dynastyId}")`).first();
    // 简单方式: 用 prompt 手动编辑
    const name = prompt('朝代名称:', $(`#dynastyTableBody tr`).filter(function() {
        return $(this).find('td:first').text() === dynastyId;
    }).find('td:eq(1)').text() || '');
    if (name && name.trim()) {
        $.ajax({
            url: '/api/dynasty/edit/' + dynastyId,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({name: name.trim()}),
            success: function() { location.reload(); },
        });
    }
}

function deleteDynasty(dynastyId) {
    $.ajax({
        url: '/api/dynasty/delete/' + dynastyId,
        method: 'POST',
        success: function(res) {
            if (res.status === 'success') location.reload();
        },
        error: function(xhr) {
            alert(xhr.responseJSON?.error || '删除失败');
        }
    });
}

function saveDynasty() {
    const id = document.getElementById('editDynastyId').value;
    const name = document.getElementById('dynastyName').value.trim();
    if (!name) { alert('名称不能为空'); return; }

    const data = {
        name: name,
        another_name: document.getElementById('dynastyAnotherName').value,
        start_year: parseInt(document.getElementById('dynastyStart').value) || null,
        end_year: parseInt(document.getElementById('dynastyEnd').value) || null,
        note: document.getElementById('dynastyNote').value,
    };

    if (id) {
        $.ajax({
            url: '/api/dynasty/edit/' + id,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() { location.reload(); },
        });
    } else {
        $.ajax({
            url: '/api/dynasty/add',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() { location.reload(); },
        });
    }
}

// ==================== 作者管理 ====================

function loadAuthorList() {
    const dynastyId = document.getElementById('authorFilterDynasty').value;
    const container = document.getElementById('authorListContainer');

    if (!dynastyId) {
        container.innerHTML = '<div class="text-muted text-center py-4">请选择朝代查看作者</div>';
        return;
    }

    $.get('/api/authors/' + dynastyId, function(authors) {
        if (!authors || authors.length === 0) {
            container.innerHTML = '<div class="text-muted text-center py-4">该朝代暂无作者</div>';
            return;
        }
        let html = '<div class="list-group">';
        authors.forEach(function(a) {
            html += `<div class="list-group-item d-flex justify-content-between align-items-center">
                <div><strong>${a.data.author_name}</strong> <small class="text-muted">(${a.data.poem_count}首)</small></div>
                <div>
                    <button class="btn btn-sm btn-outline-primary" onclick="editAuthor('${a.id}')"><i class="fas fa-edit"></i></button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteAuthorConfirm('${a.id}','${a.data.author_name}')"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    });
}

function showAddAuthorModal() {
    document.getElementById('authorModalTitle').innerHTML = '<i class="fas fa-user-plus"></i> 添加作者';
    document.getElementById('editAuthorId').value = '';
    document.getElementById('authorName').value = '';
    document.getElementById('authorCourtesy').value = '';
    document.getElementById('authorArt').value = '';
    document.getElementById('authorBio').value = '';
    document.getElementById('deleteAuthorBtn').style.display = 'none';
    new bootstrap.Modal(document.getElementById('authorModal')).show();
}

function editAuthor(authorId) {
    $.get('/api/author/' + authorId, function(data) {
        const a = data.author;
        document.getElementById('authorModalTitle').innerHTML = '<i class="fas fa-edit"></i> 编辑作者';
        document.getElementById('editAuthorId').value = a.author_id;
        document.getElementById('authorDynasty').value = a.dynasty_id;
        document.getElementById('authorName').value = a.name;
        document.getElementById('authorCourtesy').value = a.courtesy_name || '';
        document.getElementById('authorArt').value = a.art_name || '';
        document.getElementById('authorBio').value = a.bio || '';
        document.getElementById('deleteAuthorBtn').style.display = 'inline-block';
        new bootstrap.Modal(document.getElementById('authorModal')).show();
    });
}

function saveAuthor() {
    const id = document.getElementById('editAuthorId').value;
    const name = document.getElementById('authorName').value.trim();
    if (!name) { alert('姓名不能为空'); return; }

    const data = {
        name: name,
        dynasty_id: document.getElementById('authorDynasty').value,
        courtesy_name: document.getElementById('authorCourtesy').value,
        art_name: document.getElementById('authorArt').value,
        bio: document.getElementById('authorBio').value,
    };

    if (id) {
        $.ajax({
            url: '/api/author/edit/' + id,
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() { location.reload(); },
        });
    } else {
        $.ajax({
            url: '/api/author/add',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(data),
            success: function() { location.reload(); },
        });
    }
}

function deleteAuthor() {
    const id = document.getElementById('editAuthorId').value;
    if (confirm('确定删除该作者及他所有的诗词吗？')) {
        $.ajax({
            url: '/api/author/delete/' + id,
            method: 'POST',
            success: function() { location.reload(); },
        });
    }
}

function deleteAuthorConfirm(id, name) {
    if (confirm(`确定删除作者「${name}」吗？（将级联删除其所有诗词）`)) {
        $.ajax({
            url: '/api/author/delete/' + id,
            method: 'POST',
            success: function() { loadAuthorList(); },
        });
    }
}

// ==================== 诗词管理 ====================

function loadPoemAuthors() {
    const dynastyId = document.getElementById('poemFilterDynasty').value;
    const authorSelect = document.getElementById('poemFilterAuthor');

    if (!dynastyId) {
        authorSelect.innerHTML = '<option value="">选择作者</option>';
        document.getElementById('poemListContainerAdmin').innerHTML = '<div class="text-muted text-center py-4">请选择朝代</div>';
        return;
    }

    $.get('/api/authors/' + dynastyId, function(authors) {
        let options = '<option value="">选择作者</option>';
        authors.forEach(function(a) {
            options += `<option value="${a.id}">${a.data.author_name} (${a.data.poem_count}首)</option>`;
        });
        authorSelect.innerHTML = options;
    });
}

function loadPoemList() {
    const authorId = document.getElementById('poemFilterAuthor').value;
    const container = document.getElementById('poemListContainerAdmin');

    if (!authorId) {
        container.innerHTML = '<div class="text-muted text-center py-4">请选择作者</div>';
        return;
    }

    $.get('/api/poems/' + authorId, function(poems) {
        if (!poems || poems.length === 0) {
            container.innerHTML = '<div class="text-muted text-center py-4">暂无诗词</div>';
            return;
        }
        let html = '<div class="list-group">';
        poems.forEach(function(p) {
            html += `<div class="list-group-item d-flex justify-content-between align-items-center">
                <div><strong>${p.title}</strong> <small class="text-muted">${p.poem_id}</small></div>
                <div>
                    <button class="btn btn-sm btn-outline-danger" onclick="deletePoemAdmin('${p.poem_id}','${p.title}')"><i class="fas fa-trash"></i></button>
                </div>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    });
}

function showAddPoemModalAdmin() {
    document.getElementById('adminNewPoemTitle').value = '';
    document.getElementById('adminNewPoemContent').value = '';
    document.getElementById('adminNewPoemAppreciation').value = '';
    new bootstrap.Modal(document.getElementById('addPoemModalAdmin')).show();
}

function addPoemAdmin() {
    const authorId = document.getElementById('poemFilterAuthor').value;
    const title = document.getElementById('adminNewPoemTitle').value.trim();
    if (!authorId) { alert('请先选择作者'); return; }
    if (!title) { alert('请输入标题'); return; }

    $.ajax({
        url: '/api/poem/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            author_id: authorId,
            title: title,
            content: document.getElementById('adminNewPoemContent').value,
            appreciation: document.getElementById('adminNewPoemAppreciation').value,
        }),
        success: function() {
            alert('添加成功');
            bootstrap.Modal.getInstance(document.getElementById('addPoemModalAdmin')).hide();
            loadPoemList();
        },
    });
}

function deletePoemAdmin(poemId, title) {
    if (confirm(`确定删除诗词「${title}」吗？`)) {
        $.ajax({
            url: '/api/poem/delete',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({poem_id: poemId}),
            success: function() { loadPoemList(); },
        });
    }
}

// ==================== 受控词表管理 ====================

$(document).ready(function() {
    // 加载所有 vocab 列表
    $.get('/api/vocab/categories', function(categories) {
        categories.forEach(function(cat) {
            const container = document.getElementById('vocabList_' + cat);
            if (!container) return;
            $.get('/api/vocab/' + cat, function(items) {
                let html = '';
                items.forEach(function(item) {
                    html += `<span class="tag-badge">${item.label} <span class="tag-remove" onclick="deleteVocab('${item.vocab_id}','${item.label}')">×</span></span>`;
                });
                container.innerHTML = html || '<span class="text-muted small">无词条</span>';
            });
        });
    });
});

function addVocabToCategory(category) {
    document.getElementById('vocabCategory').value = category;
    document.getElementById('vocabLabel').value = '';
    new bootstrap.Modal(document.getElementById('addVocabModal')).show();
}

function showAddVocabModal() {
    document.getElementById('vocabLabel').value = '';
    new bootstrap.Modal(document.getElementById('addVocabModal')).show();
}

function saveVocab() {
    const category = document.getElementById('vocabCategory').value;
    const label = document.getElementById('vocabLabel').value.trim();
    if (!label) { alert('请输入词条名称'); return; }

    $.ajax({
        url: '/api/vocab/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({category: category, label: label}),
        success: function() { location.reload(); },
        error: function(xhr) {
            alert(xhr.responseJSON?.error || '添加失败');
        }
    });
}

function deleteVocab(vocabId, label) {
    if (confirm(`确定删除词条「${label}」吗？`)) {
        $.ajax({
            url: '/api/vocab/delete/' + vocabId,
            method: 'POST',
            success: function() { location.reload(); },
            error: function(xhr) {
                alert(xhr.responseJSON?.error || '删除失败');
            }
        });
    }
}

// ==================== 用户管理 ====================

function loadUsers() {
    $.get('/api/users', function(users) {
        let html = '';
        users.forEach(function(u) {
            html += `<tr>
                <td>${u.user_id}</td>
                <td>${u.username}</td>
                <td><span class="badge bg-${u.role === 'superadmin' ? 'danger' : u.role === 'admin' ? 'warning' : 'secondary'}">${u.role}</span></td>
                <td>${u.created_at || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteUser('${u.user_id}','${u.username}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            </tr>`;
        });
        document.getElementById('userTableBody').innerHTML = html;
    });
}

function showAddUserModal() {
    document.getElementById('newUserName').value = '';
    document.getElementById('newUserPassword').value = '';
    new bootstrap.Modal(document.getElementById('addUserModal')).show();
}

function saveUser() {
    const username = document.getElementById('newUserName').value.trim();
    const password = document.getElementById('newUserPassword').value;
    const role = document.getElementById('newUserRole').value;
    if (!username || !password) { alert('用户名和密码不能为空'); return; }

    $.ajax({
        url: '/api/user/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({username, password, role}),
        success: function() {
            alert('添加成功');
            bootstrap.Modal.getInstance(document.getElementById('addUserModal')).hide();
            loadUsers();
        },
        error: function(xhr) {
            alert(xhr.responseJSON?.error || '添加失败');
        }
    });
}

function deleteUser(userId, username) {
    if (confirm(`确定删除用户「${username}」吗？`)) {
        $.ajax({
            url: '/api/user/delete/' + userId,
            method: 'POST',
            success: function() { loadUsers(); },
            error: function(xhr) {
                alert(xhr.responseJSON?.error || '删除失败');
            }
        });
    }
}

// 用户 Tab 激活时加载
$(document).ready(function() {
    // 监听 Tab 切换
    document.querySelectorAll('[data-bs-toggle="tab"]').forEach(function(btn) {
        btn.addEventListener('shown.bs.tab', function(e) {
            if (e.target.getAttribute('data-bs-target') === '#tabUsers') {
                loadUsers();
            }
        });
    });
});
