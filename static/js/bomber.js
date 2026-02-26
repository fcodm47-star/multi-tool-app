// SMS Bomber specific JavaScript
let bomberSocket = null;
let bomberStats = {
    success: 0,
    fail: 0,
    total: 0
};

$(document).ready(function() {
    initializeBomber();
    loadBomberHistory();
});

function initializeBomber() {
    // Connect to socket
    bomberSocket = io();
    
    bomberSocket.on('connect', function() {
        addBomberLog('System', 'Connected to server', 'success');
        updateBomberStatus();
    });
    
    bomberSocket.on('service_result', function(data) {
        const icon = data.success ? '✅' : '❌';
        addBomberLog(data.service, `${icon} ${data.message}`, data.success ? 'success' : 'error');
        
        if (data.success) {
            bomberStats.success++;
        } else {
            bomberStats.fail++;
        }
        updateBomberStats();
    });
    
    bomberSocket.on('worker_result', function(data) {
        addBomberLog(`${data.worker} Worker`, `${data.message} (Batch ${data.batch})`, 
               data.success ? 'success' : 'warning');
        $(`#${data.worker.toLowerCase()}Queue`).text('0 pending');
    });
    
    bomberSocket.on('stats_update', function(stats) {
        bomberStats = stats;
        updateBomberStats();
        
        const total = stats.success + stats.fail;
        const percent = stats.total > 0 ? Math.round((total / stats.total) * 100) : 0;
        $('#progressBar').css('width', percent + '%');
    });
    
    bomberSocket.on('batch_start', function(data) {
        addBomberLog('System', `Starting batch ${data.batch}/${data.total}`, 'info');
        $('#progressText').text(`Batch ${data.batch}/${data.total}`);
    });
    
    bomberSocket.on('attack_complete', function(stats) {
        addBomberLog('System', `✅ Attack complete! Success: ${stats.success}, Failed: ${stats.fail}`, 'success');
        resetBomberButtons();
        loadBomberHistory();
    });
    
    bomberSocket.on('attack_error', function(data) {
        addBomberLog('Error', data.error, 'error');
        resetBomberButtons();
    });
}

function startBomberAttack() {
    const phone = $('#phoneNumber').val();
    const batches = $('#batches').val();
    
    if (!phone) {
        showBomberAlert('Please enter a phone number', 'warning');
        return;
    }
    
    // Validate Philippine number
    const cleanPhone = phone.replace(/[^0-9]/g, '');
    if (!/^09\d{9}$|^9\d{9}$/.test(cleanPhone)) {
        showBomberAlert('Invalid Philippine number format (e.g., 09123456789)', 'error');
        return;
    }
    
    if (batches < 1 || batches > 100) {
        showBomberAlert('Batches must be between 1 and 100', 'warning');
        return;
    }
    
    $('#startBtn').prop('disabled', true);
    $('#stopBtn').prop('disabled', false);
    $('#phoneNumber').prop('readonly', true);
    $('#batches').prop('readonly', true);
    
    // Clear previous logs
    $('#logs').empty();
    
    addBomberLog('System', `🚀 Launching attack on ${phone} (${batches} batches)`, 'info');
    
    $.ajax({
        url: '/bomber/api/start',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            phone: phone,
            batches: parseInt(batches)
        }),
        success: function(response) {
            if (!response.success) {
                showBomberAlert(response.error, 'error');
                resetBomberButtons();
            }
        },
        error: function(xhr) {
            showBomberAlert('Failed to start attack: ' + xhr.responseText, 'error');
            resetBomberButtons();
        }
    });
}

function stopBomberAttack() {
    $.ajax({
        url: '/bomber/api/stop',
        method: 'POST',
        success: function() {
            addBomberLog('System', '⏹️ Attack stopped by user', 'warning');
            resetBomberButtons();
        }
    });
}

function resetBomberButtons() {
    $('#startBtn').prop('disabled', false);
    $('#stopBtn').prop('disabled', true);
    $('#phoneNumber').prop('readonly', false);
    $('#batches').prop('readonly', false);
}

function updateBomberStatus() {
    $.get('/bomber/api/status', function(data) {
        if (data.user) {
            $('#attacks-today').text(data.user.attacks_today);
            
            // Warn if near limit
            if (data.user.attacks_today >= 4) {
                $('#attacks-today').parent().addClass('text-warning');
            }
            if (data.user.attacks_today >= 5) {
                $('#attacks-today').parent().addClass('text-danger');
                $('#startBtn').prop('disabled', true);
            }
        }
        
        if (data.running) {
            $('#startBtn').prop('disabled', true);
            $('#stopBtn').prop('disabled', false);
            $('#phoneNumber').prop('readonly', true);
            $('#batches').prop('readonly', true);
        }
        
        $('#mwellQueue').text(data.mwell_pending + ' pending');
        $('#pexxQueue').text(data.pexx_pending + ' pending');
    });
}

function updateBomberStats() {
    $('#successCount').text(bomberStats.success);
    $('#failCount').text(bomberStats.fail);
    
    const total = bomberStats.success + bomberStats.fail;
    const rate = total > 0 ? Math.round((bomberStats.success / total) * 100) : 0;
    $('#successRate').text(rate + '%');
}

function addBomberLog(source, message, type = 'info') {
    const time = new Date().toLocaleTimeString();
    const logEntry = `
        <div class="log-entry log-${type}">
            <span class="log-time">[${time}]</span>
            <strong>${source}:</strong> ${message}
        </div>
    `;
    $('#logs').prepend(logEntry);
    
    // Keep only last 100 logs
    if ($('#logs .log-entry').length > 100) {
        $('#logs .log-entry:last').remove();
    }
}

function showBomberAlert(message, type = 'info') {
    const alertDiv = $(`
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    $('.container').prepend(alertDiv);
    
    setTimeout(() => alertDiv.fadeOut('slow'), 5000);
}

function loadBomberHistory() {
    $.get('/bomber/api/history', function(attacks) {
        let html = '';
        attacks.forEach(attack => {
            html += `
                <tr>
                    <td>${attack.target}</td>
                    <td>${attack.messages}</td>
                    <td><span class="badge bg-${attack.status === 'completed' ? 'success' : 'warning'}">${attack.status}</span></td>
                    <td>${attack.date}</td>
                </tr>
            `;
        });
        
        if (html) {
            $('#attack-history').html(html);
        }
    });
}

// Auto-refresh status every 3 seconds
setInterval(updateBomberStatus, 3000);