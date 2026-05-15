// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
    
    // Auto-cerrar alertas después de 5 segundos
    setTimeout(function() {
        document.querySelectorAll('.alert').forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
    
    // Confirmación antes de eliminar
    window.confirmar = function(mensaje) {
        return confirm(mensaje || '¿Estás seguro? Esta acción no se puede deshacer.');
    };
    
    // Tooltips de Bootstrap
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(el => new bootstrap.Tooltip(el));
    
    // Resaltar filas clickeables
    document.querySelectorAll('.fila-link').forEach(function(fila) {
        fila.style.cursor = 'pointer';
        fila.addEventListener('click', function() {
            window.location = this.dataset.href;
        });
    });

    if (document.body.dataset.authenticated === 'true') {
        let socket = null;
        let reconnectAttempts = 0;

        const showToast = function(data) {
            const container = document.getElementById('toast-container') || createToastContainer();
            const toast = document.createElement('div');
            toast.className = 'alert alert-info alert-dismissible fade show';
            toast.style.cssText = 'min-width:300px;box-shadow:0 2px 8px rgba(0,0,0,.15);';
            toast.innerHTML = `
                <strong>${data.codigo}</strong><br>
                Estado: ${data.estado_anterior} &rarr; ${data.estado_nuevo}<br>
                <small>Por: ${data.empleado}</small>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 5000);
        };

        const createToastContainer = function() {
            const div = document.createElement('div');
            div.id = 'toast-container';
            div.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
            document.body.appendChild(div);
            return div;
        };

        const connectGlobalSocket = function() {
            const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
            socket = new WebSocket(protocol + window.location.host + '/ws/encomiendas/');

            socket.onopen = function() {
                reconnectAttempts = 0;
                socket.send(JSON.stringify({ tipo: 'solicitar_stats' }));
            };

            socket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.tipo === 'estado_cambio') {
                    showToast(data);
                    document.dispatchEvent(new CustomEvent('encomienda:estado_cambio', { detail: data }));
                }
                if (data.tipo === 'progreso') {
                    document.dispatchEvent(new CustomEvent('encomienda:progreso', { detail: data }));
                }
            };

            socket.onclose = function(event) {
                if (event.code === 4001) {
                    return;
                }
                if (event.code === 1000) {
                    return;
                }
                reconnectAttempts += 1;
                const delay = Math.min(30000, 1000 * (2 ** reconnectAttempts));
                setTimeout(connectGlobalSocket, delay);
            };

            socket.onerror = function() {};
        };

        connectGlobalSocket();
    }
});
