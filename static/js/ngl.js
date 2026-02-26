// NGL Spammer specific JavaScript
let nglInterval = null;
let nglStats = {
    sent: 0,
    failed: 0,
    total: 0
};

$(document).ready(function() {
    initializeNGL();
    loadQuoteCount();
    loadNGLHistory();
    
    // Toggle custom message field
    $('#mode').change(function() {
        if ($(this).val() === '2') {
            $('#custom-message-group').slideDown();
            $('#quote-preview').slideUp();
        } else {
            $('#custom-message-group').slideUp();
            $('#quote-preview').slideDown();
            updateQuotePreview();
        }
    });
});

function initializeNGL() {
    // Load initial quote
    updateQuotePreview();
    
    // Validate inputs
    $('#count, #delay').on('input', function() {
        validateNGLInputs();
    });
}

function startNGLSpam() {
    const data = {
        username: $('#username').val().replace('@', ''),
        mode: $('#mode').val(),
        count: parseInt($('#count').val()),
        delay: parseFloat($('#delay').val()),
        message: $('#custom-message').val()
    };
    
    // Validation
    if (!data.username) {
        showNGLAalert('Please enter a username', 'warning');
        return;
    }
    
    if (data.count < 1 || data.count > 500) {
        showNGLAalert('Count must be between 1 and 500', 'warning');
        return;
    }
    
    if (data.delay < 0.1 || data.delay > 5) {
        showNGLAalert('Delay must be between 0.1 and 5 seconds', 'warning');
        return;
    }
    
    if (data.mode === '2' && !data.message) {
        showNGLAalert('Please enter a custom message', 'warning');
        return;
    }
    
    if (data.mode === '2' && data.message.length > 1000) {
        showNGLAalert('Message too long (max 1000 characters)', 'warning');
        return;
    }
    
    $('#startNGLBtn').prop('disabled', true);
    $('#stopNGLBtn').prop('disabled', false);
    $('#username, #count, #delay, #mode, #custom-message').prop('readonly', true);
    
    addNGLLog('System', `🚀 Starting spam to @${data.username} (${data.count} messages)`, 'info');
    
    $.ajax({
        url: '/ngl/api/start',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(response) {
            if (response.success) {
                // Start progress tracking
                nglInterval = setInterval(updateNGLProgress, 500);
            } else {
                showNGLAalert(response.error, 'error');
                resetNGLButtons();
            }
        },
        error: function() {
            showNGLAalert('Failed to start spam', 'error');
            resetNGLButtons();
        }
    });
}

function stopNGLSpam() {
    $.ajax({
        url: '/ngl/api/stop',
        method: 'POST',
        success: function() {
            addNGLLog('System', '⏹️ Spam stopped by user', 'warning');
            clearInterval(nglInterval);
            resetNGLButtons();
        }
    });
}

function resetNGLButtons() {
    $('#startNGLBtn').prop('disabled', false);
    $('#stopNGLBtn').prop('disabled', true);
    $('#username, #count, #delay, #mode, #custom-message').prop('readonly', false);
}

function updateNGLProgress() {
    $.get('/ngl/api/progress', function(data) {
        if (data.running) {
            const percent = Math.round((data.current / data.total) * 100);
            $('#ngl-progress-bar').css('width', percent + '%').text(percent + '%');
            
            nglStats.sent = data.current;
            nglStats.total = data.total;
            nglStats.failed = data.current - (data.current - 0); // This needs adjustment
            
            $('#ngl-sent').text(data.current);
            $('#ngl-total').text(data.total);
            
            if (data.current > 0) {
                addNGLLog('Progress', data.status, 'info');
            }
        } else {
            clearInterval(nglInterval);
            resetNGLButtons();
            
            if (data.status.includes('Completed')) {
                addNGLLog('System', '✅ ' + data.status, 'success');
                loadNGLHistory();
            }
        }
    });
}

function addNGLLog(source, message, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const logEntry = `
        <div class="log-entry log-${type}">
            <span class="log-time">[${time}]</span>
            <strong>${source}:</strong> ${message}
        </div>
    `;
    $('#ngl-logs').prepend(logEntry);
    
    // Keep only last 50 logs
    if ($('#ngl-logs .log-entry').length > 50) {
        $('#ngl-logs .log-entry:last').remove();
    }
}

function showNGLAalert(message, type = 'info') {
    const alertDiv = $(`
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('.container').prepend(alertDiv);
    
    setTimeout(() => alertDiv.fadeOut('slow'), 5000);
}

function validateNGLInputs() {
    const count = parseInt($('#count').val());
    const delay = parseFloat($('#delay').val());
    let valid = true;
    
    if (isNaN(count) || count < 1 || count > 500) {
        $('#count').addClass('is-invalid');
        valid = false;
    } else {
        $('#count').removeClass('is-invalid');
    }
    
    if (isNaN(delay) || delay < 0.1 || delay > 5) {
        $('#delay').addClass('is-invalid');
        valid = false;
    } else {
        $('#delay').removeClass('is-invalid');
    }
    
    $('#startNGLBtn').prop('disabled', !valid);
}

function updateQuotePreview() {
    $.get('/ngl/api/quotes/random', function(data) {
        $('#quote-preview small').html(`<i class="bi bi-quote me-1"></i>Sample: "${data.quote.substring(0, 100)}${data.quote.length > 100 ? '...' : ''}"`);
    });
}

function loadQuoteCount() {
    $.get('/ngl/api/quotes/count', function(data) {
        $('#quote-count').text(data.count + ' quotes available');
    });
}

function loadNGLHistory() {
    $.get('/ngl/api/history', function(attacks) {
        let html = '';
        attacks.forEach(attack => {
            html += `
                <tr>
                    <td>@${attack.target}</td>
                    <td>${attack.messages}</td>
                    <td><span class="badge bg-${attack.status === 'completed' ? 'success' : 'warning'}">${attack.status}</span></td>
                    <td>${attack.date}</td>
                </tr>
            `;
        });
        
        if (html) {
            $('#ngl-history').html(html);
        }
    });
}

// Auto-refresh quote preview every 10 seconds if in random mode
setInterval(function() {
    if ($('#mode').val() === '1') {
        updateQuotePreview();
    }
}, 10000);