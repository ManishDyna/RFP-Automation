// Sample user data
let users = [
    {
        id: 1,
        name: 'John Doe',
        email: 'john.doe@example.com',
        role: 'Administrator',
        status: 'Active',
        joinDate: '2024-01-15',
        avatar: 'https://images.pexels.com/photos/2379004/pexels-photo-2379004.jpeg?auto=compress&cs=tinysrgb&w=150'
    },
    {
        id: 2,
        name: 'Jane Smith',
        email: 'jane.smith@example.com',
        role: 'Editor',
        status: 'Active',
        joinDate: '2024-01-10',
        avatar: 'https://images.pexels.com/photos/1181686/pexels-photo-1181686.jpeg?auto=compress&cs=tinysrgb&w=150'
    },
    {
        id: 3,
        name: 'Mike Johnson',
        email: 'mike.johnson@example.com',
        role: 'User',
        status: 'Inactive',
        joinDate: '2024-01-05',
        avatar: 'https://images.pexels.com/photos/1043471/pexels-photo-1043471.jpeg?auto=compress&cs=tinysrgb&w=150'
    },
    {
        id: 4,
        name: 'Sarah Wilson',
        email: 'sarah.wilson@example.com',
        role: 'Editor',
        status: 'Active',
        joinDate: '2024-01-20',
        avatar: 'https://images.pexels.com/photos/1181424/pexels-photo-1181424.jpeg?auto=compress&cs=tinysrgb&w=150'
    }
];

let editingUserId = null;

// Check if user is logged in on page load
document.addEventListener('DOMContentLoaded', function() {
    const isLoggedIn = localStorage.getItem('isLoggedIn');
    if (isLoggedIn === 'true') {
        showDashboard();
        const userEmail = localStorage.getItem('userEmail');
        if (userEmail) {
            document.getElementById('userName').textContent = userEmail;
        }
    } else {
        // showLogin();
    }
    
    initializeEventListeners();
    // renderUsers();
});

function initializeEventListeners() {
    // Login form handler
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Logout button handler
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async function() {
            try {
                const res = await fetch('/logout', { method: 'POST' });
                if (res.ok) {
                    const j = await res.json();
                    window.location.href = j.redirect || '/login';
                }
            } catch (e) {}
        });
    }
    
    // Navigation handlers
    const navLinks = document.querySelectorAll('[data-tab]');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            showTab(tabName);
            
            // Update active nav link
            document.querySelectorAll('.sidebar .nav-link').forEach(nav => {
                nav.classList.remove('active');
            });
            if (this.classList.contains('nav-link')) {
                this.classList.add('active');
            }
        });
    });
    
    // Schedule Automation button opens modal (supports new id and old data-tab)
    const scheduleBtn = document.getElementById('scheduleAutomationBtn') || document.querySelector('[data-tab="scheduleAutomation"]');
    if (scheduleBtn) {
        scheduleBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Show loader
            const btnText = scheduleBtn.querySelector('.btn-text');
            const btnLoading = scheduleBtn.querySelector('.btn-loading');
            if (btnText && btnLoading) {
                btnText.classList.add('d-none');
                btnLoading.classList.remove('d-none');
                scheduleBtn.disabled = true;
            }
            
            const modalEl = document.getElementById('scheduleAutomationModal');
            if (!modalEl) {
                // Hide loader if modal not found
                if (btnText && btnLoading) {
                    btnText.classList.remove('d-none');
                    btnLoading.classList.add('d-none');
                    scheduleBtn.disabled = false;
                }
                return;
            }
            const modal = new bootstrap.Modal(modalEl);
            const form = document.getElementById('scheduleAutomationForm');
            if (form) form.reset();
            const alertBox = document.getElementById('scheduleAlert');
            if (alertBox) alertBox.style.display = 'none';
            // set default start time to now rounded to minutes
            const dt = new Date();
            dt.setSeconds(0, 0);
            const pad = n => String(n).padStart(2, '0');
            const local = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
            const startInput = document.getElementById('scheduleStartTime');
            if (startInput && !startInput.value) startInput.value = local;
            // Prefill from latest saved schedule
            prefillLatestSchedule().finally(() => {
                // Hide loader
                if (btnText && btnLoading) {
                    btnText.classList.remove('d-none');
                    btnLoading.classList.add('d-none');
                    scheduleBtn.disabled = false;
                }
                modal.show();
            });
        });
    }

    // Save schedule handler
    const saveScheduleBtn = document.getElementById('saveScheduleBtn');
    if (saveScheduleBtn) {
        saveScheduleBtn.addEventListener('click', saveSchedule);
    }

    // User search functionality
    const userSearch = document.getElementById('userSearch');
    if (userSearch) {
        userSearch.addEventListener('input', filterUsers);
    }
    
    // User form handler
    const userForm = document.getElementById('userForm');
    if (userForm) {
        userForm.addEventListener('submit', function(e) {
            e.preventDefault();
            // saveUser();
        });
        }
    // Automation button handler with company selection
    const runAutomationBtn = document.getElementById('runAutomationBtn');
    const downloadCompanyModalEl = document.getElementById('downloadRfpCompanyModal');
    const downloadCompanySelect = document.getElementById('downloadCompanySelect');
    const downloadCompanyConfirmBtn = document.getElementById('downloadCompanyConfirmBtn');
    let downloadCompanyModalInstance = null;
    if (downloadCompanyModalEl && typeof bootstrap !== 'undefined') {
        downloadCompanyModalInstance = new bootstrap.Modal(downloadCompanyModalEl, {backdrop: 'static'});
    }
    if (downloadCompanySelect) {
        downloadCompanySelect.addEventListener('change', () => downloadCompanySelect.classList.remove('is-invalid'));
    }
    ['submitRfpCompanySelect', 'declineRfpCompanySelect'].forEach(id => {
        const selectEl = document.getElementById(id);
        if (selectEl) {
            selectEl.addEventListener('change', () => selectEl.classList.remove('is-invalid'));
        }
    });
    if (runAutomationBtn) {
        runAutomationBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (!downloadCompanyModalInstance) {
                showAlert('Unable to open company selector. Please refresh the page.', 'danger');
                return;
            }
            if (downloadCompanySelect) {
                downloadCompanySelect.value = '';
                downloadCompanySelect.classList.remove('is-invalid');
            }
            downloadCompanyModalInstance.show();
        });
    }
    if (downloadCompanyConfirmBtn) {
        downloadCompanyConfirmBtn.addEventListener('click', () => {
            const selectedCompany = downloadCompanySelect?.value?.trim();
            if (!selectedCompany) {
                if (downloadCompanySelect) {
                    downloadCompanySelect.classList.add('is-invalid');
                    downloadCompanySelect.focus();
                }
                return;
            }
            downloadCompanySelect.classList.remove('is-invalid');
            if (downloadCompanyModalInstance) {
                downloadCompanyModalInstance.hide();
            }
            runAutomation(selectedCompany);
        });
    }

    // Sync Portal Data button handler (Dashboard — scoped to visible RFPs only)
    const syncPortalBtn = document.getElementById('syncPortalBtn');
    if (syncPortalBtn) {
        syncPortalBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const rfpIds = window.DASHBOARD_RFP_IDS || [];
            if (rfpIds.length === 0) {
                showAlert('No RFPs to sync on the dashboard.', 'warning');
                return;
            }
            const ok = window.confirm('Sync portal data for dashboard RFPs only?');
            if (!ok) return;
            runSyncPortal(rfpIds, 'syncPortalBtn');
        });
    }

    // Sync ALL Portal Data button handler (RFP Insights page — full sync)
    const syncAllPortalBtn = document.getElementById('syncAllPortalBtn');
    if (syncAllPortalBtn) {
        syncAllPortalBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const ok = window.confirm('Sync portal data for ALL RFPs? This may take longer.');
            if (!ok) return;
            runSyncPortal([], 'syncAllPortalBtn');
        });
    }

    // Download All RFPs button handler
    const downloadAllRfpsBtn = document.getElementById('downloadAllRfpsBtn');
    if (downloadAllRfpsBtn) {
        downloadAllRfpsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            // Show confirmation modal
            const modalEl = document.getElementById('downloadAllRfpsModal');
            if (!modalEl) {
                console.error('❌ Download All RFPs modal not found');
                return;
            }
            try {
                const modal = new bootstrap.Modal(modalEl);
                const alertBox = document.getElementById('downloadAllRfpsAlert');
                if (alertBox) {
                    alertBox.style.display = 'none';
                    alertBox.className = 'alert alert-dismissible fade mt-3';
                }
                modal.show();
            } catch (error) {
                console.error('❌ Error showing modal:', error);
            }
        });
    }

    // Confirm Download All RFPs button handler
    const confirmDownloadAllRfpsBtn = document.getElementById('confirmDownloadAllRfpsBtn');
    if (confirmDownloadAllRfpsBtn) {
        confirmDownloadAllRfpsBtn.addEventListener('click', function(e) {
            e.preventDefault();
            runDownloadAllRfps();
        });
    }
    
    // Profile form handler
    const profileForm = document.getElementById('profileForm');
   
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileUpdate);
    }
    
    // Profile reset button handler
    const resetFormBtn = document.getElementById('resetFormBtn');
    if (resetFormBtn) {
        resetFormBtn.addEventListener('click', resetProfileForm);
    }
    
    // Password confirmation validation
    const newPasswordInput = document.getElementById('newPassword');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    if (newPasswordInput && confirmPasswordInput) {
        confirmPasswordInput.addEventListener('input', validatePasswordMatch);
    }

    // Change SAP Password button opens modal
    const changeSapBtn = document.getElementById('changeSapPasswordBtn');
    
    if (changeSapBtn) {
        changeSapBtn.addEventListener('click', function() {
            const modalEl = document.getElementById('sapPasswordModal');
            if (!modalEl) return;
            const modal = new bootstrap.Modal(modalEl);
            // reset form and alerts on open
            const form = document.getElementById('sapPasswordForm');
            if (form) form.reset();
            const alertBox = document.getElementById('sapPasswordAlert');
            if (alertBox) alertBox.style.display = 'none';
            modal.show();
        });
    }

    // Save SAP password button handler
    const saveSapPasswordBtn = document.getElementById('saveSapPasswordBtn');
    if (saveSapPasswordBtn) {
        saveSapPasswordBtn.addEventListener('click', submitSapPasswordChange);
    }

    // Submit RFP button opens modal
    const submitRfpBtn = document.getElementById('submitRfpBtn');
    if (submitRfpBtn) {
        console.log('✅ Submit RFP button found, adding event listener');
        submitRfpBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Submit RFP button clicked');
            const modalEl = document.getElementById('submitRfpModal');
            if (!modalEl) {
                console.error('❌ Submit RFP modal not found');
                return;
            }
            console.log('✅ Modal element found, creating bootstrap modal');
            try {
                const modal = new bootstrap.Modal(modalEl);
                const form = document.getElementById('submitRfpForm');
                if (form) form.reset();
                const alertBox = document.getElementById('submitRfpAlert');
                if (alertBox) alertBox.style.display = 'none';
                const fileInfo = document.getElementById('submitRfpFileInfo');
                if (fileInfo) fileInfo.classList.add('d-none');
                modal.show();
                console.log('✅ Modal shown');
            } catch (error) {
                console.error('❌ Error showing modal:', error);
            }
        });
    } else {
        console.error('❌ Submit RFP button not found');
    }

    // Decline RFP button opens modal
    const declineRfpBtn = document.getElementById('declineRfpBtn');
    if (declineRfpBtn) {
        console.log('✅ Decline RFP button found, adding event listener');
        declineRfpBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Decline RFP button clicked');
            const modalEl = document.getElementById('declineRfpModal');
            if (!modalEl) {
                console.error('❌ Decline RFP modal not found');
                return;
            }
            console.log('✅ Modal element found, creating bootstrap modal');
            try {
                const modal = new bootstrap.Modal(modalEl);
                const form = document.getElementById('declineRfpForm');
                if (form) form.reset();
                const alertBox = document.getElementById('declineRfpAlert');
                if (alertBox) alertBox.style.display = 'none';
                modal.show();
                console.log('✅ Modal shown');
            } catch (error) {
                console.error('❌ Error showing modal:', error);
            }
        });
    } else {
        console.error('❌ Decline RFP button not found');
    }

    // Submit RFP submit button handler
    const submitRfpSubmitBtn = document.getElementById('submitRfpSubmitBtn');
    if (submitRfpSubmitBtn) {
        submitRfpSubmitBtn.addEventListener('click', handleSubmitRfp);
    }

    // Decline RFP submit button handler
    const declineRfpSubmitBtn = document.getElementById('declineRfpSubmitBtn');
    if (declineRfpSubmitBtn) {
        declineRfpSubmitBtn.addEventListener('click', handleDeclineRfp);
    }



    // File input change handler - enable/disable Submit button based on file selection
    const excelFileInput = document.getElementById('excelFile');
    if (excelFileInput) {
        excelFileInput.addEventListener('change', function(e) {
            const fileInfo = document.getElementById('submitRfpFileInfo');
            const fileName = document.getElementById('submitRfpFileName');
            const submitBtn = document.getElementById('submitRfpSubmitBtn');
            const file = e.target.files && e.target.files[0];

            if (file) {
                const ext = file.name.split('.').pop().toLowerCase();
                const validExts = ['xls', 'xlsx'];
                if (!validExts.includes(ext)) {
                    // Wrong file type — keep button disabled, show error
                    if (fileName) fileName.textContent = `❌ Invalid file type: .${ext} — only .xls or .xlsx allowed`;
                    if (fileInfo) {
                        fileInfo.classList.remove('d-none', 'alert-info');
                        fileInfo.classList.add('alert-danger');
                    }
                    if (submitBtn) {
                        submitBtn.disabled = true;
                        submitBtn.title = 'Invalid file type. Upload a .xls or .xlsx file.';
                    }
                    e.target.value = '';
                } else {
                    const sizeKb = (file.size / 1024).toFixed(1);
                    if (fileName) fileName.textContent = `✅ ${file.name} (${sizeKb} KB) — will upload to rfp-upload-file`;
                    if (fileInfo) {
                        fileInfo.classList.remove('d-none', 'alert-danger');
                        fileInfo.classList.add('alert-info');
                    }
                    // Enable Submit button only when valid Excel is selected
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.title = '';
                    }
                }
            } else {
                // No file selected — disable button
                if (fileInfo) fileInfo.classList.add('d-none');
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.title = 'Please upload an Excel file to enable submission';
                }
            }
        });
    }

    // Also reset Submit button when the modal is hidden (so it resets for next use)
    const submitRfpModalEl = document.getElementById('submitRfpModal');
    if (submitRfpModalEl) {
        submitRfpModalEl.addEventListener('hidden.bs.modal', function () {
            const submitBtn = document.getElementById('submitRfpSubmitBtn');
            const excelInput = document.getElementById('excelFile');
            const fileInfo = document.getElementById('submitRfpFileInfo');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.title = 'Please upload an Excel file to enable submission';
            }
            if (excelInput) excelInput.value = '';
            if (fileInfo) fileInfo.classList.add('d-none');
        });
    }
}


function handleLogin(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    
    if (!email || !password) {
        showAlert('Please fill in all fields', 'danger');
        return;
    }
    
    // Simulate login (accept any email/password combination)
    localStorage.setItem('isLoggedIn', 'true');
    localStorage.setItem('userEmail', email);
    
    // Show success message
    showAlert('Login successful! Redirecting...', 'success');
    
    // Redirect to dashboard after brief delay
    setTimeout(() => {
        showDashboard();
        document.getElementById('userName').textContent = email;
    }, (window.APP_CONFIG && APP_CONFIG.LOGIN_REDIRECT_DELAY_MS) || 1000);
}

function handleLogout() {
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('userEmail');
    showAlert('Logged out successfully', 'info');
    setTimeout(() => {
        // showLogin();
    }, (window.APP_CONFIG && APP_CONFIG.LOGIN_REDIRECT_DELAY_MS) || 1000);
}

function showDashboard() {
    document.getElementById('loginPage').classList.add('d-none');
    document.getElementById('dashboard').classList.remove('d-none');
}

function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.add('d-none');
    });
    
    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.remove('d-none');
    }
}

function showAlert(message, type = 'info') {
    // Remove existing alerts
    const existingAlert = document.querySelector('.alert');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // Create new alert
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Insert alert at the top of the active container
    const activeContainer = document.querySelector('#loginPage:not(.d-none), #dashboard:not(.d-none)');
    if (activeContainer) {
        activeContainer.insertBefore(alert, activeContainer.firstChild);
    }
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert) {
            alert.remove();
        }
    }, (window.APP_CONFIG && APP_CONFIG.ALERT_DISMISS_MS) || 5000);
}



function getRoleBadgeClass(role) {
    switch (role) {
        case 'Administrator':
            return 'bg-danger';
        case 'Editor':
            return 'bg-warning text-dark';
        case 'User':
            return 'bg-secondary';
        default:
            return 'bg-secondary';
    }
}

function filterUsers() {
    const searchTerm = document.getElementById('userSearch').value.toLowerCase();
    const filteredUsers = users.filter(user =>
        user.name.toLowerCase().includes(searchTerm) ||
        user.email.toLowerCase().includes(searchTerm) ||
        user.role.toLowerCase().includes(searchTerm)
    );
    
    renderFilteredUsers(filteredUsers);
}

function renderFilteredUsers(filteredUsers) {
    const tbody = document.getElementById('userTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    filteredUsers.forEach(user => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <div class="d-flex align-items-center">
                    <img src="${user.avatar}" alt="${user.name}" class="rounded-circle me-3" width="40" height="40">
                    <div>
                        <h6 class="mb-0">${user.name}</h6>
                    </div>
                </div>
            </td>
            <td>${user.email}</td>
            <td>
                <span class="badge ${getRoleBadgeClass(user.role)}">
                    ${user.role}
                </span>
            </td>
            <td>
                <span class="badge ${user.status === 'Active' ? 'bg-success' : 'bg-secondary'}">
                    ${user.status}
                </span>
            </td>
            <td>${new Date(user.joinDate).toLocaleDateString()}</td>
            <td>
                <div class="btn-group" role="group">
                    <button class="btn btn-sm btn-outline-primary" onclick="editUser(${user.id})" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteUser(${user.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function openUserModal(userId = null) {
    editingUserId = userId;
    const modal = document.getElementById('userModal');
    const modalTitle = document.getElementById('userModalTitle');
    const form = document.getElementById('userForm');
    
    if (userId) {
        // Edit mode
        const user = users.find(u => u.id === userId);
        if (user) {
            modalTitle.textContent = 'Edit User';
            document.getElementById('userId').value = user.id;
            document.getElementById('userNameInput').value = user.name;
            document.getElementById('userEmailInput').value = user.email;
            document.getElementById('userRoleInput').value = user.role;
            document.getElementById('userStatusInput').value = user.status;
        }
    } else {
        // Add mode
        modalTitle.textContent = 'Add New User';
        form.reset();
        document.getElementById('userId').value = '';
    }
}

function editUser(userId) {
    openUserModal(userId);
    const modal = new bootstrap.Modal(document.getElementById('userModal'));
    modal.show();
}

function deleteUser(userId) {
    if (confirm('Are you sure you want to delete this user?')) {
        users = users.filter(user => user.id !== userId);
        // renderUsers();
        showAlert('User deleted successfully', 'success');
    }
}

// function saveUser() {
//     const form = document.getElementById('userForm');
//     const formData = new FormData(form);
    
//     const userData = {
//         name: document.getElementById('userNameInput').value,
//         email: document.getElementById('userEmailInput').value,
//         role: document.getElementById('userRoleInput').value,
//         // status: document.getElementById('userStatusInput').value
//     };
    
//     // Basic validation
//     if (!userData.name || !userData.email || !userData.role || !userData.status) {
//         showAlert('Please fill in all fields', 'danger');
//         return;
//     }
    
//     // Email validation
//     const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
//     if (!emailRegex.test(userData.email)) {
//         showAlert('Please enter a valid email address', 'danger');
//         return;
//     }
    
//     if (editingUserId) {
//         // Update existing user
//         const userIndex = users.findIndex(u => u.id === editingUserId);
//         if (userIndex !== -1) {
//             users[userIndex] = {
//                 ...users[userIndex],
//                 ...userData
//             };
//             showAlert('User updated successfully', 'success');
//         }
//     } else {
//         // Add new user
//         const newUser = {
//             id: Math.max(...users.map(u => u.id)) + 1,
//             ...userData,
//             joinDate: new Date().toISOString().split('T')[0],
//             avatar: getRandomAvatar()
//         };
//         users.push(newUser);
//         showAlert('User added successfully', 'success');
//     }
    
//     // renderUsers();
    
//     // Close modal
//     const modal = bootstrap.Modal.getInstance(document.getElementById('userModal'));
//     modal.hide();
    
//     // Reset form
//     form.reset();
//     editingUserId = null;
// }

function getRandomAvatar() {
    const avatars = [
        'https://images.pexels.com/photos/2379004/pexels-photo-2379004.jpeg?auto=compress&cs=tinysrgb&w=150',
        'https://images.pexels.com/photos/1181686/pexels-photo-1181686.jpeg?auto=compress&cs=tinysrgb&w=150',
        'https://images.pexels.com/photos/1043471/pexels-photo-1043471.jpeg?auto=compress&cs=tinysrgb&w=150',
        'https://images.pexels.com/photos/1181424/pexels-photo-1181424.jpeg?auto=compress&cs=tinysrgb&w=150',
        'https://images.pexels.com/photos/614810/pexels-photo-614810.jpeg?auto=compress&cs=tinysrgb&w=150',
        'https://images.pexels.com/photos/1239291/pexels-photo-1239291.jpeg?auto=compress&cs=tinysrgb&w=150'
    ];
    return avatars[Math.floor(Math.random() * avatars.length)];
}

// Mobile sidebar toggle (optional enhancement)
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('show');
}

// Add click outside to close sidebar on mobile
document.addEventListener('click', function(event) {
    const sidebar = document.querySelector('.sidebar');
    const isClickInsideSidebar = sidebar.contains(event.target);
    
    if (!isClickInsideSidebar && window.innerWidth <= 768) {
        sidebar.classList.remove('show');
    }
});

// Handle window resize
window.addEventListener('resize', function() {
    const sidebar = document.querySelector('.sidebar');
    if (window.innerWidth > 768) {
        sidebar.classList.remove('show');
    }
});

// Smooth scrolling for internal links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add loading states to buttons
function addLoadingState(button) {
    const originalText = button.innerHTML;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    button.disabled = true;
    
    setTimeout(() => {
        button.innerHTML = originalText;
        button.disabled = false;
    }, 1000);
}

// Enhanced form validation
function validateForm(formElement) {
    const inputs = formElement.querySelectorAll('input[required], select[required]');
    let isValid = true;
    
    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
        }
    });
    
    return isValid;
}

// Real-time form validation
document.addEventListener('input', function(e) {
    if (e.target.hasAttribute('required')) {
        if (e.target.value.trim()) {
            e.target.classList.remove('is-invalid');
            e.target.classList.add('is-valid');
        } else {
            e.target.classList.remove('is-valid');
            e.target.classList.add('is-invalid');
        }
    }
});

// Initialize tooltips (if needed)
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-tooltip]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Run Automation function
async function runAutomation(selectedCompany) {
    // Get DOM elements with proper existence checks
    const button = document.getElementById('runAutomationBtn');
    if (!button) {
        console.error('runAutomationBtn element not found');
        showAlert('Automation button not found. Please refresh the page.', 'danger');
        return;
    }

    const btnText = button.querySelector('.btn-text');
    const btnLoading = button.querySelector('.btn-loading');
    const statusBadge = document.getElementById('automationStatus');    
    const progressBar = document.getElementById('automationProgress');

    // Check if all required elements exist
    if (!btnText || !btnLoading || !statusBadge || !progressBar) {
        console.error('Required DOM elements not found:', {
            btnText: !!btnText,
            btnLoading: !!btnLoading,
            statusBadge: !!statusBadge,
            progressBar: !!progressBar
        });
        showAlert('Required UI elements not found. Please refresh the page.', 'danger');
        return;
    }

    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    // button.disabled = true;
    button.classList.add('runbtn_disable');
    statusBadge.textContent = 'Running';
    statusBadge.className = 'badge bg-warning';
    progressBar.style.width = '2%';
    

    try {
        // Make API call to run automation with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), (window.APP_CONFIG && APP_CONFIG.AUTOMATION_TIMEOUT_MS) || 300000);

        const baseUrl = (window.APP_CONFIG && APP_CONFIG.API_DOWNLOAD_RFP) || '/download-rfp';
        const companyParam = (selectedCompany || '').trim();
        const url = companyParam ? `${baseUrl}?company=${encodeURIComponent(companyParam)}` : baseUrl;

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response) {
            throw new Error('No response received from server');
        }

        let result;
        try {
            result = await response.json();
        } catch (parseError) {
            throw new Error('Invalid response format from server');
        }

        if (response.ok || response.status === 202) {
            // Background started; poll status until finished
            await pollAutomationUntilIdle('download');
        } else {
            throw new Error(result.detail || result.message || `Server error: ${response.status}`);
        }

    } catch (error) {
        console.error('Automation error:', error);

        // Handle specific error types
        let errorMessage = error.message;
        if (error.name === 'AbortError') {
            errorMessage = 'Automation timed out. Please try again.';
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            errorMessage = 'Network error. Please check your connection and try again.';
        }

        // Show error state only if elements still exist
        if (statusBadge && progressBar) {
            statusBadge.textContent = 'Failed';
            statusBadge.className = 'badge bg-danger';
            progressBar.style.width = '0%';
        }

        showAlert(`Automation failed: ${errorMessage}`, 'danger');
        
    } finally {
        // Hide loading state after a brief delay to show completion status
        setTimeout(() => {
            // Check if elements still exist before manipulating them
            if (btnText && btnLoading && button && statusBadge && progressBar) {
                btnText.classList.remove('d-none');
                btnLoading.classList.add('d-none');
                // button.disabled = false;
                button.classList.remove('runbtn_disable');
                hidePageLoader();

                // Reset status after showing completion for a while
                setTimeout(() => {
                    if (statusBadge && progressBar) {
                        statusBadge.textContent = 'Ready';
                        statusBadge.className = 'badge bg-secondary';
                        progressBar.style.width = '0%';
                    }
                }, (window.APP_CONFIG && APP_CONFIG.STATUS_RESET_DELAY_MS) || 3000);
            }
        }, 1000);
    }
}

async function pollAutomationUntilIdle(expected, options = {}) {
    const statusBadge = document.getElementById('automationStatus');
    const progressBar = document.getElementById('automationProgress');
    const autoRefresh = options.autoRefresh !== false; // Default true for backward compatibility
    
    try {
        let attempts = 0;
        const maxAttempts = 600; // ~10 minutes
        const key = expected ? `${expected}_running` : null;

        console.log(`🔍 Starting to poll for ${expected} automation (key: ${key})`);

        while (attempts < maxAttempts) {
            attempts++;
            const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_AUTOMATION_STATUS) || '/automation/status');
            const data = await res.json();
            const running = key ? !!data[key] : (data.download_running || data.submit_running || data.decline_running || data.sync_running);
            
            if (attempts === 1) {
                console.log('📊 Automation status:', data);
                console.log(`🔍 Checking ${key}: ${running}`);
            }
            
            if (running) {
                if (attempts % 10 === 0) { // Log every 10 attempts
                    console.log(`⏳ Still running... (attempt ${attempts})`);
                }
                if (statusBadge) {
                    statusBadge.textContent = 'Running';
                    statusBadge.className = 'badge bg-warning';
                }
                if (progressBar) {
                    const width = Math.min(50, (attempts % 50) + 10);
                    progressBar.style.width = width + '%';
                }
                await new Promise(r => setTimeout(r, 1000));
                continue;
            }
            
            console.log(`✅ Automation completed after ${attempts} attempts`);
            // Finished
            if (statusBadge) {
                statusBadge.textContent = 'Completed';
                statusBadge.className = 'badge bg-success';
            }
            if (progressBar) {
                progressBar.style.width = '100%';
            }

            // Only auto-refresh if autoRefresh option is true
            if (autoRefresh) {
                // Force dashboard refresh with cache-busting param; include fallback hard reload
                const refreshUrl = '/dashboard?refresh=' + Date.now();
                setTimeout(() => {
                    try { window.location.href = refreshUrl; } catch(_) {}
                    setTimeout(() => { try { window.location.reload(); } catch(_) {} }, 1500);
                }, 400);

                // Reset UI status after some delay (in case navigation is blocked)
                setTimeout(() => {
                    if (statusBadge) {
                        statusBadge.textContent = 'Ready';
                        statusBadge.className = 'badge bg-secondary';
                    }
                    if (progressBar) {
                        progressBar.style.width = '0%';
                    }
                }, (window.APP_CONFIG && APP_CONFIG.STATUS_RESET_DELAY_MS) || 3000);
            }
            
            break;
        }
    } catch (e) {
        console.error('Status polling failed', e);
    }
}

// Run Download All RFPs function
async function runDownloadAllRfps() {
    const button = document.getElementById('downloadAllRfpsBtn');
    const modalButton = document.getElementById('confirmDownloadAllRfpsBtn');
    const modal = bootstrap.Modal.getInstance(document.getElementById('downloadAllRfpsModal'));
    const companySelect = document.getElementById('companyFilterSelect');
    
    if (!button) return;
    
    // Get selected company
    const selectedCompany = companySelect ? companySelect.value : '';
    
    // Validate selection
    if (!selectedCompany) {
        const alertBox = document.getElementById('downloadAllRfpsAlert');
        const alertMsg = document.getElementById('downloadAllRfpsAlertMessage');
        if (alertBox && alertMsg) {
            alertMsg.textContent = 'Please select a company or "All Companies" option.';
            alertBox.className = 'alert alert-danger alert-dismissible fade mt-3 show';
            alertBox.style.display = 'block';
        }
        return;
    }
    
    const btnText = button.querySelector('.btn-text');
    const btnLoading = button.querySelector('.btn-loading');
    const modalBtnText = modalButton?.querySelector('.btn-text');
    const modalBtnLoading = modalButton?.querySelector('.btn-loading');
    const alertBox = document.getElementById('downloadAllRfpsAlert');
    const alertMsg = document.getElementById('downloadAllRfpsAlertMessage');

    // Show loading state
    if (btnText) btnText.classList.add('d-none');
    if (btnLoading) btnLoading.classList.remove('d-none');
    if (modalBtnText) modalBtnText.classList.add('d-none');
    if (modalBtnLoading) modalBtnLoading.classList.remove('d-none');
    if (button) button.disabled = true;
    if (modalButton) modalButton.disabled = true;
    if (alertBox) alertBox.style.display = 'none';

    try {
        const response = await fetch('/dashboard/download-all-rfps', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                company: selectedCompany
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || data.message || 'Failed to start download all RFPs');
        }

        // Show success message
        if (alertBox && alertMsg) {
            const companyText = selectedCompany || 'All Companies';
            alertMsg.textContent = `Download All RFPs automation started for ${companyText}! This process may take a while.`;
            alertBox.className = 'alert alert-success alert-dismissible fade mt-3 show';
            alertBox.style.display = 'block';
        }

        // Close modal after a short delay
        setTimeout(() => {
            if (modal) modal.hide();
            // Reset dropdown
            if (companySelect) companySelect.value = '';
        }, 2000);

        // Show success notification
        showAlert('Download All RFPs automation started successfully!', 'success');

    } catch (error) {
        console.error('Error starting download all RFPs:', error);
        
        // Show error message
        if (alertBox && alertMsg) {
            alertMsg.textContent = error.message || 'Failed to start download all RFPs automation.';
            alertBox.className = 'alert alert-danger alert-dismissible fade mt-3 show';
            alertBox.style.display = 'block';
        }
        
        showAlert(error.message || 'Failed to start download all RFPs automation.', 'danger');
    } finally {
        // Reset button states
        if (btnText) btnText.classList.remove('d-none');
        if (btnLoading) btnLoading.classList.add('d-none');
        if (modalBtnText) modalBtnText.classList.remove('d-none');
        if (modalBtnLoading) modalBtnLoading.classList.add('d-none');
        if (button) button.disabled = false;
        if (modalButton) modalButton.disabled = false;
    }
}

// Run Sync Portal function
async function runSyncPortal(rfpIds, buttonId) {
    const button = document.getElementById(buttonId || 'syncPortalBtn');
    if (!button) return;
    const btnText = button.querySelector('.btn-text');
    const btnLoading = button.querySelector('.btn-loading');

    // Show loading state (button + global)
    btnText && btnText.classList.add('d-none');
    btnLoading && btnLoading.classList.remove('d-none');
    button.disabled = true;
    // showPageLoader('Syncing portal data...');

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), (window.APP_CONFIG && APP_CONFIG.AUTOMATION_TIMEOUT_MS) || 300000);
        let syncUrl = (window.APP_CONFIG && APP_CONFIG.API_SYNC_PORTAL) || '/sync_portal_data';
        if (rfpIds && rfpIds.length > 0) {
            syncUrl += '?rfp_ids=' + encodeURIComponent(rfpIds.join(','));
        }
        const response = await fetch(syncUrl, { method: 'GET', signal: controller.signal });
        clearTimeout(timeoutId);

        const j = await response.json().catch(() => ({}));
        if (!response.ok && response.status !== 202) {
            throw new Error(j.detail || j.message || 'Failed to start sync');
        }

        // Poll status until sync completes (unified poller)
        await pollAutomationUntilIdle('sync', { autoRefresh: false });
        showAlert('Portal sync completed successfully', 'success');
        setTimeout(() => { window.location.reload(); }, 500);
    } catch (e) {
        showAlert(`Sync failed: ${e.message || e}`, 'danger');
        // hidePageLoader();
    } finally {
        btnText && btnText.classList.remove('d-none');
        btnLoading && btnLoading.classList.add('d-none');
        button.disabled = false;
    }
}

async function pollSyncUntilIdle() {
    try {
        let attempts = 0;
        const maxAttempts = 600;
        while (attempts < maxAttempts) {
            attempts++;
            const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_AUTOMATION_STATUS) || '/automation/status');
            const data = await res.json();
            if (data.sync_running) {
                await new Promise(r => setTimeout(r, 1000));
                continue;
            }
            // After sync completes, refresh dashboard so analytics and tables update
            setTimeout(() => { window.location.href = '/dashboard?refresh=1'; }, 300);
            break;
        }
    } catch (e) {
        console.error('Sync polling failed', e);
    }
}

// Button loader helpers and status sync
function setButtonLoading(buttonId, isLoading) {
    const btn = document.getElementById(buttonId);
    if (!btn) return;
    const btnText = btn.querySelector('.btn-text');
    const btnLoading = btn.querySelector('.btn-loading');
    if (isLoading) {
        btnText && btnText.classList.add('d-none');
        btnLoading && btnLoading.classList.remove('d-none');
        // btn.disabled = true;
        btn.classList.add('runbtn_disable');
    } else {
        btnText && btnText.classList.remove('d-none');
        btnLoading && btnLoading.classList.add('d-none');
        // btn.disabled = false;
        btn.classList.remove('runbtn_disable');
    }
}

async function syncUiWithAutomationStatus() {
    try {
        const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_AUTOMATION_STATUS) || '/automation/status');
        const data = await res.json();
        const running = data.download_running || data.submit_running || data.decline_running || data.sync_running;

        const statusBadge = document.getElementById('automationStatus');
        const progressBar = document.getElementById('automationProgress');
        if (running) {
            statusBadge && (statusBadge.textContent = 'Running', statusBadge.className = 'badge bg-warning');
            if (progressBar) {
                const w = Math.min(90, ((Date.now() / 1000) % 90) + 10);
                progressBar.style.width = w + '%';
            }
        } else {
            statusBadge && (statusBadge.textContent = 'Ready', statusBadge.className = 'badge bg-secondary');
            progressBar && (progressBar.style.width = '0%');
        }

        setButtonLoading('runAutomationBtn', !!data.download_running);
        setButtonLoading('submitRfpBtn', !!data.submit_running);
        setButtonLoading('declineRfpBtn', !!data.decline_running);
        setButtonLoading('syncPortalBtn', !!data.sync_running);
    } catch (e) {
        console.error('syncUiWithAutomationStatus error:', e);
    }
}

// Schedule save function
async function saveSchedule() {
    const btn = document.getElementById('saveScheduleBtn');
    const btnText = btn?.querySelector('.btn-text');
    const btnLoading = btn?.querySelector('.btn-loading');
    const form = document.getElementById('scheduleAutomationForm');
    if (!form || !btn || !btnText || !btnLoading) return;

    const interval = document.getElementById('scheduleInterval')?.value;
    const frequency = document.getElementById('scheduleFrequency')?.value;
    const timezone = document.getElementById('scheduleTimezone')?.value;
    const startTime = document.getElementById('scheduleStartTime')?.value;
    const maxConcurrency = document.getElementById('scheduleMaxConcurrency')?.value;
    const notes = document.getElementById('scheduleNotes')?.value;

    // basic validation
    if (!interval || !frequency) {
        showScheduleAlert('Interval and Frequency are required', 'danger');
        return;
    }

    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    btn.disabled = true;
    showPageLoader('Saving schedule...');

    try {
        const payload = {
            interval: Number(interval),
            frequency,
            timezone,
            start_time: startTime,
            max_concurrency: maxConcurrency ? Number(maxConcurrency) : 1,
            notes
        };

        // POST to backend (endpoint to be implemented server-side if not present)
        const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_SCHEDULE_SAVE) || '/dashboard/schedule-automation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const j = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(j.detail || j.message || 'Failed to save schedule');

        showScheduleAlert('Schedule saved successfully', 'success');
        hidePageLoader();
        setTimeout(() => {
            const modalEl = document.getElementById('scheduleAutomationModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modal.hide();
            }
        }, 900);
    } catch (e) {
        showScheduleAlert(e.message || 'Error saving schedule', 'danger');
        hidePageLoader();
    } finally {
        btnText.classList.remove('d-none');
        btnLoading.classList.add('d-none');
        btn.disabled = false;
    }
}

function showScheduleAlert(message, type) {
    const alertBox = document.getElementById('scheduleAlert');
    const alertMsg = document.getElementById('scheduleAlertMessage');
    if (!alertBox || !alertMsg) return;
    alertMsg.textContent = message;
    alertBox.className = `alert alert-${type} alert-dismissible fade show`;
    alertBox.style.display = 'block';
}

async function prefillLatestSchedule() {
    try {
        const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_SCHEDULE_LATEST) || '/dashboard/schedule-automation/latest');
        const j = await res.json();
        if (!res.ok || !j.ok) return;
        const d = j.data || {};
        const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined && val !== null && val !== '') el.value = val; };
        setVal('scheduleInterval', d.interval);
        setVal('scheduleFrequency', d.frequency);
        setVal('scheduleTimezone', d.timezone);
        if (d.start_time) {
            const dt = new Date(d.start_time);
            if (!isNaN(dt)) {
                const pad = n => String(n).padStart(2, '0');
                const local = `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
                setVal('scheduleStartTime', local);
            }
        }
        setVal('scheduleMaxConcurrency', d.max_concurrency);
        setVal('scheduleNotes', d.notes);
    } catch (e) {
        // ignore prefill errors; user can input manually
    }
}

// Export data functionality (demo)
function exportData() {
    const dataStr = JSON.stringify(users, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = 'users-export.json';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('Data exported successfully', 'success');
}

// Print functionality
function printReport() {
    window.print();
}

// Dark mode toggle (optional enhancement)
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

// Load dark mode preference
document.addEventListener('DOMContentLoaded', function() {
    const darkMode = localStorage.getItem('darkMode');
    if (darkMode === 'true') {
        document.body.classList.add('dark-mode');
    }
});

// Profile functionality
async function handleProfileUpdate(e) {
    e.preventDefault();
    
    const form = document.getElementById('profileForm');
    const saveBtn = document.getElementById('saveProfileBtn');
    const btnText = saveBtn.querySelector('.btn-text');
    const btnLoading = saveBtn.querySelector('.btn-loading');
    
    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    saveBtn.disabled = true;
    showPageLoader('Updating profile...');
    
    try {
        const formData = new FormData(form);
        const data = {};
        
        // Collect form data
        for (let [key, value] of formData.entries()) {
            if (value.trim()) {
                data[key] = value.trim();
            }
        }
        
        // Validate password fields if any are filled
        if (data.current_password || data.new_password || data.confirm_password) {
            if (!data.current_password) {
                throw new Error('Current password is required to change password');
            }
            if (!data.new_password) {
                throw new Error('New password is required');
            }
            if (!data.confirm_password) {
                throw new Error('Please confirm your new password');
            }
            if (data.new_password !== data.confirm_password) {
                throw new Error('New passwords do not match');
            }
            if (data.new_password.length < 6) {
                throw new Error('New password must be at least 6 characters');
            }
        }
        
        // Make API call
        const response = await fetch((window.APP_CONFIG && APP_CONFIG.API_PROFILE) || '/dashboard/profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showProfileAlert('Profile updated successfully!', 'success');
            hidePageLoader();
            
            // Update user name in header if it changed
            if (data.name) {
                const userNameElement = document.getElementById('userName');
                if (userNameElement) {
                    userNameElement.textContent = data.name;
                }
            }
            
            // Clear password fields
            document.getElementById('currentPassword').value = '';
            document.getElementById('newPassword').value = '';
            document.getElementById('confirmPassword').value = '';
            
        } else {
            throw new Error(result.detail || result.message || 'Failed to update profile');
        }
        
    } catch (error) {
        console.error('Profile update error:', error);
        showProfileAlert(`Error: ${error.message}`, 'danger');
        hidePageLoader();
    } finally {
        // Hide loading state
        btnText.classList.remove('d-none');
        btnLoading.classList.add('d-none');
        saveBtn.disabled = false;
    }
}

// SAP Password functionality
async function submitSapPasswordChange() {
    const newPwd = document.getElementById('sapNewPassword');
    const usernameInput = document.getElementById('sapUsername');
    const saveBtn = document.getElementById('saveSapPasswordBtn');
    const btnText = saveBtn.querySelector('.btn-text');
    const btnLoading = saveBtn.querySelector('.btn-loading');

    const password = (newPwd?.value ?? "");
    const username = (usernameInput?.value ?? "");

    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    saveBtn.disabled = true;
    showPageLoader('Updating SAP password...');

    try {
        const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_SAP_PASSWORD) || '/dashboard/sap-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password, username })
        });
        const j = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(j.detail || j.message || 'Failed to save password');

        showSapAlert('SAP password updated successfully', 'success');
        hidePageLoader();
        setTimeout(() => {
            const modalEl = document.getElementById('sapPasswordModal');
            if (modalEl) {
                const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modal.hide();
            }
        }, 900);
    } catch (e) {
        showSapAlert(e.message || 'Error updating password', 'danger');
        hidePageLoader();
    } finally {
        btnText.classList.remove('d-none');
        btnLoading.classList.add('d-none');
        saveBtn.disabled = false;
    }
}


function showSapAlert(message, type) {
    const alertBox = document.getElementById('sapPasswordAlert');
    const alertMsg = document.getElementById('sapPasswordAlertMessage');
    if (!alertBox || !alertMsg) return;
    alertMsg.textContent = message;
    alertBox.className = `alert alert-${type} alert-dismissible fade show`;
    alertBox.style.display = 'block';
}

function resetProfileForm() {
    const form = document.getElementById('profileForm');
    if (form) {
        form.reset();
        // Clear any validation classes
        form.querySelectorAll('.is-invalid, .is-valid').forEach(input => {
            input.classList.remove('is-invalid', 'is-valid');
        });
        showProfileAlert('Form reset to original values', 'info');
    }
}

function validatePasswordMatch() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const confirmInput = document.getElementById('confirmPassword');
    
    if (confirmPassword && newPassword !== confirmPassword) {
        confirmInput.classList.add('is-invalid');
        confirmInput.classList.remove('is-valid');
    } else if (confirmPassword && newPassword === confirmPassword) {
        confirmInput.classList.add('is-valid');
        confirmInput.classList.remove('is-invalid');
    } else {
        confirmInput.classList.remove('is-invalid', 'is-valid');
    }
}

function showProfileAlert(message, type = 'info') {
    const alertContainer = document.getElementById('profileAlert');
    const alertMessage = document.getElementById('profileAlertMessage');
    
    if (alertContainer && alertMessage) {
        alertMessage.textContent = message;
        alertContainer.className = `alert alert-${type} alert-dismissible fade show`;
        alertContainer.style.display = 'block';
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            alertContainer.style.display = 'none';
        }, 5000);
    } else {
        // Fallback to general alert function
        showAlert(message, type);
    }
}

// ================= Session Management =================

// Session management variables
let sessionManager = {
    idleTimer: null,
    warningTimer: null,
    refreshTimer: null,
    countdownTimer: null,
    isWarningShown: false,
    lastActivity: Date.now(),
    
    // Configuration (in milliseconds)
    IDLE_TIMEOUT: (window.APP_CONFIG && APP_CONFIG.IDLE_TIMEOUT_MS) || 1800000, // 30 minutes
    WARNING_TIME: (window.APP_CONFIG && APP_CONFIG.SESSION_WARNING_MS) || 300000, // 5 minutes
    REFRESH_INTERVAL: (window.APP_CONFIG && APP_CONFIG.SESSION_REFRESH_MS) || 300000, // 5 minutes
    SESSION_TIMEOUT: (window.APP_CONFIG && APP_CONFIG.SESSION_TIMEOUT_MS) || 7200000, // 2 hours
    
    init() {
        this.startIdleTimer();
        this.startRefreshTimer();
        this.setupActivityListeners();
        this.setupWarningModalListeners();
        console.log('Session manager initialized');
    },
    
    setupActivityListeners() {
        // Track user activity
        const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
        events.forEach(event => {
            document.addEventListener(event, () => this.resetIdleTimer(), true);
        });
    },
    
    setupWarningModalListeners() {
        // Stay logged in button
        const stayLoggedInBtn = document.getElementById('stayLoggedInBtn');
        if (stayLoggedInBtn) {
            stayLoggedInBtn.addEventListener('click', () => this.stayLoggedIn());
        }
        
        // Logout button
        const logoutBtn = document.getElementById('logoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => this.logout());
        }
    },
    
    resetIdleTimer() {
        this.lastActivity = Date.now();
        
        // Clear existing timers
        if (this.idleTimer) clearTimeout(this.idleTimer);
        if (this.warningTimer) clearTimeout(this.warningTimer);
        
        // Hide warning modal if shown
        if (this.isWarningShown) {
            this.hideWarningModal();
        }
        
        // Start new idle timer
        this.startIdleTimer();
    },
    
    startIdleTimer() {
        this.idleTimer = setTimeout(() => {
            this.showWarningModal();
        }, this.IDLE_TIMEOUT - this.WARNING_TIME);
    },
    
    startRefreshTimer() {
        this.refreshTimer = setInterval(() => {
            this.refreshSession();
        }, this.REFRESH_INTERVAL);
    },
    
    async refreshSession() {
        try {
            const response = await fetch('/session/refresh', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                console.log('Session refreshed successfully');
            } else if (response.status === 401) {
                console.log('Session expired, redirecting to login');
                this.redirectToLogin();
            }
        } catch (error) {
            console.error('Session refresh failed:', error);
        }
    },
    
    showWarningModal() {
        if (this.isWarningShown) return;
        
        this.isWarningShown = true;
        const modal = new bootstrap.Modal(document.getElementById('sessionWarningModal'));
        modal.show();
        
        // Start countdown
        this.startCountdown();
        
        // Set timer for automatic logout
        this.warningTimer = setTimeout(() => {
            this.logout();
        }, this.WARNING_TIME);
    },
    
    hideWarningModal() {
        this.isWarningShown = false;
        const modalEl = document.getElementById('sessionWarningModal');
        if (modalEl) {
            const modal = bootstrap.Modal.getInstance(modalEl);
            if (modal) modal.hide();
        }
        
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
        }
    },
    
    startCountdown() {
        let timeLeft = this.WARNING_TIME / 1000; // Convert to seconds
        
        this.countdownTimer = setInterval(() => {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = Math.floor(timeLeft % 60);
            const countdownEl = document.getElementById('sessionCountdown');
            
            if (countdownEl) {
                countdownEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
            
            timeLeft--;
            
            if (timeLeft < 0) {
                clearInterval(this.countdownTimer);
            }
        }, 1000);
    },
    
    async stayLoggedIn() {
        try {
            await this.refreshSession();
            this.hideWarningModal();
            this.resetIdleTimer();
            console.log('User chose to stay logged in');
        } catch (error) {
            console.error('Failed to extend session:', error);
            this.logout();
        }
    },
    
    async logout() {
        try {
            await fetch('/logout', { method: 'POST' });
        } catch (error) {
            console.error('Logout request failed:', error);
        } finally {
            this.redirectToLogin();
        }
    },
    
    redirectToLogin() {
        // Clear all timers
        this.cleanup();
        
        // Redirect to login
        window.location.href = '/login';
    },
    
    cleanup() {
        if (this.idleTimer) clearTimeout(this.idleTimer);
        if (this.warningTimer) clearTimeout(this.warningTimer);
        if (this.refreshTimer) clearInterval(this.refreshTimer);
        if (this.countdownTimer) clearInterval(this.countdownTimer);
    }
};

// Initialize session manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize on dashboard pages
    if (window.location.pathname.includes('/dashboard') || window.location.pathname === '/') {
        sessionManager.init();
        // Initial sync of loaders from server state
        if (typeof syncUiWithAutomationStatus === 'function') {
            syncUiWithAutomationStatus();
            // Extra early tick to restore button loader right after initial render
            setTimeout(() => {
                try { syncUiWithAutomationStatus(); } catch (_) {}
            }, 150);
            setInterval(syncUiWithAutomationStatus, 1000);
        }
        // Also re-sync when tab regains focus or becomes visible again
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && typeof syncUiWithAutomationStatus === 'function') {
                syncUiWithAutomationStatus();
            }
        });
        window.addEventListener('focus', () => {
            if (typeof syncUiWithAutomationStatus === 'function') {
                syncUiWithAutomationStatus();
            }
        });
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    sessionManager.cleanup();
});

// ================= Submit RFP Handler =================
async function handleSubmitRfp() {
    const submitBtn = document.getElementById('submitRfpSubmitBtn');
    const btnText = submitBtn?.querySelector('.btn-text');
    const btnLoading = submitBtn?.querySelector('.btn-loading');
    const form = document.getElementById('submitRfpForm');
    
    if (!form || !submitBtn || !btnText || !btnLoading) return;

    const rfpName = document.getElementById('rfpName')?.value?.trim();
    const submitCompanySelect = document.getElementById('submitRfpCompanySelect');
    const submitCompany = submitCompanySelect?.value?.trim();
    const excelFile = document.getElementById('excelFile')?.files[0];
    const technicalFilesInput = document.getElementById('technicalFiles');
    const technicalFiles = technicalFilesInput ? Array.from(technicalFilesInput.files || []) : [];

    // Validation
    if (!rfpName) {
        showSubmitRfpAlert('Please enter RFP Name', 'danger');
        return;
    }

    if (!submitCompany) {
        showSubmitRfpAlert('Please select a company', 'danger');
        submitCompanySelect?.classList.add('is-invalid');
        submitCompanySelect?.focus();
        return;
    } else {
        submitCompanySelect?.classList.remove('is-invalid');
    }

    if (!excelFile) {
        showSubmitRfpAlert('Please upload an Excel file', 'danger');
        return;
    }

    // Validate file type
    const allowedExtensions = ['.xls', '.xlsx'];
    const fileName = excelFile.name.toLowerCase();
    const isValidFile = allowedExtensions.some(ext => fileName.endsWith(ext));
    
    if (!isValidFile) {
        showSubmitRfpAlert('Please upload a valid Excel file (.xls or .xlsx)', 'danger');
        return;
    }

    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    submitBtn.disabled = true;

    try {
        // Create FormData to send files
        const formData = new FormData();
        formData.append('rfp_id', rfpName);
        formData.append('company', submitCompany);
        formData.append('excel_file', excelFile);
        // Append technical PDFs (optional, multiple)
        if (technicalFiles && technicalFiles.length > 0) {
            for (const file of technicalFiles) {
                // Only allow pdf
                if (file && typeof file.name === 'string' && file.name.toLowerCase().endsWith('.pdf')) {
                    formData.append('technical_files', file);
                }
            }
        }

        // Make API call to dashboard-specific endpoint
        const response = await fetch((window.APP_CONFIG && APP_CONFIG.API_SUBMIT_RFP) || '/dashboard/submit-rfp', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok || response.status === 202) {
            showSubmitRfpAlert('RFP submitted successfully! Automation started in background.', 'success');
            // Close modal after a delay
            setTimeout(() => {
                const modalEl = document.getElementById('submitRfpModal');
                if (modalEl) {
                    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                    modal.hide();
                }
                showAlert('RFP submission started.', 'success');
            }, 1500);
            // Start polling to toggle loaders on submit controls
            await pollSubmitButtonUntilIdle();
            // Wait for submit automation to finish and then refresh via unified poller
            try { localStorage.setItem('preferredRfpTab', 'submitted'); } catch(_) {}
            await pollAutomationUntilIdle('submit');
        } else {
            throw new Error(result.detail || result.message || 'Failed to submit RFP');
        }

    } catch (error) {
        console.error('Submit RFP error:', error);
        showSubmitRfpAlert(`Error: ${error.message}`, 'danger');
       
    } finally {
        // Hide loading state
        btnText.classList.remove('d-none');
        btnLoading.classList.add('d-none');
        submitBtn.disabled = false;
    }
}

async function pollSubmitButtonUntilIdle() {
    const mainBtn = document.getElementById('submitRfpBtn');
    const modalBtn = document.getElementById('submitRfpSubmitBtn');
    const modalBtnText = modalBtn?.querySelector('.btn-text');
    const modalBtnLoading = modalBtn?.querySelector('.btn-loading');
    try {
        let attempts = 0;
        const maxAttempts = 600;
        // Show visual running state on main button (if present)
        if (mainBtn) mainBtn.classList.add('disabled');
        if (modalBtnText && modalBtnLoading) {
            modalBtnText.classList.add('d-none');
            modalBtnLoading.classList.remove('d-none');
        }
        while (attempts < maxAttempts) {
            attempts++;
            const res = await fetch((window.APP_CONFIG && APP_CONFIG.API_AUTOMATION_STATUS) || '/automation/status');
            const data = await res.json();
            if (data.submit_running) {
                await new Promise(r => setTimeout(r, 1000));
                continue;
            }
            break;
        }
    } catch (e) {
        console.error('Submit polling failed', e);
    } finally {
        const mainBtn = document.getElementById('submitRfpBtn');
        const modalBtn = document.getElementById('submitRfpSubmitBtn');
        const modalBtnText = modalBtn?.querySelector('.btn-text');
        const modalBtnLoading = modalBtn?.querySelector('.btn-loading');
        if (mainBtn) mainBtn.classList.remove('disabled');
        if (modalBtnText && modalBtnLoading) {
            modalBtnText.classList.remove('d-none');
            modalBtnLoading.classList.add('d-none');
        }
    }
}

function showSubmitRfpAlert(message, type) {
    const alertBox = document.getElementById('submitRfpAlert');
    const alertMsg = document.getElementById('submitRfpAlertMessage');
    if (!alertBox || !alertMsg) return;
    alertMsg.textContent = message;
    alertBox.className = `alert alert-${type} alert-dismissible fade show`;
    alertBox.style.display = 'block';
}


// ================= Decline RFP Handler =================
async function handleDeclineRfp() {
    const declineBtn = document.getElementById('declineRfpSubmitBtn');
    const btnText = declineBtn?.querySelector('.btn-text');
    const btnLoading = declineBtn?.querySelector('.btn-loading');
    const form = document.getElementById('declineRfpForm');
    
    if (!form || !declineBtn || !btnText || !btnLoading) return;

    const rfpTitle = document.getElementById('rfpTitle')?.value?.trim();
    const declineCompanySelect = document.getElementById('declineRfpCompanySelect');
    const declineCompany = declineCompanySelect?.value?.trim();

    // Validation
    if (!rfpTitle) {
        showDeclineRfpAlert('Please enter RFP Title', 'danger');
        return;
    }

    if (!declineCompany) {
        showDeclineRfpAlert('Please select a company', 'danger');
        declineCompanySelect?.classList.add('is-invalid');
        declineCompanySelect?.focus();
        return;
    } else {
        declineCompanySelect?.classList.remove('is-invalid');
    }

    // Show loading state (button + global)
    btnText.classList.add('d-none');
    btnLoading.classList.remove('d-none');
    declineBtn.disabled = true;
    showPageLoader('Declining RFP...');

    try {
        // Make API call to existing endpoint
        const response = await fetch((window.APP_CONFIG && APP_CONFIG.API_DECLINE_RFP) || '/decline-rfp', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ rfp_id: rfpTitle, company: declineCompany })
        });

        const result = await response.json();

        if (response.ok) {
            showDeclineRfpAlert('RFP declined successfully! The automation is running.', 'success');
            
            // Close modal after a delay
            setTimeout(() => {
                const modalEl = document.getElementById('declineRfpModal');
                if (modalEl) {
                    const modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                    modal.hide();
                }
                showAlert('RFP declined successfully!', 'success');
            }, 2000);
            // After decline finishes in background, refresh dashboard via unified poller
            (async () => {
                try { localStorage.setItem('preferredRfpTab', 'declined'); } catch(_) {}
                await pollAutomationUntilIdle('decline');
            })();
        } else {
            throw new Error(result.detail || result.message || 'Failed to decline RFP');
        }

    } catch (error) {
        console.error('Decline RFP error:', error);
        showDeclineRfpAlert(`Error: ${error.message}`, 'danger');
        hidePageLoader();
    } finally {
        // Hide loading state
        btnText.classList.remove('d-none');
        btnLoading.classList.add('d-none');
        declineBtn.disabled = false;
    }
}

function showDeclineRfpAlert(message, type) {
    const alertBox = document.getElementById('declineRfpAlert');
    const alertMsg = document.getElementById('declineRfpAlertMessage');
    if (!alertBox || !alertMsg) return;
    alertMsg.textContent = message;
    alertBox.className = `alert alert-${type} alert-dismissible fade show`;
    alertBox.style.display = 'block';
}

// ================= View Excel Handler (Download & Open) =================

// Store selected materials data
let selectedMaterialsData = null;
let currentRfpId = null;
let currentSubmitButton = null; // Track the listing button that initiated submission

/**
 * Submit RFP Button in listing page Initializer 
 */
function initSubmitRfpButtons() {
    const submitRfpButtons = document.querySelectorAll('.submit-rfp-btn');
    
    submitRfpButtons.forEach(button => {
        // Prevent re-binding if already bound
        if (button.dataset.bound === '1') return;
        button.dataset.bound = '1';
        
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const rfpId = this.getAttribute('data-rfp-id');
            
            if (!rfpId) {
                showAlert('RFP ID not found', 'danger');
                return;
            }
            
            currentRfpId = rfpId;
            currentSubmitButton = this; // Store button reference for later use
            
            // Show loading state using btn-text/btn-loading pattern
            const btnText = this.querySelector('.btn-text');
            const btnLoading = this.querySelector('.btn-loading');
            
            if (btnText && btnLoading) {
                btnText.classList.add('d-none');
                btnLoading.classList.remove('d-none');
            }
            this.disabled = true;
            
            try {
                // Fetch materials for this RFP
                const response = await fetch(`/dashboard/rfp/${encodeURIComponent(rfpId)}/materials`);
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.detail || 'Failed to load materials');
                }
                
                // Show materials modal
                showMaterialsModal(data);
                
                // Don't restore button state - keep it loading until submission completes
                
            } catch (error) {
                console.error('Error loading materials:', error);
                showAlert(`Error: ${error.message}`, 'danger');
                // Only restore button state on error
                if (btnText && btnLoading) {
                    btnText.classList.remove('d-none');
                    btnLoading.classList.add('d-none');
                }
                this.disabled = false;
                currentSubmitButton = null;
            }
        });
    });
}

/**
 * Show materials modal with materials list
 */
function showMaterialsModal(data) {
    const modalElement = document.getElementById('submitRfpMaterialsModal');
    if (!modalElement) {
        console.error('Materials modal not found on this page');
        showAlert('Materials modal is not available on this page. Please use the Dashboard page to submit RFPs.', 'warning');
        return;
    }
    
    const modal = new bootstrap.Modal(modalElement);
    
    // Reset state - add null checks
    selectedMaterialsData = data;
    const materialsTableBody = document.getElementById('materialsTableBody');
    const materialsLoading = document.getElementById('materialsLoading');
    const materialsContent = document.getElementById('materialsContent');
    const materialsError = document.getElementById('materialsError');
    const confirmMaterialsBtn = document.getElementById('confirmMaterialsBtn');
    
    if (materialsTableBody) materialsTableBody.innerHTML = '';
    if (materialsLoading) materialsLoading.classList.remove('d-none');
    if (materialsContent) materialsContent.classList.add('d-none');
    if (materialsError) materialsError.classList.add('d-none');
    if (confirmMaterialsBtn) confirmMaterialsBtn.disabled = true;
    
    // Update summary - add null checks
    const materialsRfpId = document.getElementById('materialsRfpId');
    const materialsTotal = document.getElementById('materialsTotal');
    const materialsMatched = document.getElementById('materialsMatched');
    const materialsUnmatched = document.getElementById('materialsUnmatched');
    
    if (materialsRfpId) materialsRfpId.textContent = data.rfp_id;
    if (materialsTotal) materialsTotal.textContent = data.total_materials;
    let matchedText = data.matched_count;
    if (data.exact_code_matches || data.keyword_matches) {
        matchedText += ` (${data.exact_code_matches || 0} Code, ${data.keyword_matches || 0} Keyword)`;
    }
    if (materialsMatched) materialsMatched.textContent = matchedText;
    if (materialsUnmatched) materialsUnmatched.textContent = data.unmatched_count;
    
    // Setup Decline RFP button handler
    const declineBtn = document.getElementById('declineRfpFromModalBtn');
    if (declineBtn) {
        // Remove any existing event listeners by cloning
        const newDeclineBtn = declineBtn.cloneNode(true);
        declineBtn.parentNode.replaceChild(newDeclineBtn, declineBtn);
        
        newDeclineBtn.addEventListener('click', async function() {
            // Show confirmation dialog
            const confirmed = window.confirm(
                `Are you sure you want to DECLINE RFP "${data.rfp_id}"?\n\n` +
                `This will run the decline process and mark this RFP as declined.`
            );
            
            if (!confirmed) return;
            
            // Close the materials modal first
            modal.hide();
            
            // Show loading
            const btnText = this.querySelector('.btn-text') || this;
            const originalHTML = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Declining...';
            
            try {
                // Call decline RFP API
                const response = await fetch((window.APP_CONFIG && APP_CONFIG.API_DECLINE_RFP) || '/decline-rfp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ rfp_id: data.rfp_id })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    showAlert(`RFP "${data.rfp_id}" is being declined. Please wait...`, 'success');
                    
                    // Poll until decline process completes
                    try { 
                        localStorage.setItem('preferredRfpTab', 'declined'); 
                    } catch(_) {}
                    
                    await pollAutomationUntilIdle('decline');
                } else {
                    throw new Error(result.detail || result.message || 'Failed to decline RFP');
                }
                
            } catch (error) {
                console.error('Decline RFP error:', error);
                showAlert(`Error declining RFP: ${error.message}`, 'danger');
            } finally {
                this.disabled = false;
                this.innerHTML = originalHTML;
            }
        });
    }
    
    // Show modal
    modal.show();
    
    // Populate materials table
    setTimeout(() => {
        populateMaterialsTable(data.materials);
        document.getElementById('materialsLoading').classList.add('d-none');
        document.getElementById('materialsContent').classList.remove('d-none');
    }, 500);
}

/**
 * Populate materials table
 */
function populateMaterialsTable(materials) {
    const tbody = document.getElementById('materialsTableBody');
    tbody.innerHTML = '';
    
    // Dropdown options for unmatched materials (from image description)
    const reasonOptions = [
        { value: '', text: '(no value)' },
        { value: 'no_compatible_part', text: 'We don\'t carry a compatible part/material' },
        { value: 'insufficient_quantity', text: 'We don\'t supply at the requested quantity' },
        { value: 'discontinued', text: 'Discontinued Item' },
        { value: 'full_capacity', text: 'We are currently at full capacity' },
        { value: 'missing_info', text: 'Missing information / not enough information provided' },
        { value: 'other', text: 'Other' }
    ];
    
    materials.forEach((material, index) => {
        const row = document.createElement('tr');
        
        // Highlight matched materials
        if (material.is_matched) {
            row.classList.add('table-success');
        } else {
            row.classList.add('table-warning');
        }
        
        // Checkbox
        const checkboxCell = document.createElement('td');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'material-checkbox';
        checkbox.dataset.index = index;
        checkbox.checked = material.selected || false;
        checkbox.addEventListener('change', function() {
            material.selected = this.checked;
            updateConfirmButton();
        });
        checkboxCell.appendChild(checkbox);
        
        // Material Code
        const codeCell = document.createElement('td');
        codeCell.textContent = material.material_code;
        codeCell.className = 'fw-bold';
        
        // Description (show name if description is empty)
        const descCell = document.createElement('td');
        const displayText = material.description || material.name || '-';
        descCell.textContent = displayText.length > 100 ? displayText.substring(0, 100) + '...' : displayText;
        descCell.title = displayText; // Full text on hover
        
        // Status
        const statusCell = document.createElement('td');
        if (material.is_matched) {
            if (material.match_method === 'exact_code') {
                statusCell.innerHTML = '<span class="badge bg-success">Matched (Code)</span>';
            } else if (material.match_method === 'keyword') {
                statusCell.innerHTML = '<span class="badge bg-info">Matched (Keyword)</span>';
            } else if (material.match_method === 'manual') {
                statusCell.innerHTML = '<span class="badge bg-primary">Manually Matched</span>';
            } else {
                statusCell.innerHTML = '<span class="badge bg-success">Matched</span>';
            }
        } else {
            statusCell.innerHTML = '<span class="badge bg-danger">Not Matched</span>';
        }
        
        // Reason dropdown (only for unmatched)
        const reasonCell = document.createElement('td');
        if (!material.is_matched) {
            const select = document.createElement('select');
            select.className = 'form-select form-select-sm';
            select.dataset.index = index;
            select.required = true;
            
            reasonOptions.forEach((option, optIdx) => {
                const opt = document.createElement('option');
                opt.value = option.value;
                opt.textContent = option.text;
                // Disable the first "(no value)" option
                if (optIdx === 0) {
                    opt.disabled = true;
                    opt.selected = !material.reason; // Select if no reason set
                } else if (material.reason === option.value) {
                    opt.selected = true;
                }
                select.appendChild(opt);
            });
            
            select.addEventListener('change', function() {
                material.reason = this.value;
                // Validate on change
                if (!this.value) {
                    this.classList.add('is-invalid');
                } else {
                    this.classList.remove('is-invalid');
                }
            });
            
            reasonCell.appendChild(select);
        } else {
            reasonCell.textContent = '-';
        }
        
        // Action button (Mark as Matched for unmatched materials)
        const actionCell = document.createElement('td');
        if (!material.is_matched) {
            const markMatchedBtn = document.createElement('button');
            markMatchedBtn.className = 'btn btn-sm btn-success';
            markMatchedBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i>Mark as Matched';
            markMatchedBtn.title = 'Manually mark this material as matched';
            markMatchedBtn.dataset.index = index;
            
            markMatchedBtn.addEventListener('click', function() {
                // Confirm with user
                const confirmed = window.confirm(`Are you sure you want to mark "${material.material_code}" as matched?`);
                if (!confirmed) return;
                
                // Update material status
                material.is_matched = true;
                material.match_method = 'manual';
                material.reason = ''; // Clear reason since it's now matched
                
                // Re-render the table to reflect changes
                populateMaterialsTable(materials);
                
                // Update summary counts
                updateMaterialsSummary(materials);
                
                showAlert(`Material "${material.material_code}" marked as matched`, 'success');
            });
            
            actionCell.appendChild(markMatchedBtn);
        } else {
            actionCell.textContent = '-';
        }
        
        row.appendChild(checkboxCell);
        row.appendChild(codeCell);
        row.appendChild(descCell);
        row.appendChild(statusCell);
        row.appendChild(reasonCell);
        row.appendChild(actionCell);
        
        tbody.appendChild(row);
    });
    
    // Select all checkbox handler
    const selectAllCheckbox = document.getElementById('selectAllMaterials');
    selectAllCheckbox.addEventListener('change', function() {
        const checkboxes = document.querySelectorAll('.material-checkbox');
        checkboxes.forEach((cb, idx) => {
            cb.checked = this.checked;
            materials[idx].selected = this.checked;
        });
        updateConfirmButton();
    });
    
    // Confirm button handler
    document.getElementById('confirmMaterialsBtn').addEventListener('click', function() {
        const selectedMaterials = materials.filter(m => m.selected);
        if (selectedMaterials.length === 0) {
            showAlert('Please select at least one material', 'warning');
            return;
        }
        
        // Validate unmatched materials have reasons
        const unmatchedWithoutReason = selectedMaterials.filter(m => !m.is_matched && (!m.reason || m.reason === ''));
        if (unmatchedWithoutReason.length > 0) {
            showAlert('Please provide a reason for all unmatched materials', 'warning');
            // Highlight invalid dropdowns
            unmatchedWithoutReason.forEach(m => {
                const index = materials.indexOf(m);
                const select = document.querySelector(`select[data-index="${index}"]`);
                if (select) {
                    select.classList.add('is-invalid');
                }
            });
            return;
        }
        
        // Show material details modal
        showMaterialDetailsModal(selectedMaterials);
    });
    
    updateConfirmButton();
}

/**
 * Update confirm button state
 */
function updateConfirmButton() {
    const checkboxes = document.querySelectorAll('.material-checkbox:checked');
    document.getElementById('confirmMaterialsBtn').disabled = checkboxes.length === 0;
}

/**
 * Update materials summary counts
 */
function updateMaterialsSummary(materials) {
    const total = materials.length;
    const matched = materials.filter(m => m.is_matched).length;
    const unmatched = total - matched;
    
    document.getElementById('materialsTotal').textContent = total;
    document.getElementById('materialsMatched').textContent = matched;
    document.getElementById('materialsUnmatched').textContent = unmatched;
}

/**
 * Show material details modal - DYNAMIC VERSION
 * Fetches form structure from backend based on Excel yellow cells
 */
async function showMaterialDetailsModal(selectedMaterials) {
    const modal = new bootstrap.Modal(document.getElementById('materialDetailsModal'));
    const content = document.getElementById('materialDetailsContent');
    
    // Close materials modal and clean up backdrop
    const materialsModal = bootstrap.Modal.getInstance(document.getElementById('submitRfpMaterialsModal'));
    if (materialsModal) {
        materialsModal.hide();
        // Clean up backdrop after modal closes
        setTimeout(() => {
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        }, 300);
    }
    
    // Show loading state
    content.innerHTML = `
        <div class="text-center p-5">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-3">Analyzing Excel file and generating form...</p>
        </div>
    `;
    
    modal.show();
    
    try {
        // Fetch dynamic form structure from backend
        const response = await fetch(`/dashboard/rfp/${currentRfpId}/dynamic-form-structure`);
        const data = await response.json();
        
        if (!response.ok || !data.ok) {
            throw new Error(data.detail || 'Failed to load form structure');
        }
        
        const formStructure = data.form_structure;
        console.log('📋 Dynamic form structure:', formStructure);
        
        // Build dynamic form HTML
        let html = `<div class="container-fluid">`;
        
        // Generate form sections dynamically based on yellow cells
        formStructure.sections.forEach((section, sectionIdx) => {
            html += `
                <div class="row mb-4">
                    <div class="col-12">
                        <h5 class="text-primary border-bottom pb-2">
                            <i class="fas fa-file-excel me-2"></i>${section.sheet_name}
                        </h5>
                    </div>
                </div>
            `;
            
            // Check if this is a material sheet (has grouped materials)
            if (section.is_material_sheet && section.materials) {
                // Display fields grouped by material
                html += `<div class="accordion" id="materialSheetAccordion_${sectionIdx}">`;
                
                section.materials.forEach((material, matIdx) => {
                    html += `
                        <div class="accordion-item">
                            <h2 class="accordion-header" id="matHeading_${sectionIdx}_${matIdx}">
                                <button class="accordion-button ${matIdx !== 0 ? 'collapsed' : ''}" type="button" 
                                        data-bs-toggle="collapse" data-bs-target="#matCollapse_${sectionIdx}_${matIdx}" 
                                        aria-expanded="${matIdx === 0 ? 'true' : 'false'}">
                                    <strong>Material:</strong>&nbsp;${material.material_code}
                                </button>
                            </h2>
                            <div id="matCollapse_${sectionIdx}_${matIdx}" 
                                 class="accordion-collapse collapse ${matIdx === 0 ? 'show' : ''}" 
                                 data-bs-parent="#materialSheetAccordion_${sectionIdx}">
                                <div class="accordion-body">
                    `;
                    
                    // Add fields for this material
                    material.fields.forEach((field, fieldIdx) => {
                        const inputId = field.id;
                        const fieldType = field.type;
                        const isRequired = field.required;
                        
                        html += `
                            <div class="row mb-3">
                                <div class="col-md-4">
                                    <label for="${inputId}" class="form-label">
                                        <strong>${field.label}:</strong>
                                        ${isRequired ? '<span class="text-danger">*</span>' : ''}
                                    </label>
                                </div>
                                <div class="col-md-8">
                        `;
                        
                        if (fieldType === 'dropdown') {
                            // Use dynamic options from backend if available
                            const dropdownOptions = field.options || ['Yes', 'No', 'Unspecified'];
                            const optionsHTML = dropdownOptions.map(opt => 
                                `<option value="${opt}">${opt}</option>`
                            ).join('');
                            
                            html += `
                                <select class="form-select form-select-sm" id="${inputId}" ${isRequired ? 'required' : ''}>
                                    <option value="">Select...</option>
                                    ${optionsHTML}
                                </select>
                            `;
                        } else {
                            html += `
                                <input 
                                    type="${fieldType}" 
                                    class="form-control form-control-sm" 
                                    id="${inputId}" 
                                    ${isRequired ? 'required' : ''}
                                    ${fieldType === 'number' ? 'step="1"' : ''}
                                >
                            `;
                        }
                        
                        html += `
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `
                                </div>
                            </div>
                        </div>
                    `;
                });
                
                html += `</div>`; // Close accordion
            } else {
                // Regular section - display fields normally
                section.fields.forEach((field, fieldIdx) => {
                    const inputId = field.id;
                    const fieldType = field.type;
                    const isRequired = field.required;
                    
                    html += `
                        <div class="row mb-3">
                            <div class="col-md-4">
                                <label for="${inputId}" class="form-label">
                                    <strong>${field.label}:</strong>
                                    ${isRequired ? '<span class="text-danger">*</span>' : ''}
                                </label>
                            </div>
                            <div class="col-md-8">
                    `;
                    
                    if (fieldType === 'dropdown') {
                        // Use dynamic options from backend if available
                        const dropdownOptions = field.options || ['Yes', 'No', 'Unspecified'];
                        const optionsHTML = dropdownOptions.map(opt => 
                            `<option value="${opt}">${opt}</option>`
                        ).join('');
                        
                        html += `
                            <select class="form-select form-select-sm" id="${inputId}" ${isRequired ? 'required' : ''}>
                                <option value="">Select...</option>
                                ${optionsHTML}
                            </select>
                        `;
                    } else {
                        html += `
                            <input 
                                type="${fieldType}" 
                                class="form-control form-control-sm" 
                                id="${inputId}" 
                                ${isRequired ? 'required' : ''}
                                ${fieldType === 'number' ? 'step="1"' : ''}
                            >
                        `;
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                });
            }
        });
        
        // Add materials section (dynamically from yellow cells)
        const materialListingFields = formStructure.material_listing_fields || [];
        
        html += `
            <div class="row mb-4">
                <div class="col-12">
                    <h5 class="text-primary border-bottom pb-2">
                        <i class="fas fa-boxes me-2"></i>Materials Required
                    </h5>
                </div>
            </div>
        `;
    
        // Add each selected material as collapsible accordion
        html += `<div class="accordion" id="materialsAccordion">`;
        
        selectedMaterials.forEach((material, idx) => {
            html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="heading_${idx}">
                        <button class="accordion-button ${idx !== 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse_${idx}" aria-expanded="${idx === 0 ? 'true' : 'false'}" aria-controls="collapse_${idx}">
                            <strong>Material ${idx + 1}:</strong>&nbsp;${material.material_code} - ${material.name || 'N/A'}
                            ${material.match_method === 'keyword' ? '&nbsp;<span class="badge bg-info">Keyword Match</span>' : ''}
                            ${material.match_method === 'exact_code' ? '&nbsp;<span class="badge bg-success">Code Match</span>' : ''}
                            ${material.match_method === 'manual' ? '&nbsp;<span class="badge bg-primary">Manual Match</span>' : ''}
                        </button>
                    </h2>
                    <div id="collapse_${idx}" class="accordion-collapse collapse ${idx === 0 ? 'show' : ''}" aria-labelledby="heading_${idx}" data-bs-parent="#materialsAccordion">
                        <div class="accordion-body">
                            <div class="row mb-2">
                                <div class="col-md-12">
                                    <strong>Material Code:</strong> ${material.material_code}<br>
                                    <strong>Name:</strong> ${material.name || '-'}<br>
                                    <strong>Description:</strong> ${material.description || '-'}
                                </div>
                            </div>
                            
                            ${!material.is_matched ? `
                            <div class="row mb-2">
                                <div class="col-md-12">
                                    <label class="form-label"><strong>Reason for Non-Match:</strong></label>
                                    <input type="text" class="form-control form-control-sm" value="${getReasonText(material.reason)}" readonly>
                                </div>
                            </div>
                            ` : ''}
                            
                            ${materialListingFields.length > 0 ? `
                                <!-- Dynamic fields from yellow cells -->
                                ${materialListingFields.map((field, fieldIdx) => {
                                    const inputId = `material_${idx}_${field.id}`;
                                    const fieldType = field.type;
                                    const isRequired = field.required;
                                    const label = field.label;
                                    const defaultValue = field.default_value || '';
                                    
                                    // Determine layout: 3 fields per row for better spacing
                                    const isNewRow = fieldIdx % 3 === 0;
                                    const isLastInRow = fieldIdx % 3 === 2 || fieldIdx === materialListingFields.length - 1;
                                    
                                    let fieldHtml = '';
                                    if (isNewRow) {
                                        fieldHtml += '<div class="row mb-2">';
                                    }
                                    
                                    // Determine column width
                                    const colWidth = 4; // 3 columns per row
                                    
                                    fieldHtml += `
                                        <div class="col-md-${colWidth}">
                                            <label class="form-label"><strong>${label}:</strong> ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                                    `;
                                    
                                    if (fieldType === 'dropdown') {
                                        // Use dynamic options from backend if available, otherwise fallback to Yes/No
                                        const dropdownOptions = field.options || ['Yes', 'No', 'Unspecified'];
                                        const optionsHTML = dropdownOptions.map(opt => 
                                            `<option value="${opt}">${opt}</option>`
                                        ).join('');
                                        
                                        fieldHtml += `
                                            <select class="form-select form-select-sm" id="${inputId}" ${isRequired ? 'required' : ''}>
                                                <option value="">Select...</option>
                                                ${optionsHTML}
                                            </select>
                                        `;
                                    } else if (fieldType === 'file') {
                                        fieldHtml += `
                                            <input type="file" class="form-control form-control-sm" id="${inputId}" accept=".pdf" ${isRequired ? 'required' : ''}>
                                            <small class="text-muted">Upload PDF file</small>
                                            <div id="${inputId}_list" class="mt-1 text-muted small"></div>
                                        `;
                                    } else {
                                        fieldHtml += `
                                            <input 
                                                type="${fieldType}" 
                                                class="form-control form-control-sm" 
                                                id="${inputId}" 
                                                ${isRequired ? 'required' : ''}
                                                ${fieldType === 'number' ? 'step="0.01"' : ''}
                                                ${defaultValue ? `value="${defaultValue}"` : ''}
                                            >
                                        `;
                                    }
                                    
                                    fieldHtml += `
                                        </div>
                                    `;
                                    
                                    if (isLastInRow) {
                                        fieldHtml += '</div>';
                                    }
                                    
                                    return fieldHtml;
                                }).join('')}
                            ` : `
                                <!-- Fallback: No yellow cells found, show basic fields -->
                                <div class="alert alert-warning">
                                    <i class="fas fa-exclamation-triangle me-2"></i>
                                    No material fields detected from yellow cells. Please check the Excel file formatting.
                                </div>
                            `}
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += `</div>`; // Close accordion
        
        html += `
                    </div>
                </div>
            </div>
        `;
        
        content.innerHTML = html;
    
        // Add event listeners for file inputs to show selected file
        selectedMaterials.forEach((material, idx) => {
            // Add listeners for dynamic file inputs from yellow cells
            materialListingFields.forEach((field) => {
                if (field.type === 'file') {
                    const fileInput = document.getElementById(`material_${idx}_${field.id}`);
                    const filesList = document.getElementById(`material_${idx}_${field.id}_list`);
                    
                    if (fileInput && filesList) {
                        fileInput.addEventListener('change', function(e) {
                            const file = e.target.files[0];
                            if (file) {
                                filesList.innerHTML = `<strong>Selected:</strong> ${file.name}`;
                            } else {
                                filesList.innerHTML = '';
                            }
                        });
                    }
                }
            });
        });
    
        // Final submit button handler
        document.getElementById('finalSubmitBtn').addEventListener('click', async function() {
            // Validate all dynamic form fields
            let isValid = true;
            let firstInvalidField = null;
            
            // Validate dynamic form fields from yellow cells
            formStructure.sections.forEach(section => {
                section.fields.forEach(field => {
                    if (field.required) {
                        const element = document.getElementById(field.id);
                        if (!element || !element.value || element.value.trim() === '') {
                            if (isValid) {
                                showAlert(`Please fill in: ${field.label}`, 'warning');
                                element?.focus();
                                firstInvalidField = element;
                            }
                            isValid = false;
                        }
                    }
                });
            });
            
            if (!isValid && firstInvalidField) {
                return;
            }
            
            // Validate material listing fields (from yellow cells)
            for (let idx = 0; idx < selectedMaterials.length; idx++) {
                const material = selectedMaterials[idx];
                
                // Validate each dynamic material field
                for (const field of materialListingFields) {
                    if (field.required) {
                        const elementId = `material_${idx}_${field.id}`;
                        const element = document.getElementById(elementId);
                        
                        if (!element) {
                            console.warn(`Field not found: ${elementId}`);
                            continue;
                        }
                        
                        if (field.type === 'file') {
                            // Validate file input
                            if (!element.files || !element.files[0]) {
                                showAlert(`Please upload ${field.label} for Material ${idx + 1} (${material.material_code})`, 'warning');
                                element?.focus();
                                return;
                            }
                        } else {
                            // Validate text/number/dropdown inputs
                            if (!element.value || element.value.trim() === '') {
                                showAlert(`Please fill in ${field.label} for Material ${idx + 1} (${material.material_code})`, 'warning');
                                element?.focus();
                                return;
                            }
                        }
                    }
                }
            }
            
            // Collect all data using FormData
            const formData = new FormData();
            formData.append('rfp_id', currentRfpId);
            
            // Collect dynamic form field values with metadata
            const dynamicFieldsData = {};
            formStructure.sections.forEach(section => {
                section.fields.forEach(field => {
                    const element = document.getElementById(field.id);
                    if (element) {
                        dynamicFieldsData[field.id] = {
                            value: element.value,
                            row: field.row,
                            col: field.col,
                            sheet_index: field.sheet_index,
                            sheet_name: field.sheet_name
                        };
                    }
                });
            });
            formData.append('dynamic_fields', JSON.stringify(dynamicFieldsData));
        
            // Add materials data with dynamic fields from yellow cells
            const materialsData = selectedMaterials.map((material, idx) => {
                const materialData = {
                    material_code: material.material_code,
                    name: material.name,
                    description: material.description,
                    is_matched: material.is_matched,
                    match_method: material.match_method,
                    reason: material.reason || '',
                    fields: {}  // Dynamic fields from yellow cells
                };
            
                // Collect all dynamic material listing field values
                materialListingFields.forEach(field => {
                    const elementId = `material_${idx}_${field.id}`;
                    const element = document.getElementById(elementId);
                    
                    if (element) {
                        if (field.type === 'file') {
                            // File fields are handled separately below
                            materialData.fields[field.label] = element.files[0]?.name || '';
                        } else {
                            materialData.fields[field.label] = element.value;
                        }
                    }
                });
                
                return materialData;
            });

            formData.append('materials_data', JSON.stringify(materialsData));
        
            // Add file attachments for each material (from yellow cells)
            for (let idx = 0; idx < selectedMaterials.length; idx++) {
                const material = selectedMaterials[idx];
                
                materialListingFields.forEach((field, fieldIdx) => {
                    if (field.type === 'file') {
                        const fileInput = document.getElementById(`material_${idx}_${field.id}`);
                        const file = fileInput?.files[0];
                        if (file) {
                            // Get file extension
                            const fileExt = file.name.substring(file.name.lastIndexOf('.'));
                            
                            // Generate filename: materialcode_fieldlabel.ext
                            const sanitizedLabel = field.label.replace(/[^a-zA-Z0-9]/g, '_');
                            const newFileName = `${material.material_code}_${sanitizedLabel}${fileExt}`;
                            
                            // Use a unique key for each file
                            formData.append(`material_${idx}_file_${fieldIdx}`, file, newFileName);
                        }
                    }
                });
            }
        
        // Show loading
        this.disabled = true;
        const submitButton = this; // Store reference before modal closes
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
        
        try {
            // Submit to backend (FormData automatically sets Content-Type with boundary)
            const response = await fetch('/dashboard/submit-rfp-final', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            console.log('📥 Backend response:', result);
            
            if (response.ok) {
                console.log('✅ Form data saved successfully!');
                console.log('📊 Response details:', {
                    ok: result.ok,
                    rfp_id: result.rfp_id,
                    sharepoint_upload: result.sharepoint_upload,
                    auto_submit: result.auto_submit
                });
                
                // Update listing button to show "Submitting..." if available
                if (currentSubmitButton) {
                    console.log('🔘 Updating listing button to show "Submitting to Portal..."');
                    currentSubmitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Submitting to Portal...';
                } else {
                    console.warn('⚠️ currentSubmitButton is not available');
                }
                
                // Show page loader BEFORE closing modal
                console.log('📺 Showing page loader');
                showPageLoader('Submitting RFP to portal...');
                
                // Properly close modal and remove backdrop
                modal.hide();
                setTimeout(() => {
                    const backdrop = document.querySelector('.modal-backdrop');
                    if (backdrop) {
                        backdrop.remove();
                    }
                    document.body.classList.remove('modal-open');
                    document.body.style.overflow = '';
                    document.body.style.paddingRight = '';
                }, 300);
                
                // Wait for submit automation to complete
                try {
                    localStorage.setItem('preferredRfpTab', 'saved-draft');
                } catch(_) {}
                
                // Small delay to ensure backend has set the state
                console.log('⏳ Waiting 1 second for backend to set state...');
                await new Promise(resolve => setTimeout(resolve, 1000));
                
                console.log('🔄 Starting to poll for automation completion...');
                console.log('🎯 Looking for: submit_running = true');
                
                // Custom polling loop that updates the listing button
                let pollAttempts = 0;
                const maxPollAttempts = 600; // 10 minutes
                let automationCompleted = false;
                
                while (pollAttempts < maxPollAttempts && !automationCompleted) {
                    pollAttempts++;
                    
                    try {
                        // Check automation status
                        const statusResponse = await fetch('/automation/status');
                        const statusData = await statusResponse.json();
                        
                        if (pollAttempts === 1 || pollAttempts === 2 || pollAttempts === 3) {
                            console.log(`📊 Automation status check #${pollAttempts}:`, statusData);
                            console.log(`🔍 submit_running = ${statusData.submit_running}`);
                        }
                        
                        // Check if submit automation is still running
                        if (statusData.submit_running) {
                            // Update listing button to show progress every second
                            if (currentSubmitButton) {
                                currentSubmitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Submitting... (' + Math.floor(pollAttempts) + 's)';
                            }
                            
                            // Update page loader message with time
                            const loaderMessage = document.getElementById('globalPageLoaderMessage');
                            if (loaderMessage) {
                                loaderMessage.textContent = `Submitting RFP to portal... (${pollAttempts}s)`;
                            }
                            
                            // Log progress every 10 seconds
                            if (pollAttempts % 10 === 0) {
                                console.log(`⏳ Still submitting... (${pollAttempts} seconds)`);
                            }
                            
                            // Wait 1 second before next check
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        } else {
                            // Automation completed
                            automationCompleted = true;
                            console.log(`✅ Automation completed successfully after ${pollAttempts} seconds!`);
                        }
                    } catch (error) {
                        console.error('Error checking automation status:', error);
                        // Continue polling even if one request fails
                        await new Promise(resolve => setTimeout(resolve, 1000));
                    }
                }
                
                if (!automationCompleted) {
                    console.warn('⚠️ Polling timeout reached after 10 minutes');
                    showAlert('Submission taking longer than expected. Please check status later.', 'warning');
                } else {
                    console.log('✅ Polling detected automation completion successfully');
                }
                
                // Check if we ever detected the automation running
                if (pollAttempts < 3) {
                    console.warn('⚠️ Automation completed very quickly (less than 3 seconds)');
                    console.warn('⚠️ This might indicate the automation did not start properly');
                }
                
                // Hide page loader
                console.log('📺 Hiding page loader');
                hidePageLoader();
                
                // Update listing button to show completion
                if (currentSubmitButton) {
                    currentSubmitButton.innerHTML = '<i class="fas fa-check-circle me-1"></i>Completed';
                    currentSubmitButton.classList.remove('btn-success');
                    currentSubmitButton.classList.add('btn-primary');
                }
                
                // Show success message
                showAlert('RFP submitted and saved as draft successfully!', 'success');
                
                // Refresh page with cache busting to saved-draft tab
                setTimeout(() => {
                    window.location.href = '/dashboard?refresh=' + Date.now();
                }, 1000);
            } else {
                throw new Error(result.detail || 'Failed to submit RFP');
            }
        } catch (error) {
            console.error('Submit error:', error);
            showAlert(`Error: ${error.message}`, 'danger');
            hidePageLoader();
            submitButton.disabled = false;
            submitButton.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Submit RFP';
            
            // Restore listing button state on error
            if (currentSubmitButton) {
                currentSubmitButton.innerHTML = '<i class="fas fa-paper-plane me-1"></i>Submit RFP';
                currentSubmitButton.disabled = false;
                currentSubmitButton = null;
            }
        }
        });
    
        // Add event listener to properly clean up on modal close
        const modalElement = document.getElementById('materialDetailsModal');
        modalElement.addEventListener('hidden.bs.modal', function() {
            // Remove backdrop if it exists
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        });
        
        modal.show();
    } catch (error) {
        console.error('Error loading dynamic form:', error);
        content.innerHTML = `
            <div class="alert alert-danger m-3">
                <h5><i class="fas fa-exclamation-triangle me-2"></i>Error Loading Form</h5>
                <p>${error.message}</p>
                <p class="mb-0">Please try again or contact support.</p>
            </div>
        `;
    }
}

/**
 * Get reason text from value
 */
function getReasonText(value) {
    const reasons = {
        'no_compatible_part': 'We don\'t carry a compatible part/material',
        'insufficient_quantity': 'We don\'t supply at the requested quantity',
        'discontinued': 'Discontinued Item',
        'full_capacity': 'We are currently at full capacity',
        'missing_info': 'Missing information / not enough information provided',
        'other': 'Other'
    };
    return reasons[value] || value || '(no value)';
}

/**
 * Initialize View Excel button handlers
 */
function initViewExcelButtons() {
    const viewExcelButtons = document.querySelectorAll('.view-excel-btn');
    
    viewExcelButtons.forEach(button => {
        // Prevent re-binding if already bound
        if (button.dataset.bound === '1') return;
        button.dataset.bound = '1';
        
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const rfpId = this.getAttribute('data-rfp-id');
            const company = this.getAttribute('data-company') || '';

            if (!rfpId) {
                showAlert('RFP ID not found', 'danger');
                return;
            }

            // Show loading state (button only, no global loader)
            const originalHTML = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Opening...';

            try {
                // Call the backend endpoint to get the unprotected Excel file
                const companyParam = company ? `?company=${encodeURIComponent(company)}` : '';
                const response = await fetch(`/dashboard/view-excel/${encodeURIComponent(rfpId)}${companyParam}`);
                
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.detail || 'Failed to load Excel file');
                }
                
                // Get the filename from Content-Disposition header if available
                const contentDisposition = response.headers.get('Content-Disposition');
                let filename = `${rfpId}_unprotected.xls`;
                if (contentDisposition) {
                    const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/);
                    if (filenameMatch) {
                        filename = filenameMatch[1];
                    }
                }
                
                // Create blob from response
                const blob = await response.blob();
                
                // Create download link and trigger download
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                
                // Cleanup
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                showAlert('Excel file downloaded! It should open automatically in Excel.', 'success');
            
            } catch (error) {
                console.error('View Excel error:', error);
                showAlert(`Error: ${error.message}`, 'danger');
            } finally {
                // Restore button state
                this.disabled = false;
                this.innerHTML = originalHTML;
            }
        });
    });
}

// Initialize Submit Draft buttons
function initSubmitDraftButtons() {
    const submitButtons = document.querySelectorAll('.submit-rfp-draft-btn');
    submitButtons.forEach(button => {
        if (button.dataset.bound === '1') return; // prevent re-binding
        button.dataset.bound = '1';
        button.addEventListener('click', async function(e) {
            e.preventDefault();
            const rfpId = this.getAttribute('data-rfp-id');
            if (!rfpId) {
                showAlert('RFP ID missing', 'danger');
                return;
            }
            // Confirm user intent
            const confirmed = window.confirm(`Are you sure you want to mark "${rfpId}" as Submitted?`);
            if (!confirmed) return;
            const originalHTML = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Submitting...';
            showPageLoader('Updating RFP status...');
            try {
                const res = await fetch('/dashboard/rfp/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rfp_id: rfpId, status: 'Submitted' })
                });
                const j = await res.json().catch(() => ({}));
                if (!res.ok) throw new Error(j.detail || j.message || 'Failed to update status');
                showAlert(`RFP "${rfpId}" marked as Submitted`, 'success');
                // On reload, automatically open Submitted tab
                try { localStorage.setItem('preferredRfpTab', 'submitted'); } catch(_) {}
                // Force backend cache refresh by using refresh=1
                showPageLoader('Refreshing data...');
                setTimeout(() => { window.location.href = '/dashboard?refresh=1'; }, 150);
            } catch (err) {
                showAlert(err.message || 'Error updating status', 'danger');
                hidePageLoader();
            } finally {
                this.disabled = false;
                this.innerHTML = originalHTML;
            }
        });
    });
}

// Load match percentages for all RFPs in the table (optimized batch request)
async function loadMatchPercentages() {
    const matchPercentageElements = document.querySelectorAll('.match-percentage');
    
    if (matchPercentageElements.length === 0) return;
    
    // Collect all RFP IDs
    const rfpIds = Array.from(matchPercentageElements)
        .map(el => el.getAttribute('data-rfp-id'))
        .filter(id => id);
    
    if (rfpIds.length === 0) return;
    
    try {
        // Single batch request for all RFPs
        const response = await fetch(`/dashboard/rfp/batch-match-percentages?rfp_ids=${rfpIds.join(',')}`);
        const data = await response.json();
        
        if (data.ok && data.results) {
            // Update all elements at once
            matchPercentageElements.forEach((element) => {
                const rfpId = element.getAttribute('data-rfp-id');
                const result = data.results[rfpId];
                
                if (result && result.match_percentage !== undefined) {
                    const percentage = result.match_percentage;
                    let badgeClass = 'bg-success';
                    if (percentage < 50) {
                        badgeClass = 'bg-danger';
                    } else if (percentage < 80) {
                        badgeClass = 'bg-warning';
                    }
                    
                    element.innerHTML = `<span class="badge ${badgeClass}">${percentage}%</span>`;
                } else {
                    element.innerHTML = '<span class="badge bg-secondary">N/A</span>';
                }
            });
        } else {
            // Fallback: show error for all
            matchPercentageElements.forEach(el => {
                el.innerHTML = '<span class="badge bg-secondary">Error</span>';
            });
        }
    } catch (error) {
        console.error('Error loading match percentages:', error);
        matchPercentageElements.forEach(el => {
            el.innerHTML = '<span class="badge bg-secondary">Error</span>';
        });
    }
}

// Initialize View Excel buttons when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initViewExcelButtons();
    initSubmitRfpButtons();
    
    // Load match percentages
    loadMatchPercentages();
    
    // Re-initialize when tab changes (in case content is loaded dynamically)
    const rfpTabButtons = document.querySelectorAll('#rfpTab button[data-bs-toggle="tab"]');
    rfpTabButtons.forEach(tabButton => {
        tabButton.addEventListener('shown.bs.tab', function() {
            initViewExcelButtons();
            initSubmitRfpButtons();
            initSubmitDraftButtons();
            // Reload match percentages when tab changes
            setTimeout(() => loadMatchPercentages(), 100);
        });
    });
    initSubmitDraftButtons();

    // Restore preferred RFP tab after hard reload (e.g., after status change)
    try {
        const preferred = localStorage.getItem('preferredRfpTab');
        if (preferred) {
            const tabId = preferred === 'submitted' ? 'submitted-tab' : preferred === 'open' ? 'open-tab' : preferred === 'declined' ? 'declined-tab' : preferred === 'saved-draft' ? 'saved-draft-tab' : null;
            if (tabId) {
                const btn = document.getElementById(tabId);
                if (btn) btn.click();
            }
            localStorage.removeItem('preferredRfpTab');
        }
    } catch (_) {}

    // Hide loader once DOM is ready (handled in unified loader section)
});

// ================= Global Page Loader (Unified) =================
// Unified loader function that works across all pages
function showPageLoader(message = 'Loading...') {
    const el = document.getElementById('globalPageLoader');
    const msgEl = document.getElementById('globalPageLoaderMessage');
    if (el) {
        if (msgEl) msgEl.textContent = message;
        el.classList.remove('d-none');
    }
    // Also support legacy pageLoader for user-management page
    const legacyLoader = document.getElementById('pageLoader');
    if (legacyLoader) {
        const legacyMsg = legacyLoader.querySelector('p');
        if (legacyMsg) legacyMsg.textContent = message;
        legacyLoader.style.display = 'flex';
    }
}

function hidePageLoader() {
    const el = document.getElementById('globalPageLoader');
    if (el) el.classList.add('d-none');
    // Also hide legacy loader
    const legacyLoader = document.getElementById('pageLoader');
    if (legacyLoader) legacyLoader.style.display = 'none';
}

// Alias for backward compatibility
function setGlobalLoaderVisible(visible, message = 'Loading...') {
    if (visible) {
        showPageLoader(message);
    } else {
        hidePageLoader();
    }
}

// Show loader on navigation away
window.addEventListener('beforeunload', function() {
    showPageLoader('Navigating...');
});

// Show loader on initial page load
if (document.readyState === 'loading') {
    showPageLoader('Loading page...');
}

// Hide loader once DOM is fully loaded, but check if automation is running first
document.addEventListener('DOMContentLoaded', async function() {
    // Check if any automation is running
    try {
        const response = await fetch((window.APP_CONFIG && APP_CONFIG.API_AUTOMATION_STATUS) || '/automation/status');
        const data = await response.json();
        
        // Check each automation type
        if (data.submit_running) {
            // Submit automation is running, keep loader visible and poll
            console.log('✅ Submit automation detected running on page load');
            showPageLoader('Submitting RFP to portal...');
            
            // Set preferred tab for after completion (saved-draft tab)
            try {
                localStorage.setItem('preferredRfpTab', 'saved-draft');
            } catch(_) {}
            
            // Poll until automation completes
            await pollAutomationUntilIdle('submit', { autoRefresh: false });
            
            // Automation completed, refresh to show updated data
            console.log('✅ Submit automation completed, refreshing...');
            setTimeout(() => {
                window.location.href = '/dashboard?refresh=' + Date.now();
            }, 1000);
        } else if (data.download_running) {
            // Download automation is running
            console.log('✅ Download automation detected running on page load');
            showPageLoader('Downloading RFPs...');
            await pollAutomationUntilIdle('download', { autoRefresh: false });
            console.log('✅ Download automation completed, refreshing...');
            setTimeout(() => {
                window.location.href = '/dashboard?refresh=' + Date.now();
            }, 1000);
        } else if (data.decline_running) {
            // Decline automation is running
            console.log('✅ Decline automation detected running on page load');
            showPageLoader('Declining RFP...');
            try {
                localStorage.setItem('preferredRfpTab', 'declined');
            } catch(_) {}
            await pollAutomationUntilIdle('decline', { autoRefresh: false });
            console.log('✅ Decline automation completed, refreshing...');
            setTimeout(() => {
                window.location.href = '/dashboard?refresh=' + Date.now();
            }, 1000);
        } else if (data.sync_running) {
            // Sync automation is running
            console.log('✅ Sync automation detected running on page load');
            showPageLoader('Syncing portal data...');
            await pollAutomationUntilIdle('sync', { autoRefresh: false });
            console.log('✅ Sync automation completed, refreshing...');
            setTimeout(() => {
                window.location.href = '/dashboard?refresh=' + Date.now();
            }, 1000);
        } else {
            // No automation running, hide loader normally
            setTimeout(() => hidePageLoader(), 100);
        }
    } catch (error) {
        console.error('Error checking automation status:', error);
        // On error, hide loader normally
        setTimeout(() => hidePageLoader(), 100);
    }
});

// Apply loader to all navigation links
document.addEventListener('DOMContentLoaded', function() {
    // Intercept all anchor links for navigation
    document.querySelectorAll('a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"]):not([href^="tel:"])').forEach(link => {
        link.addEventListener('click', function(e) {
            // Skip if it's a modal trigger or dropdown
            if (this.getAttribute('data-bs-toggle') || this.getAttribute('data-bs-target') || this.closest('.dropdown-menu')) {
                return;
            }
            // Skip RFP external links (Ariba portal links) - they open in new tab and don't need loader
            if (this.getAttribute('target') === '_blank' && (this.getAttribute('rel') === 'noopener noreferrer' || this.title === 'Open RFP in Ariba Portal')) {
                return;
            }
            // Skip Portal button links in RFP details page
            if (this.classList.contains('btn') && this.textContent.trim().includes('Portal')) {
                return;
            }
            // Show loader for navigation
            showPageLoader('Loading page...');
        });
    });
    
    // Check submit button status on page load
    checkAllSubmitButtonsStatus();
    
    // Poll submit button status every 3 seconds
    setInterval(checkAllSubmitButtonsStatus, 3000);
});

/**
 * Check status of all submit buttons and update loader state
 */
async function checkAllSubmitButtonsStatus() {
    const submitButtons = document.querySelectorAll('.submit-rfp-btn');
    
    for (const button of submitButtons) {
        const rfpId = button.getAttribute('data-rfp-id');
        if (!rfpId) continue;
        
        try {
            const response = await fetch(`/dashboard/rfp-status/${encodeURIComponent(rfpId)}`);
            const data = await response.json();
            
            if (data.ok) {
                const btnText = button.querySelector('.btn-text');
                const btnLoading = button.querySelector('.btn-loading');
                
                if (data.is_submitting) {
                    // Show loading state
                    if (btnText && btnLoading) {
                        btnText.classList.add('d-none');
                        btnLoading.classList.remove('d-none');
                    }
                    button.disabled = true;
                } else {
                    // Hide loading state
                    if (btnText && btnLoading) {
                        btnText.classList.remove('d-none');
                        btnLoading.classList.add('d-none');
                    }
                    button.disabled = false;
                }
            }
        } catch (error) {
            console.error(`Error checking status for RFP ${rfpId}:`, error);
            // On error, assume not submitting and enable button
            const btnText = button.querySelector('.btn-text');
            const btnLoading = button.querySelector('.btn-loading');
            if (btnText && btnLoading) {
                btnText.classList.remove('d-none');
                btnLoading.classList.add('d-none');
            }
            button.disabled = false;
        }
    }
}

