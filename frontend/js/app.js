
const API_URL = "/api";

// State Management
let currentUser = null;
let currentToken = localStorage.getItem('token');
let idleTimeout = null;

// Helper: Session Timeout (20 min)
function resetIdleTimer() {
    if (!currentToken) return;
    clearTimeout(idleTimeout);
    idleTimeout = setTimeout(() => {
        localStorage.removeItem('token');
        Swal.fire({
            title: 'Sesión Expirada',
            text: 'Tu sesión ha finalizado por inactividad (20 min).',
            icon: 'info',
            confirmButtonText: 'Reconectar'
        }).then(() => {
            window.location.reload();
        });
    }, 20 * 60 * 1000);
}

// Activity Listeners
['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart'].forEach(name => {
    document.addEventListener(name, resetIdleTimer, true);
});

// Helper: API calls
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

// Layout Transitions
function showView(viewId) {
    // Hide all views
    document.querySelectorAll('main > div').forEach(v => v.classList.add('hidden'));
    
    // Show target view
    const view = document.getElementById(`view-${viewId}`);
    if (view) view.classList.remove('hidden');
    
    // Sidebar & Auth Header visibility
    const sidebar = document.getElementById('sidebar');
    const header = document.getElementById('app-header');
    const isAuth = ['login', 'register', 'force-reset'].includes(viewId);
    
    if (isAuth) {
        sidebar.classList.add('hidden');
        header.classList.add('hidden');
        document.getElementById('app-footer').classList.add('hidden');
        document.body.classList.add('auth-mode');
    } else {
        sidebar.classList.remove('hidden');
        header.classList.remove('hidden');
        document.getElementById('app-footer').classList.remove('hidden');
        document.body.classList.remove('auth-mode');
        
        // Mark active menu item
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.getAttribute('onclick')?.includes(viewId)) item.classList.add('active');
        });

        // Update Breadcrumb
        const crumbs = { 'admin': 'ADMINISTRACIÓN / USUARIOS', 'user-dashboard': 'BIENVENIDO / REPORTES' };
        document.getElementById('breadcrumb').innerText = crumbs[viewId] || 'PORTAL / INICIO';
    }

    // View Initializers
    if (viewId === 'admin') renderAdmin();
    if (viewId === 'user-dashboard') renderDashboardList();
}

// Helper: Theme Management
function toggleGlobalTheme() {
    const body = document.body;
    const isDark = body.classList.toggle('dark-mode');
    localStorage.setItem('portal-theme', isDark ? 'dark' : 'light');
    
    // Update Icon and Text
    updateThemeUI(isDark);
    
    // Notify Iframe if exists
    const iframe = document.getElementById('dashboard-iframe');
    if (iframe && iframe.contentWindow) {
        iframe.contentWindow.postMessage({ type: 'THEME_CHANGE', theme: isDark ? 'dark' : 'light' }, '*');
    }
}

function updateThemeUI(isDark) {
    const icon = document.getElementById('theme-icon');
    const text = document.getElementById('theme-text');
    const iconHeader = document.getElementById('theme-icon-header');
    
    // Viewer elements
    const iconViewer = document.getElementById('theme-icon-viewer');
    const textViewer = document.getElementById('theme-text-viewer');
    
    const darkPath = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m12.728 0l-.707-.707M6.343 6.343l-.707-.707M14 12a2 2 0 11-4 0 2 2 0 014 0z"></path>';
    const lightPath = '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"></path>';

    if (icon) icon.innerHTML = isDark ? darkPath : lightPath;
    if (text) text.innerText = isDark ? 'Modo Claro' : 'Modo Oscuro';
    if (iconHeader) iconHeader.innerHTML = isDark ? darkPath : lightPath;
    
    if (iconViewer) iconViewer.innerHTML = isDark ? darkPath : lightPath;
    if (textViewer) textViewer.innerText = isDark ? 'Modo Claro' : 'Modo Oscuro';
}

function toggleProfileDropdown(e) {
    e.stopPropagation();
    document.getElementById('profile-dropdown').classList.toggle('show');
}

// Close dropdown when clicking outside
document.addEventListener('click', () => {
    const drop = document.getElementById('profile-dropdown');
    if (drop) drop.classList.remove('show');
});

function applyInitialTheme() {
    const theme = localStorage.getItem('portal-theme') || 'light';
    const isDark = theme === 'dark';
    document.body.classList.toggle('dark-mode', isDark);
    updateThemeUI(isDark);
}

// Global Init
async function init() {
    applyInitialTheme();
    if (!currentToken) return showView('login');
    
    try {
        currentUser = await apiFetch('/users/me');
        
        // UI Updates
        document.getElementById('user-display-name').innerText = currentUser.full_name;
        document.getElementById('user-display-email').innerText = currentUser.email;
        document.getElementById('reset-username').value = currentUser.email;

        if (currentUser.must_change_password) return showView('force-reset');

        // Admin Visibility
        if (currentUser.role === 'Admin') {
            document.getElementById('nav-admin').classList.remove('hidden');
        } else {
            document.getElementById('nav-admin').classList.add('hidden');
        }
        
        showView('user-dashboard');
        updateSidebarVisibility();
        resetIdleTimer();
    } catch (e) {
        console.error("Auth Fail", e);
        logout();
    }
}

function updateSidebarVisibility() {
    if (!currentUser) return;
    const isAd = currentUser.role === 'Admin';
    const perms = currentUser.permissions || [];

    const map = {
        'nav-bdef-index': 'view_bdef_index',
        'nav-bdef-individual': 'view_bdef_individual',
        'nav-bdef-bulk': 'view_bdef_bulk',
        'nav-bdef-deuda': 'view_bdef_deuda',
        'nav-bdef-recaudo': 'view_bdef_recaudo',
        'nav-bdef-history': 'view_bdef_history',
        'nav-bdef-transformer': 'view_bdef_transformer',
        'nav-bdef-territorial': 'view_bdef_territorial'
    };

    let visibleBDEF = 0;
    for (const [id, perm] of Object.entries(map)) {
        const el = document.getElementById(id);
        if (el) {
            const has = isAd || perms.includes(perm);
            el.classList.toggle('hidden', !has);
            if (has) visibleBDEF++;
        }
    }

    // Ocultar sección completa si no hay nada
    const label = document.getElementById('nav-bdef-label');
    if (label) label.classList.toggle('hidden', visibleBDEF === 0);
}

// Reports Logic
function renderDashboardList() {
    const list = document.getElementById('dashboard-list');
    list.innerHTML = '';

    const available = [
        { name: 'Historico', icon: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>' },
        { name: 'Conceptos', icon: '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"></path></svg>' }
    ];

    available.forEach(item => {
        const hasPerm = currentUser.permissions.includes(`view_${item.name.toLowerCase()}`) || currentUser.role === 'Admin';
        if (hasPerm) {
            const card = document.createElement('div');
            card.className = 'report-card';
            card.innerHTML = `
                <div class="report-icon">
                    ${item.icon}
                </div>
                <h3>REPORTE: ${item.name.toUpperCase()}</h3>
                <button class="btn-primary" style="width: 100%;" onclick="openViewer('${item.name}')">EXPLORAR DATOS</button>
            `;
            list.appendChild(card);
        }
    });

    if (list.innerHTML === '') {
        list.innerHTML = '<p style="color: var(--text-dim); text-align: center; width: 100%;">No tienes reportes asignados.</p>';
    }
}

function openViewer(name) {
    if (name === 'BDEF') return openBDEF('index');
    document.getElementById('portalLoader').classList.remove('hidden');
    document.getElementById('view-viewer').classList.remove('hidden');
    document.getElementById('app-footer').classList.add('hidden');
    document.getElementById('viewer-title').innerText = `REPORTE: ${name.toUpperCase()}`;
    document.getElementById('viewer-last-update').innerText = '...'; 
    
    // Toggle header visibility for search reports
    const headerElements = document.querySelectorAll('#viewer-last-update, #theme-toggle-viewer-container');
    const isSpecial = ['Conceptos', 'Historico'].includes(name);
    
    const dateContainer = document.querySelector('.viewer-header > div:first-child > div:last-child');
    const themeContainer = document.querySelector('.viewer-header > div:last-child > div:first-child');
    
    if (dateContainer) dateContainer.style.display = isSpecial ? 'none' : 'flex';
    if (themeContainer) themeContainer.style.display = isSpecial ? 'none' : 'flex';

    const iframe = document.getElementById('dashboard-iframe');
    iframe.onload = () => document.getElementById('portalLoader').classList.add('hidden');
    iframe.src = `/api/dashboard/view/${name}?token=${currentToken}`;
}

function closeViewer() {
    document.getElementById('view-viewer').classList.add('hidden');
    document.getElementById('app-footer').classList.remove('hidden');
    document.getElementById('dashboard-iframe').src = '';
}

async function openBDEF(module) {
    document.getElementById('portalLoader').classList.remove('hidden');
    document.getElementById('view-viewer').classList.remove('hidden');
    document.getElementById('app-footer').classList.add('hidden');
    document.getElementById('viewer-title').innerText = `BDEF: ${module.toUpperCase()}`;
    
    const isSpecial = ['bulk', 'history'].includes(module);
    const dateContainer = document.querySelector('.viewer-header > div:first-child > div:last-child');
    const themeContainer = document.querySelector('.viewer-header > div:last-child > div:first-child');
    
    if (dateContainer) dateContainer.style.display = isSpecial ? 'none' : 'flex';
    if (themeContainer) themeContainer.style.display = isSpecial ? 'none' : 'flex';

    // Intentar obtener fecha de actualización
    const dateEl = document.getElementById('viewer-last-update');
    dateEl.innerText = 'Cargando...';
    
    try {
        const stats = await apiFetch(`/bdef/stats?module=${module}&cb=${Date.now()}`);
        if (stats && stats.last_update) {
            dateEl.innerText = stats.last_update;
        }
    } catch(e) { /* ignore */ }

    const iframe = document.getElementById('dashboard-iframe');
    iframe.onload = () => document.getElementById('portalLoader').classList.add('hidden');
    iframe.src = `/api/bdef/${module}?token=${currentToken}`;

    // Marcar como activo en el sidebar
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('onclick')?.includes(`openBDEF('${module}')`)) {
            item.classList.add('active');
        }
    });
}

// Admin Panel Logic
async function renderAdmin() {
    const pendingList = document.getElementById('pending-table').querySelector('tbody');
    const tableId = '#users-table';
    
    // Destruir instancia previa si existe
    if ($.fn.DataTable.isDataTable(tableId)) {
        $(tableId).DataTable().destroy();
    }
    
    const usersList = $(tableId).find('tbody');
    pendingList.innerHTML = '';
    usersList.empty();

    const [pending, allUsers] = await Promise.all([
        apiFetch('/admin/pending'),
        apiFetch('/admin/users')
    ]);

    pending.forEach(u => {
        const row = document.createElement('tr');
        row.innerHTML = `<td>${u.full_name}</td><td>${u.email}</td><td><button class="btn-action" onclick="approveUser(${u.id})">Aprobar</button></td>`;
        pendingList.appendChild(row);
    });

    allUsers.forEach(u => {
        const row = `
            <tr>
                <td><div style="font-weight:700;">${u.email}</div><div style="font-size:0.7rem; color:var(--text-dim);">${u.full_name}</div></td>
                <td><span class="status-badge" style="background: ${u.role === 'Admin' ? 'rgba(79, 70, 229, 0.1)' : 'var(--bg-app)'}; color: ${u.role === 'Admin' ? 'var(--primary)' : 'var(--text-dim)'};">${u.role}</span></td>
                <td>
                    <div style="display:flex; gap:0.5rem;">
                        <button class="btn-action" onclick="prepareEdit(${u.id}, '${u.email}', '${u.full_name}', '${u.role}', '${u.current_permissions}')">Editar</button>
                        <button class="btn-action danger" onclick="deleteUser(${u.id})">Eliminar</button>
                    </div>
                </td>
            </tr>
        `;
        usersList.append(row);
    });

    // Inicializar DataTable con idioma español y botones
    $(tableId).DataTable({
        dom: 'Bfrtip',
        buttons: [
            {
                extend: 'copy',
                text: '<i class="fas fa-copy"></i> Copiar',
                className: 'btn-dt-action'
            },
            {
                extend: 'excel',
                text: '<i class="fas fa-file-excel"></i> Excel',
                className: 'btn-dt-action'
            },
            {
                extend: 'csv',
                text: '<i class="fas fa-file-csv"></i> CSV',
                className: 'btn-dt-action'
            }
        ],
        pageLength: 5,
        lengthMenu: [5, 10, 25, 50],
        language: {
            "sProcessing": "Procesando...",
            "sLengthMenu": "Mostrar _MENU_ registros",
            "sZeroRecords": "No se encontraron resultados",
            "sEmptyTable": "Ningún dato disponible en esta tabla",
            "sInfo": "Mostrando registros del _START_ al _END_ de un total de _TOTAL_ registros",
            "sInfoEmpty": "Mostrando registros del 0 al 0 de un total de 0 registros",
            "sInfoFiltered": "(filtrado de un total de _MAX_ registros)",
            "sInfoPostFix": "",
            "sSearch": "Buscar:",
            "sUrl": "",
            "sInfoThousands": ",",
            "sLoadingRecords": "Cargando...",
            "oPaginate": {
                "sFirst": "Primero",
                "sLast": "Último",
                "sNext": "Siguiente",
                "sPrevious": "Anterior"
            },
            "oAria": {
                "sSortAscending": ": Activar para ordenar la columna de manera ascendente",
                "sSortDescending": ": Activar para ordenar la columna de manera descendente"
            }
        }
    });
}

let editingUserId = null;
function prepareEdit(id, email, name, role, perms) {
    editingUserId = id;
    document.getElementById('adm-new-name').value = name;
    document.getElementById('adm-new-email').value = email;
    document.getElementById('adm-new-password').placeholder = "(Vacio = Misma Contraseña)";
    document.getElementById('adm-new-role').value = (role === 'Admin' ? '1' : '2');
    
    const permList = perms ? perms.split(',') : [];
    document.getElementById('perm-hist').checked = permList.includes('view_historico');
    document.getElementById('perm-conc').checked = permList.includes('view_conceptos');
    document.getElementById('perm-bdef-index').checked = permList.includes('view_bdef_index');
    document.getElementById('perm-bdef-ind').checked = permList.includes('view_bdef_individual');
    document.getElementById('perm-bdef-bulk').checked = permList.includes('view_bdef_bulk');
    document.getElementById('perm-bdef-deuda').checked = permList.includes('view_bdef_deuda');
    document.getElementById('perm-bdef-recaudo').checked = permList.includes('view_bdef_recaudo');
    document.getElementById('perm-bdef-hist').checked = permList.includes('view_bdef_history');
    document.getElementById('perm-bdef-trans').checked = permList.includes('view_bdef_transformer');
    document.getElementById('perm-bdef-territorial').checked = permList.includes('view_bdef_territorial');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function approveUser(id) {
    await apiFetch(`/admin/approve/${id}`, 'POST');
    Swal.fire('Aprobado', '', 'success');
    renderAdmin();
}

async function deleteUser(id) {
    const res = await Swal.fire({ title: '¿Eliminar?', icon: 'warning', showCancelButton: true });
    if (res.isConfirmed) {
        await apiFetch(`/admin/delete-user/${id}`, 'DELETE');
        Swal.fire('Eliminado', '', 'success');
        renderAdmin();
    }
}

// Form Handlers
document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append('username', document.getElementById('login-email').value);
    fd.append('password', document.getElementById('login-password').value);
    
    try {
        const res = await fetch(`${API_URL}/token`, { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Login fallido');
        localStorage.setItem('token', data.access_token);
        currentToken = data.access_token;
        init();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('reset-form').onsubmit = async (e) => {
    e.preventDefault();
    const np = document.getElementById('reset-new-password').value;
    const cp = document.getElementById('reset-confirm-password').value;
    
    if (np !== cp) return Swal.fire('Error', 'Las contraseñas no coinciden', 'error');
    
    try {
        await apiFetch('/change-password', 'POST', { new_password: np });
        Swal.fire('Éxito', 'Contraseña actualizada', 'success');
        init(); // Refresh data and show dashboard
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('register-form').onsubmit = async (e) => {
    e.preventDefault();
    try {
        await apiFetch('/register', 'POST', {
            full_name: document.getElementById('reg-name').value,
            email: document.getElementById('reg-email').value,
            password: document.getElementById('reg-password').value
        });
        Swal.fire('Enviado', 'Espera aprobación', 'success');
        showView('login');
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

document.getElementById('admin-create-user-form').onsubmit = async (e) => {
    e.preventDefault();
    const perms = [];
    if (document.getElementById('perm-hist').checked) perms.push('view_historico');
    if (document.getElementById('perm-conc').checked) perms.push('view_conceptos');
    if (document.getElementById('perm-bdef-index').checked) perms.push('view_bdef_index');
    if (document.getElementById('perm-bdef-ind').checked) perms.push('view_bdef_individual');
    if (document.getElementById('perm-bdef-bulk').checked) perms.push('view_bdef_bulk');
    if (document.getElementById('perm-bdef-deuda').checked) perms.push('view_bdef_deuda');
    if (document.getElementById('perm-bdef-recaudo').checked) perms.push('view_bdef_recaudo');
    if (document.getElementById('perm-bdef-hist').checked) perms.push('view_bdef_history');
    if (document.getElementById('perm-bdef-trans').checked) perms.push('view_bdef_transformer');
    if (document.getElementById('perm-bdef-territorial').checked) perms.push('view_bdef_territorial');
    
    const body = {
        full_name: document.getElementById('adm-new-name').value,
        email: document.getElementById('adm-new-email').value,
        password: document.getElementById('adm-new-password').value,
        role_id: parseInt(document.getElementById('adm-new-role').value),
        permissions: perms
    };
    
    try {
        const url = editingUserId ? `/admin/update-user/${editingUserId}` : '/alta-usuario';
        await apiFetch(url, 'POST', body);
        Swal.fire('Listo', '', 'success');
        editingUserId = null;
        e.target.reset();
        renderAdmin();
    } catch (e) { Swal.fire('Error', e.message, 'error'); }
};

async function logout() {
    const res = await Swal.fire({
        title: '¿CERRAR SESIÓN?',
        text: "Tendrás que volver a ingresar tus credenciales para acceder.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3b82f6',
        cancelButtonColor: '#ef4444',
        confirmButtonText: 'SÍ, CERRAR SESIÓN',
        cancelButtonText: 'CANCELAR',
        background: 'rgba(15, 23, 42, 0.9)',
        color: '#f8fafc',
        backdrop: 'rgba(0,0,0,0.6) blur(8px)',
        customClass: {
            popup: 'glass-popup',
            title: 'premium-title',
            confirmButton: 'premium-confirm',
            cancelButton: 'premium-cancel'
        }
    });

    if (res.isConfirmed) {
        localStorage.removeItem('token');
        window.location.reload();
    }
}

// Run
init();
