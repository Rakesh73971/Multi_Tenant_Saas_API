// CLIENT ENVIRONMENT STATE CONFIGURATION
const CONFIG = {
    API_BASE: '/api/v1' // Uses relative URLs since frontend is served directly on the Django server
};

let state = {
    token: localStorage.getItem('saas_token') || null,
    refreshToken: localStorage.getItem('saas_refresh') || null,
    user: JSON.parse(localStorage.getItem('saas_user')) || null,
    subdomain: localStorage.getItem('saas_subdomain') || null,
    activeTab: 'dashboard',
    plans: []
};

// NOTIFICATION UTILITY
function showToast(title, desc, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Map types to Lucide icon strings
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-triangle';
    if (type === 'warning') iconName = 'alert-circle';
    
    toast.innerHTML = `
        <div class="toast-icon"><i data-lucide="${iconName}"></i></div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-desc">${desc}</div>
        </div>
    `;
    
    container.appendChild(toast);
    if (window.lucide) {
        window.lucide.createIcons();
    }
    
    // Slide in animation
    setTimeout(() => toast.classList.add('show'), 50);
    
    // Destroy node
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, 5000);
}

// CUSTOM HEADERS API CALL CLIENT WRAPPER
async function apiRequest(endpoint, options = {}) {
    const headers = new Headers(options.headers || {});
    
    // Inject Auth tokens if they exist
    if (state.token) {
        headers.append('Authorization', `Bearer ${state.token}`);
    }
    
    // Inject Tenant Context if it exists
    if (state.subdomain) {
        headers.append('X-Tenant', state.subdomain);
    }
    
    // Content type
    if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
        headers.append('Content-Type', 'application/json');
    }

    const updatedOptions = {
        ...options,
        headers
    };

    try {
        let response = await fetch(`${CONFIG.API_BASE}${endpoint}`, updatedOptions);
        
        // Handle JWT token expiry
        if (response.status === 401 && state.refreshToken) {
            const refreshed = await attemptTokenRefresh();
            if (refreshed) {
                // Re-fetch original query with updated token
                headers.set('Authorization', `Bearer ${state.token}`);
                response = await fetch(`${CONFIG.API_BASE}${endpoint}`, updatedOptions);
            } else {
                handleLogout();
                showToast('Session Expired', 'Please login to re-authenticate.', 'warning');
                return null;
            }
        }

        // Handle Redis rate limit exhaustion
        if (response.status === 429) {
            showToast(
                'Rate Limit Exceeded', 
                'Redis Sliding-Window throttle triggered. Speed limits activated. Upgrade plan to expand allocations.', 
                'warning'
            );
            return { status: 429, error: 'Rate limited' };
        }

        // Process responses
        if (response.status === 204) return true;
        const data = await response.json();
        
        if (!response.ok) {
            return { error: data, status: response.status };
        }
        return data;
    } catch (err) {
        console.error("Network or parsing failure:", err);
        showToast('Connection Error', 'Failed to communicate with SaaS API.', 'error');
        return { error: err.message };
    }
}

// ATTEMPT JWT REFRESH LOGIC
async function attemptTokenRefresh() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/auth/token/refresh/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: state.refreshToken })
        });
        
        if (response.ok) {
            const data = await response.json();
            state.token = data.access;
            localStorage.setItem('saas_token', state.token);
            if (data.refresh) {
                state.refreshToken = data.refresh;
                localStorage.setItem('saas_refresh', state.refreshToken);
            }
            return true;
        }
    } catch (e) {
        console.error("Error refreshing token", e);
    }
    return false;
}

// LOAD PUBLIC TIER SCHEMES FOR REGISTRATION LIST
async function loadPublicPlans() {
    const plans = await apiRequest('/tenants/plans/');
    if (plans && !plans.error) {
        state.plans = plans;
        renderLandingPlans();
    }
}

// RENDERS LANDING PLANS LIST
function renderLandingPlans() {
    const container = document.getElementById('landing-plans-grid');
    if (!container || !state.plans.length) return;
    
    container.innerHTML = state.plans.map(plan => {
        const isPro = plan.name.toLowerCase().includes('pro');
        return `
            <div class="glass-card price-card ${isPro ? 'popular' : ''}">
                <div class="price-header">
                    <h3>${plan.name} Plan</h3>
                    <div class="price-amount">$${parseFloat(plan.price).toFixed(0)}<span>/mo</span></div>
                </div>
                <ul class="price-features">
                    <li><i data-lucide="check"></i> Max ${plan.max_users} Users</li>
                    <li><i data-lucide="check"></i> Project Management</li>
                    <li><i data-lucide="check"></i> Rate Limit: ${plan.rate_limit_limit} / ${plan.rate_limit_period}</li>
                    <li class="${!isPro ? 'disabled' : ''}">
                        <i data-lucide="${isPro ? 'check' : 'x'}"></i> Real-time analytics charts
                    </li>
                </ul>
                <button class="btn ${isPro ? 'btn-primary' : 'btn-secondary'}" style="width: 100%;" onclick="showAuthPage('signup', ${plan.id})">
                    Choose ${plan.name}
                </button>
            </div>
        `;
    }).join('');
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// ROUTING STATE TO AUTH PORTAL
function showAuthPage(mode, selectedPlanId = null) {
    document.getElementById('landing-page').style.display = 'none';
    document.getElementById('auth-page').style.display = 'block';
    toggleAuthMode(mode, selectedPlanId);
}

// TOGGLE LOGIN VS REGISTRATION FIELDS
function toggleAuthMode(mode, selectedPlanId = null) {
    const title = document.getElementById('auth-title');
    const subtitle = document.getElementById('auth-subtitle');
    const signupFields = document.getElementById('signup-fields');
    const authBtn = document.getElementById('auth-btn');
    const switcher = document.getElementById('auth-switcher-container');
    const authForm = document.getElementById('auth-form');

    // Save selected plan dynamically to a data attribute
    if (selectedPlanId) {
        authForm.dataset.planId = selectedPlanId;
    } else {
        delete authForm.dataset.planId;
    }

    if (mode === 'signup') {
        title.textContent = 'Create Sandbox Workspace';
        subtitle.textContent = 'Initialize a fully isolated SaaS business database';
        signupFields.style.display = 'block';
        authBtn.textContent = 'Deploy SaaS Organization';
        switcher.innerHTML = `Already registered? <a onclick="toggleAuthMode('login')">Sign In Here</a>`;
        authForm.dataset.mode = 'signup';
        
        // Subdomain and tenant inputs are required for signup
        document.getElementById('tenant_name').required = true;
    } else {
        title.textContent = 'Access Workspace';
        subtitle.textContent = 'Provide tenant credentials to enter sandbox console';
        signupFields.style.display = 'none';
        authBtn.textContent = 'Access Console';
        switcher.innerHTML = `Need a new workspace? <a onclick="toggleAuthMode('signup')">Sign Up Here</a>`;
        authForm.dataset.mode = 'login';
        
        // Clear validation triggers
        document.getElementById('tenant_name').required = false;
    }
}

// SUBMIT AUTHENTICATION DETAILS TO API
async function handleAuthSubmit(event) {
    event.preventDefault();
    const form = event.target;
    const mode = form.dataset.mode;
    
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const subdomain = document.getElementById('subdomain').value.trim().toLowerCase();

    if (mode === 'signup') {
        const tenantName = document.getElementById('tenant_name').value.trim();
        const firstName = document.getElementById('first_name').value.trim();
        const lastName = document.getElementById('last_name').value.trim();
        const planId = form.dataset.planId ? parseInt(form.dataset.planId) : null;

        const response = await apiRequest('/auth/signup/', {
            method: 'POST',
            body: JSON.stringify({
                tenant_name: tenantName,
                subdomain,
                email,
                password,
                first_name: firstName,
                last_name: lastName,
                plan_id: planId
            })
        });

        if (response && !response.error) {
            state.token = response.tokens.access;
            state.refreshToken = response.tokens.refresh;
            state.user = response.user;
            state.subdomain = subdomain;
            
            saveState();
            bootstrapWorkspace();
            showToast('Workspace Created', `SaaS Workspace [${tenantName}] successfully deployed.`, 'success');
        } else {
            const errors = response ? response.error : {};
            const errMsg = Object.entries(errors).map(([key, val]) => `${key}: ${val}`).join(', ');
            showToast('Provisioning Failed', errMsg || 'Error creating tenant workspace.', 'error');
        }
    } else {
        // Log in flow
        const response = await apiRequest('/auth/login/', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        if (response && !response.error) {
            state.token = response.tokens ? response.tokens.access : response.access;
            state.refreshToken = response.tokens ? response.tokens.refresh : response.refresh;
            state.user = response.user;
            state.subdomain = subdomain; // Injected to attach workspace header

            saveState();
            bootstrapWorkspace();
            showToast('Access Granted', 'Successfully logged in to workspace sandbox.', 'success');
        } else {
            showToast('Authentication Error', 'Invalid credentials or tenant domain details.', 'error');
        }
    }
}

// LOGOUT PROCEDURE
function handleLogout() {
    state.token = null;
    state.refreshToken = null;
    state.user = null;
    state.subdomain = null;
    
    localStorage.removeItem('saas_token');
    localStorage.removeItem('saas_refresh');
    localStorage.removeItem('saas_user');
    localStorage.removeItem('saas_subdomain');

    document.getElementById('app-layout').style.display = 'none';
    document.getElementById('auth-page').style.display = 'none';
    document.getElementById('landing-page').style.display = 'block';
    
    showToast('Disconnected', 'Session credentials cleared.', 'info');
    loadPublicPlans();
}

// SAVE STATE HELPER
function saveState() {
    localStorage.setItem('saas_token', state.token);
    localStorage.setItem('saas_refresh', state.refreshToken);
    localStorage.setItem('saas_user', JSON.stringify(state.user));
    localStorage.setItem('saas_subdomain', state.subdomain);
}

// BOOTSTRAP USER WORKSPACE SESSION
function bootstrapWorkspace() {
    document.getElementById('landing-page').style.display = 'none';
    document.getElementById('auth-page').style.display = 'none';
    document.getElementById('app-layout').style.display = 'grid';

    // Set navbar badges
    document.getElementById('nav-user-email').textContent = state.user.email;
    document.getElementById('nav-user-role').textContent = state.user.role || 'Member';
    document.getElementById('nav-user-avatar').textContent = state.user.email.substring(0, 1).toUpperCase();
    
    // Subdomain visuals
    const cleanSub = state.subdomain ? `${state.subdomain}.localhost` : 'Isolated Workspace';
    document.getElementById('active-workspace-label').textContent = cleanSub;
    document.querySelectorAll('.active-subdomain-tag').forEach(el => el.textContent = cleanSub);

    // Hide members management panel for standard users (Admins only)
    const addMemberContainer = document.getElementById('add-user-container');
    const adminBillingContainer = document.getElementById('admin-tier-management-card');
    
    if (state.user.role !== 'admin') {
        if (addMemberContainer) addMemberContainer.style.display = 'none';
        if (adminBillingContainer) adminBillingContainer.style.display = 'none';
    } else {
        if (addMemberContainer) addMemberContainer.style.display = 'block';
        if (adminBillingContainer) adminBillingContainer.style.display = 'block';
    }

    // Sync menu elements
    switchTab('dashboard');
}

// TAB SWITCHER
function switchTab(tabId) {
    state.activeTab = tabId;
    
    // Manage visual links
    document.querySelectorAll('.menu-item').forEach(item => item.classList.remove('active'));
    const activeLink = document.getElementById(`menu-${tabId}`);
    if (activeLink) activeLink.classList.add('active');

    // Manage panel views
    document.querySelectorAll('.view-panel').forEach(panel => panel.classList.remove('active'));
    const activePanel = document.getElementById(`panel-${tabId}`);
    if (activePanel) activePanel.classList.add('active');

    // Load data for selected view
    if (tabId === 'dashboard') loadProjects();
    if (tabId === 'analytics') loadAnalytics();
    if (tabId === 'users') loadTeamUsers();
    if (tabId === 'billing') loadBillingPortal();
}

// LOAD SCOPED PROJECTS FROM DRF
async function loadProjects() {
    const grid = document.getElementById('dashboard-projects-grid');
    if (!grid) return;
    grid.innerHTML = '<div style="color: var(--text-muted);">Fetching scoped projects...</div>';

    const projects = await apiRequest('/projects/');
    if (projects && !projects.error) {
        if (projects.length === 0) {
            grid.innerHTML = `
                <div class="glass-card" style="grid-column: 1/-1; padding: 40px; text-align: center; border-style: dashed;">
                    <i data-lucide="folder-open" style="width: 48px; height: 48px; margin: 0 auto 12px auto; color: var(--text-muted); opacity: 0.5;"></i>
                    <h4>No Projects Found</h4>
                    <p style="color: var(--text-muted); font-size: 13px; margin-top: 4px;">Click 'Register New Project' to spawn isolated database rows.</p>
                </div>
            `;
        } else {
            grid.innerHTML = projects.map(proj => `
                <div class="glass-card project-card">
                    <div>
                        <div class="project-card-header">
                            <div class="project-title">${proj.name}</div>
                            <button class="project-action-btn" onclick="deleteProject(${proj.id})">
                                <i data-lucide="trash-2" style="width: 16px;"></i>
                            </button>
                        </div>
                        <div class="project-desc">${proj.description || ''}</div>
                    </div>
                    <div class="project-meta">
                        <span>Ref: #${proj.id}</span>
                        <span>Created: ${new Date(proj.created_at).toLocaleDateString()}</span>
                    </div>
                </div>
            `).join('');
        }
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } else if (projects && projects.status === 429) {
        grid.innerHTML = '<div style="color: #ef4444;">API Request throttled by server.</div>';
    }
}

// REGISTER NEW PROJECT MODAL TRIGGERS
function openCreateProjectModal() {
    document.getElementById('modal-project').classList.add('open');
}

function closeProjectModal() {
    document.getElementById('modal-project').classList.remove('open');
    document.getElementById('project-form').reset();
}

async function handleProjectSubmit(event) {
    event.preventDefault();
    const name = document.getElementById('project_name').value.trim();
    const desc = document.getElementById('project_desc').value.trim();

    const res = await apiRequest('/projects/', {
        method: 'POST',
        body: JSON.stringify({ name, description: desc })
    });

    if (res && !res.error) {
        showToast('Project Registered', `Project [${name}] created in database.`, 'success');
        closeProjectModal();
        loadProjects();
    } else {
        showToast('Failed to create', res && res.error ? JSON.stringify(res.error) : 'Unknown backend validation issue', 'error');
    }
}

// DELETE PROJECT
async function deleteProject(id) {
    if (confirm('Delete project row? This cannot be undone.')) {
        const res = await apiRequest(`/projects/${id}/`, { method: 'DELETE' });
        if (res === true || (res && !res.error)) {
            showToast('Project Deleted', 'Project successfully purged from tenant database.', 'success');
            loadProjects();
        } else {
            showToast('Delete Blocked', 'Error removing requested project resources.', 'error');
        }
    }
}

// TRIGGER RATE LIMIT SPAM TEST TOOL
async function triggerRateLimitSpam() {
    showToast('Stress Test Initiated', 'Firing 15 consecutive API queries in parallel...', 'info');
    
    const promises = Array.from({ length: 15 }).map(() => apiRequest('/projects/'));
    const results = await Promise.all(promises);
    
    // Audit how many responses returned 429 rate limit statuses
    const rateLimitedCount = results.filter(r => r && r.status === 429).length;
    
    if (rateLimitedCount > 0) {
        showToast(
            'Limiter Active', 
            `Fired 15 calls. ${rateLimitedCount} requests blocked with 429 status code.`, 
            'warning'
        );
    } else {
        showToast('Spam Completed', '15 queries succeeded. Limit threshold not reached.', 'success');
    }
    loadProjects();
}

// LOAD WORKSPACE MEMBERS LIST
async function loadTeamUsers() {
    const tableBody = document.getElementById('users-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '<tr><td colspan="4" style="color: var(--text-muted);">Syncing workspace users...</td></tr>';

    const members = await apiRequest('/users/');
    if (members && !members.error) {
        tableBody.innerHTML = members.map(m => `
            <tr>
                <td><strong>${m.first_name || ''} ${m.last_name || ''}</strong></td>
                <td>${m.email}</td>
                <td><span class="badge badge-${m.role === 'admin' ? 'admin' : 'member'}">${m.role}</span></td>
                <td>${new Date(m.created_at).toLocaleDateString()}</td>
            </tr>
        `).join('');
    } else {
        tableBody.innerHTML = `<tr><td colspan="4" style="color: #f87171;">Authorization error fetching workspace users.</td></tr>`;
    }
}

// CREATE NEW TEAM MEMBER WORKSPACE INVITATION
async function handleInviteUser(event) {
    event.preventDefault();
    const email = document.getElementById('invite_email').value.trim();
    const fName = document.getElementById('invite_first_name').value.trim();
    const lName = document.getElementById('invite_last_name').value.trim();
    const password = document.getElementById('invite_password').value;

    const res = await apiRequest('/users/', {
        method: 'POST',
        body: JSON.stringify({
            email,
            first_name: fName,
            last_name: lName,
            password
        })
    });

    if (res && !res.error) {
        showToast('User Registered', `Account created for ${email}.`, 'success');
        document.getElementById('invite-user-form').reset();
        loadTeamUsers();
    } else {
        showToast('Invite Blocked', res && res.error ? JSON.stringify(res.error) : 'Verify validations.', 'error');
    }
}

// LOAD SUBSCRIPTION PORTAL INFORMATION
async function loadBillingPortal() {
    const currentPlanEl = document.getElementById('billing-current-plan');
    const currentStatusEl = document.getElementById('billing-current-status');
    
    // Get tenant info and active subscription
    const tenantInfo = await apiRequest('/tenants/info/my-tenant/');
    if (tenantInfo && !tenantInfo.error) {
        const sub = tenantInfo.subscription;
        if (sub && sub.plan) {
            currentPlanEl.textContent = `${sub.plan.name} Tier`;
            currentStatusEl.textContent = `Status: ${sub.status.toUpperCase()}`;
            
            // Style badge
            if (sub.plan.name.toLowerCase().includes('pro')) {
                currentPlanEl.className = 'stat-value gradient-text-pink';
            } else {
                currentPlanEl.className = 'stat-value gradient-text';
            }
        } else {
            currentPlanEl.textContent = 'None';
            currentStatusEl.textContent = 'Status: Inactive';
        }
    }

    // Load plans selection options
    const plansContainer = document.getElementById('billing-plans-container');
    if (plansContainer) {
        plansContainer.innerHTML = '<div style="color: var(--text-muted);">Syncing package catalog...</div>';
        
        // Retrieve available plans
        const plans = await apiRequest('/tenants/plans/');
        if (plans && !plans.error) {
            plansContainer.innerHTML = plans.map(p => {
                const isActive = tenantInfo.subscription && tenantInfo.subscription.plan && tenantInfo.subscription.plan.id === p.id;
                return `
                    <div class="glass-card" style="flex: 1; min-width: 200px; padding: 20px; border-color: ${isActive ? 'var(--accent-purple)' : 'var(--border-glass)'};">
                        <h4 style="font-size: 15px; text-transform: uppercase;">${p.name} Package</h4>
                        <div style="font-size: 20px; font-weight: 800; margin: 10px 0;">$${parseFloat(p.price).toFixed(0)}<span style="font-size: 11px; color: var(--text-muted);">/mo</span></div>
                        <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 16px;">
                            Speed Limit: ${p.rate_limit_limit} / ${p.rate_limit_period}
                        </p>
                        ${isActive ? 
                            `<span class="badge badge-admin" style="display: block; text-align: center; font-size: 10px;">ACTIVE SYSTEM TIER</span>` : 
                            `<button class="btn btn-primary" style="width: 100%; padding: 6px 12px; font-size: 11px;" onclick="upgradeSubscription(${p.id})">Subscribe Tier</button>`
                        }
                    </div>
                `;
            }).join('');
        }
    }

    // Sync Invoice History
    const historyBody = document.getElementById('billing-history-body');
    if (historyBody) {
        historyBody.innerHTML = '<tr><td colspan="4" style="color: var(--text-muted);">Fetching receipt transactions...</td></tr>';
        
        const invoices = await apiRequest('/billing/invoices/');
        if (invoices && !invoices.error) {
            if (invoices.length === 0) {
                historyBody.innerHTML = '<tr><td colspan="4" style="color: var(--text-muted); text-align: center;">No invoices found.</td></tr>';
            } else {
                historyBody.innerHTML = invoices.map(inv => `
                    <tr>
                        <td><code>${inv.stripe_invoice_id}</code></td>
                        <td>${new Date(inv.billing_date).toLocaleDateString()}</td>
                        <td><strong>$${parseFloat(inv.amount).toFixed(2)}</strong></td>
                        <td><span class="badge" style="background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.3); color: #4ade80;">${inv.status}</span></td>
                    </tr>
                `).join('');
            }
        } else {
            historyBody.innerHTML = '<tr><td colspan="4" style="color: #f87171;">Error fetching transactions.</td></tr>';
        }
    }
}

// UPGRADE SUBSCRIPTION
async function upgradeSubscription(planId) {
    showToast('Initiating Purchase', 'Opening secure payment pipeline...', 'info');
    
    const res = await apiRequest('/billing/subscribe/', {
        method: 'POST',
        body: JSON.stringify({ plan_id: planId })
    });

    if (res && !res.error) {
        if (res.checkout_url) {
            showToast('Stripe Pipeline', 'Redirecting to mock Stripe checkout gateway...', 'success');
            // Simulating checkout page redirect
            setTimeout(() => {
                window.location.href = res.checkout_url;
            }, 1000);
        } else {
            // Mock instant checkout completed
            showToast('Subscription Updated', 'Workspace permissions refreshed instantly.', 'success');
            loadBillingPortal();
        }
    } else {
        showToast('Transaction Interrupted', res && res.error ? JSON.stringify(res.error) : 'Verify billing configuration.', 'error');
    }
}

// LOAD PREMIUM ANALYTICS VIEW
async function loadAnalytics() {
    const container = document.getElementById('analytics-content-container');
    if (!container) return;
    container.innerHTML = '<div style="color: var(--text-muted); padding: 30px;">Syncing premium charts...</div>';

    const analytics = await apiRequest('/projects/analytics/');
    if (analytics && !analytics.error) {
        container.innerHTML = `
            <div class="glass-card" style="padding: 30px; display: grid; grid-template-columns: 1fr 1fr; gap: 30px;">
                <div class="glass-card stat-card" style="background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-label">Active Projects Registry Count</div>
                    <div class="stat-value gradient-text-pink">${analytics.data.active_projects}</div>
                    <div class="stat-sub">Scoping status: Isolated</div>
                </div>
                <div class="glass-card stat-card" style="background: rgba(255, 255, 255, 0.02);">
                    <div class="stat-label">Performance Dashboard Score</div>
                    <div class="stat-value" style="color: var(--accent-cyan);">${analytics.data.performance_score}%</div>
                    <div class="stat-sub">Real-time processing latency: <12ms</div>
                </div>
                <div class="glass-card" style="grid-column: 1 / -1; padding: 24px;">
                    <h4 style="margin-bottom: 12px;"><i data-lucide="shield" style="width: 16px; vertical-align: middle; margin-right: 4px; color: var(--accent-purple);"></i> Workspace Isolation Verification</h4>
                    <p style="color: var(--text-muted); font-size: 13px; line-height: 1.5;">
                        Your workspace is executing queries under strict multi-tenant constraints. Database managers isolate SQL queries at the thread execution boundary. All data is isolated within the <code>${state.subdomain}</code> context space.
                    </p>
                </div>
            </div>
        `;
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } else if (analytics && analytics.status === 403) {
        // Free subscription gatekeeping
        container.innerHTML = `
            <div class="locked-overlay">
                <div class="locked-icon-box"><i data-lucide="lock" style="width: 28px; height: 28px;"></i></div>
                <h3>Unlock Premium Analytics</h3>
                <p>Real-time analytics graphs, database scoping validations, and server execution performance indices are locked. Upgrade to the Pro Plan to explore these features.</p>
                <button class="btn btn-cyan" onclick="switchTab('billing')">
                    Upgrade Sandbox to Pro
                    <i data-lucide="chevron-right" style="width: 16px;"></i>
                </button>
            </div>
        `;
        if (window.lucide) {
            window.lucide.createIcons();
        }
    } else {
        container.innerHTML = '<div style="color: #f87171; padding: 30px;">Error reloading analytics.</div>';
    }
}

// SYSTEM INITIALIZER
function init() {
    if (window.lucide) {
        window.lucide.createIcons();
    }
    if (state.token && state.user) {
        bootstrapWorkspace();
    } else {
        loadPublicPlans();
    }
}

// RUN SYSTEM BOOT
window.addEventListener('DOMContentLoaded', init);
