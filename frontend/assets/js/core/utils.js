export function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;

    // Style it (if not in CSS)
    Object.assign(notification.style, {
        position: 'fixed',
        top: '20px',
        right: '20px',
        padding: '15px 25px',
        borderRadius: '4px',
        color: 'white',
        fontWeight: '500',
        zIndex: '1000',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        transition: 'opacity 0.3s ease-in-out',
        backgroundColor: type === 'success' ? '#4CAF50' :
            type === 'error' ? '#f44336' :
                type === 'warning' ? '#ff9800' : '#2196F3'
    });

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

export function formatCurrency(amount) {
    return new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'EUR'
    }).format(amount);
}

export function formatDate(dateString) {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('es-ES');
}
