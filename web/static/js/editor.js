/**
 * 编辑器脚本
 * 负责诗词内容的编辑和保存
 */

// 保存诗词
function savePoem() {
    const poemTitle = getCurrentPoemId();
    if (!poemTitle) {
        alert('请先选择一首诗词');
        return;
    }
    
    // 收集数据（title 和 author_name 放在 body 里，避免 URL 特殊字符问题）
    const data = {
        // 标识信息
        title: poemTitle,
        author_name: currentPoemAuthor || '',
        
        // 正文和赏析
        content: $('#poemContent').val(),
        appreciation: $('#poemAppreciation').val(),
        translation: $('#poemTranslation').val(),
        
        // 属性字段
        genre: $('#attrGenre').val(),
        form: $('#attrForm').val(),
        meter: $('#attrMeter').val(),
        theme: $('#attrTheme').val(),
        style: $('#attrStyle').val(),
        emotion: $('#attrEmotion').val(),
        imagery: $('#attrImagery').val(),
        allusions: $('#attrAllusions').val(),
        keywords: $('#attrKeywords').val(),
        season: $('#attrSeason').val(),
        festival: $('#attrFestival').val(),
        places_involved: $('#attrPlaces').val(),
        people_involved: $('#attrPeople').val(),
        background: $('#attrBackground').val(),
        historical_context: $('#attrHistoricalContext').val()
    };
    
    console.log('Saving poem:', poemTitle, data);
    
    // 发送保存请求（URL 不含 poem_id，改用 body 传递）
    $.ajax({
        url: '/api/poem/save',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        beforeSend: function() {
            $('#saveSection button').html('<i class="fas fa-spinner fa-spin"></i> 保存中...');
            $('#saveSection button').prop('disabled', true);
        },
        success: function(response) {
            console.log('Save success:', response);
            showSaveSuccess();
        },
        error: function(xhr, status, error) {
            console.error('Save error:', status, error, xhr.responseText);
            const errMsg = xhr.responseJSON ? xhr.responseJSON.error : error;
            showSaveError('保存失败: ' + (errMsg || 'INTERNAL SERVER ERROR'));
        },
        complete: function() {
            $('#saveSection button').html('<i class="fas fa-save"></i> 保存修改');
            $('#saveSection button').prop('disabled', false);
        }
    });
}

// 显示保存成功
function showSaveSuccess() {
    const btn = $('#saveSection button');
    const originalHtml = btn.html();
    
    //btn.removeClass('btn-primary').addClass('btn-success');
    btn.html('<i class="fas fa-check"></i> 已保存');
    btn.prop('disabled', false); // 禁用按钮以防止重复点击
    // btn 显示文字 “保存成功”

    setTimeout(1000);
    
    setTimeout(function() {
        btn.removeClass('btn-success').addClass('btn-primary');
        btn.html('<i class="fas fa-check"></i> 保存修改');
    }, 1000);
}

// 显示保存错误
function showSaveError(message) {
    alert(message);
}

// 标记有未保存的更改
function markUnsaved() {
    $('#saveSection button').addClass('unsaved');
}

// 初始化编辑器事件
$(document).ready(function() {
    // 监听内容变化
    $('#poemContent, #poemAppreciation, #poemTranslation').on('input', function() {
        markUnsaved();
    });
    
    // 监听属性变化
    $('.attr-input').on('input', function() {
        markUnsaved();
    });
    
    // 键盘快捷键 Ctrl+S 保存
    $(document).on('keydown', function(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            savePoem();
        }
    });
    
    // 离开页面时检查未保存的更改
    $(window).on('beforeunload', function(e) {
        if ($('#saveSection button').hasClass('unsaved')) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});

// 添加 unsaved 样式
$('<style>')
    .text(`
        #saveSection button.unsaved {
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
    `)
    .appendTo('head');
