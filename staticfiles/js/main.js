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
});