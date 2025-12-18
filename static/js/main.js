// Utility to fetch API
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };
    if (data) options.body = JSON.stringify(data);

    const res = await fetch(`/api${endpoint}`, options);

    // Check if response is JSON
    const contentType = res.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'API Error');
        }
        return res.json();
    } else {
        // Handle non-JSON response (e.g. HTML error page)
        const text = await res.text();
        if (!res.ok) {
            throw new Error(`Server Error (${res.status}): ${text.substring(0, 100)}...`);
        }
        // If 200 OK but not JSON? Probably shouldn't happen for API
        throw new Error('Received non-JSON response from server');
    }
}

// Utility to show alerts
function showAlert(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    const container = document.querySelector('.main-content');
    container.insertBefore(alertDiv, container.firstChild);

    setTimeout(() => alertDiv.remove(), 5000);
}
