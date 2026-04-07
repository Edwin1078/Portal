
const API_URL = "http://localhost:8000/api";

// State Management
let currentUser = null;
let currentToken = localStorage.getItem('token');

// Helper for API calls
async function apiFetch(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (currentToken) headers['Authorization'] = `Bearer ${currentToken}`;
    
    const config = { method, headers };
    if (body) config.body = JSON.stringify(body);
    
    const res = await fetch(`${API_URL}${endpoint}`, config);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Error en la petición');
    return data;
}

// Password Toggle Function
function togglePass(btn) {
    const input = btn.parentElement.querySelector('input');
    if (input.type === 'password') {
        input.type = 'text';
        btn.style.color = 'var(--primary-light)';
    } else {
        input.type = 'password';
        btn.style.color = 'var(--text-dim)';
    }
}

// Layout Transitions
function showView(viewId) {
    document.querySelectorAll('main > div').forEach(v => v.classList.add('hidden'));
    document.getElementById(`view-${viewId}`).classList.remove('hidden');
    
    // Sidebar & Auth Layout logic
    const sidebar = document.getElementById('sidebar');
    const isAuth = ['login', 'register', 'force-reset'].includes(viewId);
    
    if (isAuth) {
        sidebar.classList.add('hidden');
        document.body.classList.add('auth-mode');
    } else {
        sidebar.classList.remove('hidden');
        document.body.classList.remove('auth-mode');
    }

    // Active nav state
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    if (viewId === 'user-dashboard') document.querySelectorAll('.nav-item')[0].classList.add('active');
    if (viewId === 'admin') document.getElementById('nav-admin').classList.add('active');
}

async function logout() {
    const result = await Swal.fire({
        title: '¿Cerrar Sesión?',
        text: "Deberás ingresar tus credenciales nuevamente.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, Salir',
        cancelButtonText: 'Cancelar',
        reverseButtons: true
    });

    if (result.isConfirmed) {
        localStorage.removeItem('token');
        currentUser = null;
        currentToken = null;
        window.location.reload();
    }
}

// Authentication Initialization
async function init() {
    if (!currentToken) return showView('login');
    
    try {
        currentUser = await apiFetch('/users/me');
        
        // Update User Display
        document.getElementById('user-display-name').innerText = currentUser.full_name;
        document.getElementById('user-display-email').innerText = currentUser.email;

        if (currentUser.must_change_password) {
            return showView('force-reset');
        }

        if (currentUser.role === 'Admin') {
            document.getElementById('nav-admin').classList.remove('hidden');
            renderAdmin();
        } else {
            document.getElementById('nav-admin').classList.add('hidden');
        }
        
        renderDashboardList();
        showView('user-dashboard');
    } catch (e) {
        console.error(e);
        localStorage.removeItem('token');
        showView('login');
    }
}

// Dashboard Rendering
function createDashboardCard(name) {
    const icons = {
        'Historico': `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`,
        'Conceptos': `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>`
    };
    
    // Icono por defecto si el nombre no coincide
    const icon = icons[name] || `<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>`;

    const card = document.createElement('div');
    card.className = 'report-card';
    card.innerHTML = `
        <div class="report-icon">${icon}</div>
        <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;">Visualización</div>
        <h3>${name}</h3>
        <button class="btn-primary" style="width: 100%;" onclick="openViewer('${name}')">Explorar Datos</button>
    `;
    return card;
}

function renderDashboardList() {
    const list = document.getElementById('dashboard-list');
    list.innerHTML = '';

    const available = ['Historico', 'Conceptos'];
    available.forEach(name => {
        const hasPerm = currentUser.permissions.includes(`view_${name.toLowerCase()}`) || currentUser.role === 'Admin';
        if (hasPerm) {
            const card = createDashboardCard(name);
            list.appendChild(card);
        }
    });

    if (list.innerHTML === '') {
        list.innerHTML = '<p style="color: var(--text-dim);">No tienes reportes asignados.</p>';
    }
}

// Admin Panel Logic
let usersDataTable = null;
async function renderAdmin() {
    const pendingList = document.getElementById('pending-table').querySelector('tbody');
    pendingList.innerHTML = '';

    const pending = await apiFetch('/admin/pending');
    pending.forEach(u => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${u.full_name}</td>
            <td style="color: var(--text-dim);">${u.email}</td>
            <td><button class="btn-ghost" onclick="approveUser(${u.id})">Aprobar</button></td>
        `;
        pendingList.appendChild(row);
    });

    const allUsers = await apiFetch('/admin/users');
    
    // Si la tabla ya está inicializada, la destruimos para recargarla
    if (usersDataTable) {
        usersDataTable.destroy();
    }

    const usersList = document.getElementById('users-table').querySelector('tbody');
    usersList.innerHTML = '';
    allUsers.forEach(u => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div style="font-weight:700;">${u.email}</div>
                <div style="font-size:0.7rem; color:var(--text-muted);">${u.full_name}</div>
            </td>
            <td><span class="status-badge" style="background: ${u.role === 'Admin' ? 'rgba(14, 165, 233, 0.1)' : '#f1f5f9'}; color: ${u.role === 'Admin' ? 'var(--primary)' : 'var(--text-muted)'};">${u.role}</span></td>
            <td>
                <div style="display:flex; gap:0.5rem;">
                    <button class="btn-action" onclick="editUser(${u.id}, '${u.email}', '${u.full_name}', '${u.role}', '${u.current_permissions}')">
                        <svg style="width:14px;height:14px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>
                    </button>
                    <button class="btn-action danger" onclick="deleteUser(${u.id}, '${u.email}')">
                        <svg style="width:14px;height:14px;" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                    </button>
                </div>
            </td>
        `;
        usersList.appendChild(row);
    });

    // Re-inicializamos DataTable con idioma integrado
    usersDataTable = $('#users-table').DataTable({
        language: {
            search: "Buscar:",
            lengthMenu: "Mostrar _MENU_ registros",
            info: "Mostrando _START_ a _END_ de _TOTAL_ usuarios",
            infoEmpty: "Mostrando 0 a 0 de 0 usuarios",
            infoFiltered: "(filtrado de _MAX_ usuarios totales)",
            paginate: { first: "Primero", last: "Último", next: "Siguiente", previous: "Anterior" },
            zeroRecords: "No se encontraron usuarios"
        },
        pageLength: 5,
        lengthMenu: [5, 10, 25, 50],
        destroy: true,
        responsive: true
    });
}

let editingUserId = null;
function editUser(id, email, name, role, perms) {
    editingUserId = id;
    document.getElementById('adm-new-name').value = name;
    document.getElementById('adm-new-email').value = email;
    document.getElementById('adm-new-password').placeholder = "(Vaco para dejar igual)";
    document.getElementById('adm-new-password').required = false;
    document.getElementById('adm-new-role').value = (role === 'Admin' ? '1' : '2');
    
    const permList = perms ? perms.split(',') : [];
    document.getElementById('perm-hist').checked = permList.includes('view_historico');
    document.getElementById('perm-conc').checked = permList.includes('view_conceptos');
    document.getElementById('admin-create-user-form').querySelector('button').innerText = "Actualizar Datos";
}

async function deleteUser(id, email) {
    if (email === currentUser.email) return Swal.fire('Error', "No puedes eliminarte a ti mismo", 'error');
    const res = await Swal.fire({ title: '¿Eliminar usuario?', text: email, icon: 'warning', showCancelButton: true });
    if (res.isConfirmed) {
        try {
            await apiFetch(`/admin/delete-user/${id}`, 'DELETE');
            Swal.fire('Eliminado', '', 'success');
            renderAdmin();
        } catch (e) { Swal.fire('Error', e.message, 'error'); }
    }
}

async function approveUser(id) {
    try {
        await apiFetch(`/admin/approve/${id}`, 'POST');
        Swal.fire('Aprobado', '', 'success');
        renderAdmin();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
}

// Viewer Control
function openViewer(name) {
    document.getElementById('view-viewer').classList.remove('hidden');
    document.getElementById('viewer-title').innerText = `REPORTE: ${name.toUpperCase()}`;
    // Pass token for iframe authentication
    document.getElementById('dashboard-iframe').src = `/api/dashboard/view/${name}?token=${currentToken}`;
}

function closeViewer() {
    document.getElementById('view-viewer').classList.add('hidden');
    document.getElementById('dashboard-iframe').src = '';
}

// Form Event Listeners
document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append('username', document.getElementById('login-email').value);
    formData.append('password', document.getElementById('login-password').value);
    
    try {
        const res = await fetch(`${API_URL}/token`, { method: 'POST', body: formData });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login fallido');
        localStorage.setItem('token', data.access_token);
        currentToken = data.access_token;
        init();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('register-form').onsubmit = async (e) => {
    e.preventDefault();
    const body = {
        full_name: document.getElementById('reg-name').value,
        email: document.getElementById('reg-email').value,
        password: document.getElementById('reg-password').value
    };
    try {
        await apiFetch('/register', 'POST', body);
        Swal.fire('Solicitud Enviada', 'Espera la aprobacin del administrador', 'success');
        showView('login');
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('reset-form').onsubmit = async (e) => {
    e.preventDefault();
    const p1 = document.getElementById('reset-new-password').value;
    const p2 = document.getElementById('reset-confirm-password').value;
    if (p1 !== p2) return Swal.fire('Error', 'No coinciden', 'warning');
    try {
        await apiFetch('/users/update-password', 'POST', { new_password: p1 });
        Swal.fire('Listo', 'Contrasea actualizada', 'success');
        init();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('admin-create-user-form').onsubmit = async (e) => {
    e.preventDefault();
    const perms = [];
    if (document.getElementById('perm-hist').checked) perms.push('view_historico');
    if (document.getElementById('perm-conc').checked) perms.push('view_conceptos');
    
    const body = {
        full_name: document.getElementById('adm-new-name').value,
        email: document.getElementById('adm-new-email').value,
        password: document.getElementById('adm-new-password').value || "TEMP123",
        role_id: parseInt(document.getElementById('adm-new-role').value),
        permissions: perms
    };
    
    try {
        const ep = editingUserId ? `/admin/update-user/${editingUserId}` : '/alta-usuario';
        await apiFetch(ep, 'POST', body);
        Swal.fire('Completado', '', 'success');
        editingUserId = null;
        e.target.reset();
        document.getElementById('admin-create-user-form').querySelector('button').innerText = "Ejecutar Accin";
        renderAdmin();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

// Start
init();
