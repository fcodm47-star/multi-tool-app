// Global functions
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function showToast(message, type = 'info') {
    // Create toast container if not exists
    if (!$('#toast-container').length) {
        $('body').append('<div id="toast-container" style="position: fixed; top: 20px; right: 20px; z-index: 9999;"></div>');
    }
    
    const toastId = 'toast-' + Date.now();
    const bgColor = type === 'success' ? 'bg-success' : 
                   type === 'error' ? 'bg-danger' : 
                   type === 'warning' ? 'bg-warning' : 'bg-info';
    
    const toast = `
        <div id="${toastId}" class="toast ${bgColor} text-white" role="alert" style="min-width: 250px; margin-bottom: 10px;">
            <div class="toast-body d-flex justify-content-between align-items-center">
                ${message}
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    $('#toast-container').append(toast);
    const toastEl = new bootstrap.Toast(document.getElementById(toastId), { delay: 3000 });
    toastEl.show();
    
    setTimeout(() => $(`#${toastId}`).remove(), 3500);
}

// Add CSRF token to all AJAX requests
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", "{{ csrf_token() if csrf_token else '' }}");
        }
    }
});

// Auto-hide alerts after 5 seconds
setTimeout(function() {
    $('.alert').fadeOut('slow');
}, 5000);

// Initialize tooltips
$(function() {
    $('[data-toggle="tooltip"]').tooltip();
});

// Confirm actions
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Handle offline/online status
window.addEventListener('online', function() {
    showToast('You are back online!', 'success');
});

window.addEventListener('offline', function() {
    showToast('You are offline. Check your connection.', 'warning');
});

// Add loading state to buttons
$(document).on('click', 'button[type="submit"]', function() {
    const $btn = $(this);
    if ($btn.hasClass('no-loading')) return;
    
    $btn.prop('disabled', true);
    $btn.data('original-text', $btn.html());
    $btn.html('<span class="spinner-border spinner-border-sm me-2"></span>Loading...');
});

// Re-enable buttons after form submission
$(document).on('submit', 'form', function() {
    setTimeout(function() {
        $('button[type="submit"]').each(function() {
            const $btn = $(this);
            if ($btn.data('original-text')) {
                $btn.prop('disabled', false);
                $btn.html($btn.data('original-text'));
            }
        });
    }, 1000);
});

// Fetch recent activity
function loadRecentActivity() {
    $.get('/api/recent-activity', function(data) {
        let html = '';
        data.forEach(attack => {
            html += `
                <tr>
                    <td><span class="badge bg-${attack.type === 'sms' ? 'danger' : 'info'}">${attack.type.toUpperCase()}</span></td>
                    <td>${attack.target}</td>
                    <td>${attack.messages}</td>
                    <td><span class="badge bg-${attack.status === 'completed' ? 'success' : 'warning'}">${attack.status}</span></td>
                    <td>${attack.date}</td>
                </tr>
            `;
        });
        $('#recent-activity').html(html || '<tr><td colspan="5" class="text-center">No activity yet</td></tr>');
    });
}

// Auto-refresh status every 30 seconds
setInterval(loadRecentActivity, 30000);