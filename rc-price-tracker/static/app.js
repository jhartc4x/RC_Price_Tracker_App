(function () {
  function activateReveal() {
    const elements = document.querySelectorAll('.reveal');
    if (!('IntersectionObserver' in window)) {
      elements.forEach((el) => el.classList.add('in'));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );

    elements.forEach((el) => observer.observe(el));
  }

  function hookDynamicRows() {
    document.querySelectorAll('.add-row').forEach((button) => {
      button.addEventListener('click', () => {
        const target = button.getAttribute('data-target');
        const container = document.getElementById(target + '-rows');
        const template = document.getElementById('template-' + target.slice(0, -1) + '-row');
        if (!container || !template) {
          return;
        }
        const clone = template.content.cloneNode(true);
        container.appendChild(clone);
      });
    });

    document.addEventListener('click', (event) => {
      const button = event.target.closest('.remove-row');
      if (!button) {
        return;
      }
      const card = button.closest('.row-card');
      if (card) {
        card.remove();
      }
    });
  }

  function hookStatusPolling() {
    const statusRoot = document.querySelector('[data-run-status]');
    if (!statusRoot) {
      return;
    }

    const valueEl = document.getElementById('run-status-value');
    const metaEl = document.getElementById('run-status-meta');
    const messageEl = document.getElementById('run-status-message');

    const applyState = (state) => {
      if (!valueEl || !metaEl || !messageEl) {
        return;
      }
      valueEl.textContent = state.status || 'unknown';
      metaEl.textContent = 'Module: ' + (state.module || 'all') + (state.started_at ? ' | Started: ' + state.started_at : '');
      messageEl.textContent = state.message || '';
    };

    const poll = async () => {
      try {
        const response = await fetch('/api/run-status', { cache: 'no-store' });
        if (!response.ok) {
          return;
        }
        const state = await response.json();
        applyState(state);
      } catch (error) {
        // Silent failure to avoid distracting users.
      }
    };

    poll();
    window.setInterval(poll, 5000);
  }

  function hookRunLogModal() {
    const openButton = document.getElementById('open-run-log');
    const modal = document.getElementById('run-log-modal');
    const body = document.getElementById('run-log-body');
    if (!openButton || !modal || !body) {
      return;
    }

    const renderRows = (logs) => {
      if (!Array.isArray(logs) || logs.length === 0) {
        body.innerHTML = '<tr><td colspan=\"4\">No run logs yet.</td></tr>';
        return;
      }

      body.innerHTML = logs
        .map((row) => {
          return '<tr>' +
            '<td>' + (row.run_date || '-') + '</td>' +
            '<td>' + (row.module || '-') + '</td>' +
            '<td>' + (row.status || '-') + '</td>' +
            '<td>' + (row.message || '-') + '</td>' +
            '</tr>';
        })
        .join('');
    };

    const openModal = async () => {
      modal.hidden = false;
      body.innerHTML = '<tr><td colspan=\"4\">Loading run logs...</td></tr>';
      try {
        const response = await fetch('/api/run-log', { cache: 'no-store' });
        if (!response.ok) {
          body.innerHTML = '<tr><td colspan=\"4\">Unable to load run logs.</td></tr>';
          return;
        }
        const payload = await response.json();
        renderRows(payload.logs || []);
      } catch (error) {
        body.innerHTML = '<tr><td colspan=\"4\">Unable to load run logs.</td></tr>';
      }
    };

    const closeModal = () => {
      modal.hidden = true;
    };

    openButton.addEventListener('click', openModal);
    modal.querySelectorAll('[data-close-modal]').forEach((btn) => {
      btn.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !modal.hidden) {
        closeModal();
      }
    });
  }

  function hookAddonsPage() {
    const shipSelect = document.getElementById('filter-ship');
    const dateInput = document.getElementById('filter-date');
    const goBtn = document.getElementById('filter-go');
    const goBtnText = document.getElementById('filter-go-text');
    const resultsSection = document.getElementById('addons-results');

    if (!shipSelect || !dateInput || !goBtn || !resultsSection) {
      return; // Not on addons page
    }

    // Fetch all ships for dropdown
    fetch('/api/ships', { cache: 'no-store' })
      .then(r => r.json())
      .then(data => {
        const ships = data.ships || [];
        shipSelect.innerHTML = '<option value="">Select a ship</option>';
        ships.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.ship_code;
          opt.textContent = s.ship_name + ' (' + s.ship_code + ')';
          shipSelect.appendChild(opt);
        });
      })
      .catch(() => {
        shipSelect.innerHTML = '<option value="">No ships found</option>';
      });

    // Enable/disable go button based on both fields
    function updateGoButton() {
      goBtn.disabled = !shipSelect.value || !dateInput.value;
    }
    shipSelect.addEventListener('change', updateGoButton);
    dateInput.addEventListener('input', updateGoButton);

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const panel = document.getElementById('panel-' + btn.getAttribute('data-tab'));
        if (panel) panel.classList.add('active');
      });
    });

    // Fetch and render addons
    goBtn.addEventListener('click', () => {
      const ship = shipSelect.value;
      const rawDate = dateInput.value;
      if (!ship || !rawDate) return;

      // Convert YYYY-MM-DD to YYYYMMDD for the API
      const sailDate = rawDate.replace(/-/g, '');

      resultsSection.style.display = 'block';
      const purchasedBody = document.getElementById('purchased-body');
      const availableBody = document.getElementById('available-body');
      const summaryDiv = document.getElementById('addons-summary');

      // Loading state
      goBtn.disabled = true;
      goBtnText.textContent = 'Loading...';
      purchasedBody.innerHTML = '<tr><td colspan="5" class="addons-loading">Fetching from Royal Caribbean...</td></tr>';
      availableBody.innerHTML = '<tr><td colspan="3" class="addons-loading">Fetching from Royal Caribbean...</td></tr>';
      summaryDiv.innerHTML = '<div class="addons-loading">Querying RC catalog (this may take a few seconds)...</div>';

      fetch('/api/addons?ship_code=' + encodeURIComponent(ship) + '&sail_date=' + encodeURIComponent(sailDate), { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
          goBtn.disabled = false;
          goBtnText.textContent = 'View Add-ons';

          const purchased = data.purchased || [];
          const available = data.available || [];
          const source = data.source || 'unknown';
          const error = data.error || null;
          const diag = data.diagnostics || {};

          // Summary
          const totalSavings = purchased.reduce((sum, item) => sum + (item.savings > 0 ? item.savings : 0), 0);
          let sourceLabel = source === 'live' ? '🟢 Live' : (source === 'db' ? '🔵 Cached' : '⚪ No data');
          if (error && source !== 'live') {
            sourceLabel += ' ⚠️';
          }

          let summaryHtml =
            '<div class="summary-item"><span class="summary-label">Purchased</span><span class="summary-value">' + purchased.length + '</span></div>' +
            '<div class="summary-item"><span class="summary-label">Available</span><span class="summary-value">' + available.length + '</span></div>' +
            '<div class="summary-item"><span class="summary-label">Total Savings</span><span class="summary-value savings">$' + totalSavings.toFixed(2) + '</span></div>' +
            '<div class="summary-item"><span class="summary-label">Source</span><span class="summary-value" style="font-size:0.95rem;">' + sourceLabel + '</span></div>';

          // Show error details if present
          if (error) {
            summaryHtml += '<div style="grid-column: 1 / -1; margin-top: 12px; padding: 12px 16px; ' +
              'background: rgba(255,160,0,0.1); border: 1px solid rgba(255,160,0,0.3); border-radius: 8px; ' +
              'color: var(--text-secondary); font-size: 0.9rem; line-height: 1.5;">' +
              '<strong style="color: #ffa000;">⚠ API Note:</strong> ' + escapeHtml(error) + '</div>';
          }

          // Show diagnostics if API was called
          if (diag.categories && Object.keys(diag.categories).length > 0) {
            let diagHtml = '<div style="grid-column: 1 / -1; margin-top: 8px; padding: 10px 14px; ' +
              'background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; ' +
              'font-size: 0.85rem; color: var(--text-muted);">' +
              '<details><summary style="cursor:pointer; color: var(--text-secondary); font-weight: 500;">API Diagnostics</summary>' +
              '<div style="margin-top: 8px;">';

            diagHtml += '<div style="margin-bottom: 6px;">Auth: <strong>' + escapeHtml(diag.auth || 'unknown') + '</strong>' +
              ' · Booking: ' + (diag.has_booking ? '✅' : '❌') +
              ' · Reservation: ' + (diag.has_reservation_id ? '✅' : '❌') +
              ' · Passenger: ' + (diag.has_passenger_id ? '✅' : '❌') + '</div>';

            for (const [catName, catInfo] of Object.entries(diag.categories)) {
              const statusCode = catInfo.status || 'N/A';
              const statusColor = statusCode === 200 ? '#4caf50' : (statusCode >= 400 ? '#ff5252' : '#ffa000');
              const methodLabel = catInfo.method || '?';
              const prodCount = catInfo.products != null ? (' · ' + catInfo.products + ' products') : '';
              diagHtml += '<div style="padding: 2px 0;">' +
                '<span style="color:' + statusColor + '; font-weight: 600;">' + statusCode + '</span> ' +
                '<span style="opacity:0.6;">[' + methodLabel + ']</span> ' +
                escapeHtml(catName) + prodCount + '</div>';
            }

            diagHtml += '</div></details></div>';
            summaryHtml += diagHtml;
          }

          summaryDiv.innerHTML = summaryHtml;

          // Purchased table
          if (purchased.length === 0) {
            purchasedBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-muted); padding: 24px;">No purchased add-ons found for this sailing.</td></tr>';
          } else {
            purchasedBody.innerHTML = purchased.map(item => {
              const paid = item.paid_price != null ? '$' + Number(item.paid_price).toFixed(2) : '-';
              const current = '$' + Number(item.current_price).toFixed(2);
              let savingsHtml = '<span class="savings-badge neutral">-</span>';
              if (item.savings != null && item.savings > 0) {
                savingsHtml = '<span class="savings-badge positive">-$' + item.savings.toFixed(2) + '</span>';
              } else if (item.savings != null && item.savings < 0) {
                savingsHtml = '<span class="savings-badge negative">+$' + Math.abs(item.savings).toFixed(2) + '</span>';
              }

              const name = escapeHtml(item.product_name || 'Unknown');
              const guest = escapeHtml(item.passenger_name || '-');

              return '<tr>' +
                '<td><strong>' + name + '</strong></td>' +
                '<td>' + guest + '</td>' +
                '<td>' + paid + '</td>' +
                '<td>' + current + '</td>' +
                '<td>' + savingsHtml + '</td>' +
                '</tr>';
            }).join('');
          }

          // Available table
          if (available.length === 0) {
            let msg = 'No available add-ons found for this sailing.';
            if (error) {
              msg += '<br><small style="color: var(--text-muted); font-weight: normal;">' + escapeHtml(error) + '</small>';
            }
            availableBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--text-muted); padding: 24px;">' + msg + '</td></tr>';
          } else {
            availableBody.innerHTML = available.map(item => {
              const category = escapeHtml(item.category || '-');
              const name = escapeHtml(item.product_name || 'Unknown');

              // Regular (shipboard) price
              let regularHtml = '-';
              if (item.base_price != null) {
                regularHtml = '$' + Number(item.base_price).toFixed(2);
              }

              // Current (promotional) price
              let currentHtml = '<span style="color: var(--text-muted);">-</span>';
              if (item.current_price != null) {
                const hasDiscount = item.base_price != null && item.base_price > item.current_price;
                currentHtml = '<span style="font-weight:600; color: ' + (hasDiscount ? '#4caf50' : 'inherit') + ';">$' +
                  Number(item.current_price).toFixed(2) + '</span>';
                if (hasDiscount) {
                  regularHtml = '<span style="text-decoration: line-through; opacity: 0.5;">$' +
                    Number(item.base_price).toFixed(2) + '</span>';
                  const pctOff = Math.round((1 - item.current_price / item.base_price) * 100);
                  if (pctOff > 0) {
                    currentHtml += ' <span style="font-size:0.8rem; color:#4caf50;">(' + pctOff + '% off)</span>';
                  }
                }
              }

              return '<tr>' +
                '<td><strong>' + name + '</strong></td>' +
                '<td>' + category + '</td>' +
                '<td>' + regularHtml + '</td>' +
                '<td>' + currentHtml + '</td>' +
                '</tr>';
            }).join('');
          }
        })
        .catch(() => {
          goBtn.disabled = false;
          goBtnText.textContent = 'View Add-ons';
          purchasedBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--status-err);">Failed to load add-ons.</td></tr>';
          availableBody.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--status-err);">Failed to load add-ons.</td></tr>';
        });
    });
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  activateReveal();
  hookDynamicRows();
  hookStatusPolling();
  hookRunLogModal();
  hookAddonsPage();
})();
