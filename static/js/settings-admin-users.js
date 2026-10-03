/**
 * Admin Users Management
 * Handles user table, permission toggles, and user deletion
 */

let dataSources = [];

// Initialize function
function initializeAdminUsers() {
    console.log('[Admin Users] Initialization started');
    const controlUsersSection = document.getElementById('control-users-section');
    console.log('[Admin Users] Control users section found:', !!controlUsersSection);
    if (controlUsersSection) {
        console.log('[Admin Users] Loading data sources...');
        loadDataSources();
    } else {
        console.log('[Admin Users] Section not found, skipping initialization');
    }
}

// Initialize on page load OR immediately if already loaded
if (document.readyState === 'loading') {
    console.log('[Admin Users] Document still loading, waiting for DOMContentLoaded');
    document.addEventListener('DOMContentLoaded', initializeAdminUsers);
} else {
    console.log('[Admin Users] Document already loaded, initializing immediately');
    initializeAdminUsers();
}

// Load data sources from config
async function loadDataSources() {
    try {
        console.log('[Admin Users] Fetching data sources from /admin/users/data-sources');
        const response = await fetch('/admin/users/data-sources');
        console.log('[Admin Users] Response status:', response.status);
        const data = await response.json();
        console.log('[Admin Users] Data sources response:', data);

        if (data.success) {
            dataSources = data.data_sources;
            console.log('[Admin Users] Data sources loaded:', dataSources.length);
            loadUsersTable();
        } else {
            console.error('[Admin Users] Failed to load data sources:', data.error);
        }
    } catch (error) {
        console.error('[Admin Users] Failed to load data sources:', error);
        showError('Failed to load data sources');
    }
}

// Load users table
async function loadUsersTable() {
    try {
        console.log('[Admin Users] Fetching users from /admin/users');
        const response = await fetch('/admin/users');
        console.log('[Admin Users] Response status:', response.status);
        const data = await response.json();
        console.log('[Admin Users] Users response:', data);

        if (data.success) {
            console.log('[Admin Users] Rendering', data.users.length, 'users');
            renderUsersTable(data.users);
        } else {
            console.error('[Admin Users] Failed to load users:', data.error);
            showError(data.error || 'Failed to load users');
        }
    } catch (error) {
        console.error('[Admin Users] Failed to load users:', error);
        showError('Failed to load users');
    }
}

// Render users table
function renderUsersTable(users) {
    console.log('[Admin Users] renderUsersTable called with', users.length, 'users');
    const table = document.getElementById('usersTable');
    const thead = table.querySelector('thead tr');
    const tbody = document.getElementById('usersTableBody');
    console.log('[Admin Users] Table elements found:', !!table, !!thead, !!tbody);

    // Add data source columns to header
    thead.innerHTML = `
        <th>Username</th>
        <th>Email</th>
        <th>Created</th>
        <th>Last Login</th>
        ${dataSources.map(ds => `<th>${ds.display_name}</th>`).join('')}
        <th>Status</th>
        <th>Actions</th>
    `;

    // Render rows
    tbody.innerHTML = users.map(user => {
        if (user.is_admin) {
            return `
                <tr class="admin-row">
                    <td>${escapeHtml(user.username)}</td>
                    <td>${escapeHtml(user.email)}</td>
                    <td colspan="${dataSources.length + 4}" class="admin-label">
                        <span class="badge badge-admin">Administrator</span>
                    </td>
                </tr>
            `;
        }

        const statusBadge = user.is_deleted 
            ? '<span class="badge badge-deleted">Deleted</span>'
            : '<span class="badge badge-active">Active</span>';

        return `
            <tr data-user-id="${user.id}" ${user.is_deleted ? 'class="deleted-row"' : ''}>
                <td>${escapeHtml(user.username)}</td>
                <td>${escapeHtml(user.email)}</td>
                <td>${formatDate(user.created_at)}</td>
                <td>${user.last_login ? formatDate(user.last_login) : 'Never'}</td>
                ${dataSources.map(ds => `
                    <td class="toggle-cell">
                        <label class="toggle-switch ${user.is_deleted ? 'disabled' : ''}">
                            <input type="checkbox"
                                   data-user-id="${user.id}"
                                   data-source="${ds.id}"
                                   ${user.permissions[ds.id] !== false ? 'checked' : ''}
                                   ${user.is_deleted ? 'disabled' : ''}
                                   onchange="togglePermission(${user.id}, '${ds.id}', this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                `).join('')}
                <td>${statusBadge}</td>
                <td>
                    <button class="btn-danger btn-sm" onclick="deleteUser(${user.id}, '${escapeHtml(user.username)}')">
                        ${user.is_deleted ? 'Purge' : 'Delete'}
                    </button>
                </td>
            </tr>
        `;
    }).join('');
    console.log('[Admin Users] Table rendered successfully');
}

// Toggle permission
async function togglePermission(userId, dataSource, enabled) {
    try {
        const response = await fetch(`/admin/users/${userId}/permissions`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ data_source: dataSource, enabled })
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(`Permission ${enabled ? 'enabled' : 'disabled'} for ${dataSource}`);
        } else {
            throw new Error(data.error || 'Failed to update permission');
        }
    } catch (error) {
        console.error('Failed to toggle permission:', error);
        showError(error.message);
        // Revert toggle
        const checkbox = document.querySelector(`input[data-user-id="${userId}"][data-source="${dataSource}"]`);
        if (checkbox) checkbox.checked = !enabled;
    }
}

// Delete user
async function deleteUser(userId, username) {
    // Get user row to check if already deleted
    const row = document.querySelector(`tr[data-user-id="${userId}"]`);
    const isDeleted = row && row.classList.contains('deleted-row');
    
    const confirmMessage = isDeleted 
        ? `Are you sure you want to PERMANENTLY DELETE user "${username}"?\n\nThis will:\n- Remove all user data from database\n- Delete chat history\n- Delete permissions\n- Email will be available for re-registration\n- This action CANNOT be undone!`
        : `Are you sure you want to delete user "${username}"?\n\nThis will:\n- Remove all user data from database\n- Delete chat history\n- Delete permissions\n- Email will be available for re-registration\n- This action CANNOT be undone!`;
    
    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        const response = await fetch(`/admin/users/${userId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            showSuccess(data.message);
            // Remove row from table
            const row = document.querySelector(`tr[data-user-id="${userId}"]`);
            if (row) row.remove();
            
            // Show additional info about email being available
            setTimeout(() => {
                showSuccess('✓ Email is now available for new user registration');
            }, 1500);
        } else {
            throw new Error(data.error || 'Failed to delete user');
        }
    } catch (error) {
        console.error('Failed to delete user:', error);
        showError(error.message);
    }
}

// Utility functions
function formatDate(dateString) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function showSuccess(message) {
    // Use existing flash message system or create toast
    console.log('Success:', message);

    // Create a temporary success message
    const msgDiv = document.createElement('div');
    msgDiv.className = 'toast-message success';
    msgDiv.textContent = '✓ ' + message;
    msgDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #10b981;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    document.body.appendChild(msgDiv);

    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => msgDiv.remove(), 300);
    }, 3000);
}

function showError(message) {
    console.error('Error:', message);

    // Create a temporary error message
    const msgDiv = document.createElement('div');
    msgDiv.className = 'toast-message error';
    msgDiv.textContent = '✗ ' + message;
    msgDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    document.body.appendChild(msgDiv);

    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => msgDiv.remove(), 300);
    }, 3000);
}

// Add animations
(function() {
    const styleElement = document.createElement('style');
    styleElement.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(styleElement);
})();
