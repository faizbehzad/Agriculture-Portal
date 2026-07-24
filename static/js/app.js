/* Agricultural Engineering Portal - Core Application JS */

document.addEventListener('DOMContentLoaded', () => {
  initCNICFormatter();
  initPhoneRepeater();
  initViewToggle();
  initEquipmentCalculators();
  initToastManager();
});

// Toast Manager
function showToast(message, type = 'success') {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  
  const toast = document.createElement('div');
  toast.className = `toast ${type === 'error' ? 'toast-error' : ''}`;
  toast.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      ${type === 'error' 
        ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
        : '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'}
    </svg>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// CNIC Auto-Formatter & Farmer ID Auto-Derive
function initCNICFormatter() {
  const cnicInput = document.getElementById('cnic');
  const farmerIdInput = document.getElementById('farmer_id');
  
  if (!cnicInput) return;
  
  cnicInput.addEventListener('input', (e) => {
    let value = e.target.value.replace(/\D/g, ''); // strip non-digits
    if (value.length > 13) value = value.substring(0, 13);
    
    let formatted = value;
    if (value.length > 5 && value.length <= 12) {
      formatted = `${value.substring(0, 5)}-${value.substring(5)}`;
    } else if (value.length > 12) {
      formatted = `${value.substring(0, 5)}-${value.substring(5, 12)}-${value.substring(12)}`;
    }
    
    e.target.value = formatted;
    
    // Auto-derive Farmer ID (middle 7 digits)
    if (value.length >= 12 && farmerIdInput) {
      const middleSeven = value.substring(5, 12);
      farmerIdInput.value = middleSeven;
    } else if (farmerIdInput && !farmerIdInput.hasAttribute('data-manual')) {
      farmerIdInput.value = '';
    }
  });
}

// Phone Repeater
function initPhoneRepeater() {
  const addBtn = document.getElementById('add-phone-btn');
  const container = document.getElementById('phone-repeater-container');
  
  if (!addBtn || !container) return;
  
  addBtn.addEventListener('click', () => {
    const count = container.children.length;
    const div = document.createElement('div');
    div.className = 'form-row phone-row mb-2';
    div.innerHTML = `
      <div class="form-group" style="flex: 1;">
        <select name="phone_provider[]" class="form-control">
          <option value="Jazz">Jazz</option>
          <option value="Telenor">Telenor</option>
          <option value="Zong">Zong</option>
          <option value="Ufone">Ufone</option>
          <option value="Onic">Onic</option>
          <option value="PTCL">PTCL</option>
          <option value="Other">Other</option>
        </select>
      </div>
      <div class="form-group" style="flex: 2;">
        <input type="text" name="phone_number[]" class="form-control" placeholder="03001234567">
      </div>
      <div class="form-group" style="width: auto; display: flex; align-items: center;">
        <label class="btn-icon" style="cursor: pointer;" title="Primary Phone">
          <input type="radio" name="primary_phone_index" value="${count}"> Primary
        </label>
        <button type="button" class="btn btn-icon text-danger remove-phone-btn" title="Remove">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
    `;
    container.appendChild(div);
    
    div.querySelector('.remove-phone-btn').addEventListener('click', () => {
      div.remove();
    });
  });

  container.querySelectorAll('.remove-phone-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.target.closest('.phone-row').remove();
    });
  });
}

// Cookie-Persisted Farmers Grid/List Toggle
function initViewToggle() {
  const toggleGrid = document.getElementById('view-toggle-grid');
  const toggleList = document.getElementById('view-toggle-list');
  const gridContainer = document.getElementById('farmers-grid-view');
  const listContainer = document.getElementById('farmers-list-view');
  
  if (!toggleGrid || !toggleList || !gridContainer || !listContainer) return;

  function setView(mode) {
    if (mode === 'grid') {
      gridContainer.style.display = 'grid';
      listContainer.style.display = 'none';
      toggleGrid.classList.add('btn-primary');
      toggleGrid.classList.remove('btn-secondary');
      toggleList.classList.add('btn-secondary');
      toggleList.classList.remove('btn-primary');
    } else {
      gridContainer.style.display = 'none';
      listContainer.style.display = 'block';
      toggleList.classList.add('btn-primary');
      toggleList.classList.remove('btn-secondary');
      toggleGrid.classList.add('btn-secondary');
      toggleGrid.classList.remove('btn-primary');
    }
    document.cookie = `farmer_view_mode=${mode}; path=/; max-age=31536000`;
  }

  toggleGrid.addEventListener('click', () => setView('grid'));
  toggleList.addEventListener('click', () => setView('list'));

  // Read initial cookie
  const match = document.cookie.match(/farmer_view_mode=(grid|list)/);
  if (match) {
    setView(match[1]);
  }
}

// Equipment 60/40 Split Calculation for Program Creation
function initEquipmentCalculators() {
  const container = document.getElementById('equipment-repeater-container');
  const addBtn = document.getElementById('add-equipment-btn');
  
  if (!container || !addBtn) return;
  
  function bindCalc(row) {
    const priceInput = row.querySelector('.actual-price');
    const subsidyInput = row.querySelector('.subsidy-pct');
    const govtSpan = row.querySelector('.govt-share');
    const farmerSpan = row.querySelector('.farmer-share');
    
    function recalculate() {
      const price = parseFloat(priceInput.value) || 0;
      const pct = parseFloat(subsidyInput.value) || 60;
      const govt = (price * (pct / 100)).toFixed(2);
      const farmer = (price - govt).toFixed(2);
      if (govtSpan) govtSpan.textContent = `PKR ${govt}`;
      if (farmerSpan) farmerSpan.textContent = `PKR ${farmer}`;
    }

    if (priceInput) priceInput.addEventListener('input', recalculate);
    if (subsidyInput) subsidyInput.addEventListener('input', recalculate);
  }

  container.querySelectorAll('.equipment-row').forEach(bindCalc);

  addBtn.addEventListener('click', () => {
    const row = document.createElement('div');
    row.className = 'form-row equipment-row mb-3 p-3 card';
    row.innerHTML = `
      <div class="form-group" style="flex: 2;">
        <label class="form-label">Equipment Name</label>
        <input type="text" name="equipment_name[]" class="form-control" placeholder="e.g. Laser Land Leveler" required>
      </div>
      <div class="form-group" style="flex: 1;">
        <label class="form-label">Actual Price (PKR)</label>
        <input type="number" step="0.01" name="actual_price[]" class="form-control actual-price" placeholder="0.00" required>
      </div>
      <div class="form-group" style="flex: 1;">
        <label class="form-label">Subsidy %</label>
        <input type="number" step="0.01" name="subsidy_pct[]" class="form-control subsidy-pct" value="60.00">
      </div>
      <div class="form-group" style="flex: 1; font-size: 0.82rem;">
        <label class="form-label">Split Preview</label>
        <div>Govt: <strong class="govt-share" style="color:var(--forest-700)">PKR 0.00</strong></div>
        <div>Farmer: <strong class="farmer-share" style="color:var(--leaf-600)">PKR 0.00</strong></div>
      </div>
      <div style="display:flex; align-items:flex-end;">
        <button type="button" class="btn btn-icon text-danger remove-eq-btn"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
      </div>
    `;
    container.appendChild(row);
    bindCalc(row);
    row.querySelector('.remove-eq-btn').addEventListener('click', () => row.remove());
  });
}

// Modal helper
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.add('active');
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) modal.classList.remove('active');
}
