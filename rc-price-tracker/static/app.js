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
    const valueModalEl = document.getElementById('run-status-value-modal');
    const metaModalEl = document.getElementById('run-status-meta-modal');
    const messageModalEl = document.getElementById('run-status-message-modal');

    const applyState = (state) => {
      if (!valueEl || !metaEl || !messageEl) {
        return;
      }
      const statusText = state.status || 'unknown';
      const metaText = 'Module: ' + (state.module || 'all') + (state.started_at ? ' | Started: ' + state.started_at : '');
      const msgText = state.message || '';

      valueEl.textContent = statusText;
      metaEl.textContent = metaText;
      messageEl.textContent = msgText;

      if (valueModalEl) valueModalEl.textContent = statusText;
      if (metaModalEl) metaModalEl.textContent = metaText;
      if (messageModalEl) messageModalEl.textContent = msgText;
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

  function hookGenericModal() {
    document.querySelectorAll('[data-open-modal]').forEach((button) => {
      button.addEventListener('click', () => {
        const id = button.getAttribute('data-open-modal');
        const modal = document.getElementById(id);
        if (modal) {
          modal.hidden = false;
        }
      });
    });

    document.querySelectorAll('[data-close-modal]').forEach((button) => {
      button.addEventListener('click', () => {
        const modal = button.closest('.modal');
        if (modal) {
          modal.hidden = true;
        }
      });
    });
  }

  function hookAddonsPage() {
    const shipSelect = document.getElementById('filter-ship');
    const dateSelect = document.getElementById('filter-date');
    const goBtn = document.getElementById('filter-go');
    const goBtnText = document.getElementById('filter-go-text');
    const resultsSection = document.getElementById('addons-results');

    if (!shipSelect || !dateSelect || !goBtn || !resultsSection) {
      return; // Not on addons page
    }

    // Helper to check valid state
    const validateForm = () => {
      if (shipSelect.value && dateSelect.value) {
        goBtn.disabled = false;
      } else {
        goBtn.disabled = true;
      }
    };

    // Fetch all ships for dropdown
    fetch('/api/ships', { cache: 'no-store' })
      .then(r => r.json())
      .then(data => {
        const ships = data.ships || [];
        shipSelect.innerHTML = '<option value="">Select a Ship</option>';
        ships.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.ship_code;
          opt.textContent = s.ship_name;
          shipSelect.appendChild(opt);
        });
      })
      .catch(() => {
        shipSelect.innerHTML = '<option value="">Failed to load ships</option>';
      });

    // Handle ship change -> fetch sailings
    shipSelect.addEventListener('change', () => {
      const shipCode = shipSelect.value;

      // Reset date dropdown
      dateSelect.innerHTML = '<option value="">Select a Ship First</option>';
      dateSelect.disabled = true;
      goBtn.disabled = true;

      if (!shipCode) return;

      dateSelect.innerHTML = '<option value="">Loading sailings...</option>';

      fetch('/api/sailings?ship_code=' + encodeURIComponent(shipCode), { cache: 'no-store' })
        .then(r => r.json())
        .then(data => {
          const sailings = data.sailings || [];
          if (sailings.length === 0) {
            dateSelect.innerHTML = '<option value="">No sailings found</option>';
            return;
          }

          dateSelect.innerHTML = '<option value="">Select Sail Date</option>';
          sailings.forEach(dateStr => {
            // Format date nicely (YYYY-MM-DD -> Month DD, YYYY)
            const d = new Date(dateStr + 'T12:00:00');
            const label = d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });

            const opt = document.createElement('option');
            opt.value = dateStr; // Keep YYYY-MM-DD for API
            opt.textContent = label;
            dateSelect.appendChild(opt);
          });

          dateSelect.disabled = false;
        })
        .catch(err => {
          console.error(err);
          dateSelect.innerHTML = '<option value="">Error loading dates</option>';
        });
    });

    // Handle date change -> enable button
    dateSelect.addEventListener('change', validateForm);

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
      const rawDate = dateSelect.value;
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
              'background: rgba(217,144,26,0.1); border: 1px solid rgba(217,144,26,0.35); border-radius: 8px; ' +
              'color: var(--text); font-size: 0.9rem; line-height: 1.5;">' +
              '<strong style="color: #d9901a;">⚠ API Note:</strong> ' + escapeHtml(error) + '</div>';
          }

          // Show diagnostics if API was called
          if (diag.categories && Object.keys(diag.categories).length > 0) {
            let diagHtml = '<div style="grid-column: 1 / -1; margin-top: 8px; padding: 10px 14px; ' +
              'background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; ' +
              'font-size: 0.85rem; color: var(--text-muted);">' +
              '<details><summary style="cursor:pointer; color: var(--text); font-weight: 600;">API Diagnostics</summary>' +
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
          purchasedBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--err);">Failed to load add-ons.</td></tr>';
          availableBody.innerHTML = '<tr><td colspan="4" style="text-align:center; color: var(--err);">Failed to load add-ons.</td></tr>';
        });
    });
  }

  function hookCruisesPage() {
    const shipSelect = document.getElementById('cruise-ship');
    const portSelect = document.getElementById('cruise-port');
    const dateInput = document.getElementById('cruise-month');
    const guestsInput = document.getElementById('cruise-guests');
    const maxPriceInput = document.getElementById('cruise-max-price');
    const searchBtn = document.getElementById('cruise-search-btn');
    const searchBtnText = document.getElementById('cruise-search-text');
    const resultsContainer = document.getElementById('cruises-results'); // Section
    const summaryDiv = document.getElementById('cruises-summary');
    const gridDiv = document.getElementById('cruises-grid');

    if (!shipSelect || !searchBtn) return; // Not on cruises page

    // 1. Populate Ships (with retry)
    const loadShips = () => {
      if (shipSelect.options.length > 1) return; // Already loaded

      fetch('/api/ships')
        .then(r => r.json())
        .then(data => {
          if (data.ships) {
            shipSelect.innerHTML = '<option value="">Any Ship</option>';
            data.ships.forEach(s => {
              const opt = document.createElement('option');
              opt.value = s.ship_code;
              opt.textContent = s.ship_name;
              shipSelect.appendChild(opt);
            });
          }
        })
        .catch(console.error);
    };

    loadShips();
    // Retry once in case of race condition
    setTimeout(loadShips, 1000);

    // 2. Search Handler
    searchBtn.addEventListener('click', () => {
      // Validate - require at least one filter?
      const shipCode = shipSelect.value;
      const portCode = portSelect.value;
      const dateRange = dateInput.value;

      if (!shipCode && !portCode && !dateRange) {
        alert("Please select at least a Ship, Port, or Month.");
        return;
      }

      // UI Loading
      searchBtn.disabled = true;
      searchBtnText.textContent = 'Searching...';
      resultsContainer.style.display = 'block';
      summaryDiv.innerHTML = '<span style="color:var(--text-muted)">Loading sailings...</span>';
      gridDiv.innerHTML = '<div style="grid-column: 1/-1; text-align:center; padding:40px;"><div class="spinner"></div></div>';

      // Build Params
      const params = new URLSearchParams();
      if (shipCode) params.append('ship_code', shipCode);
      if (portCode) params.append('port_code', portCode);
      if (dateRange) params.append('date_range', dateRange); // YYYY-MM
      params.append('guests', guestsInput.value || '2');
      if (maxPriceInput.value) params.append('max_price', maxPriceInput.value);

      // Fetch
      fetch('/api/cruises?' + params.toString())
        .then(r => r.json())
        .then(data => {
          searchBtn.disabled = false;
          searchBtnText.textContent = 'Search';

          if (data.error) {
            summaryDiv.innerHTML = `<span style="color:var(--err)">Error: ${data.error}</span>`;
            gridDiv.innerHTML = '';
            return;
          }

          const cruises = data.cruises || [];
          if (cruises.length === 0) {
            summaryDiv.innerHTML = 'No scheduled cruises found for these filters.';
            gridDiv.innerHTML = '';
            return;
          }

          summaryDiv.innerHTML = `Found <strong>${cruises.length}</strong> sailings. showing lowest price per person.`;

          gridDiv.innerHTML = cruises.map(c => {
            // Logic to format date nicely
            let dateStr = c.sail_date; // YYYY-MM-DD
            try {
              const parts = c.sail_date.split('-');
              const d = new Date(parts[0], parts[1] - 1, parts[2]);
              dateStr = d.toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
            } catch (e) { }

            // Ports list
            const portsStr = (c.ports || []).join(' • ');

            // Pricing
            const p = c.prices || {};
            const formatPrice = (val) => val ? `$${Math.round(val)}` : '<span class="na">--</span>';

            return `
            <div class="cruise-card">
                <div class="cruise-header">
                    <div class="cruise-title">${c.ship_name}</div>
                    <div class="cruise-meta">
                        <span>${c.nights}-Night ${c.title}</span>
                        <span>${dateStr}</span>
                    </div>
                </div>
                <div class="cruise-body">
                    <div class="cruise-ports">${portsStr}</div>
                    <div class="price-grid">
                        <div class="price-item">
                            <div class="price-label">Interior</div>
                            <div class="price-val">${formatPrice(p.INTERIOR)}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Ocean View</div>
                            <div class="price-val">${formatPrice(p.OCEANVIEW)}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Balcony</div>
                            <div class="price-val">${formatPrice(p.BALCONY)}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Suite</div>
                            <div class="price-val">${formatPrice(p.SUITE)}</div>
                        </div>
                    </div>
                </div>
            </div>
            `;
          }).join('');

        })
        .catch(err => {
          searchBtn.disabled = false;
          searchBtnText.textContent = 'Search';
          summaryDiv.innerHTML = `<span style="color:var(--err)">Failed to load: ${err}</span>`;
          gridDiv.innerHTML = '';
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
  hookGenericModal();
  hookAddonsPage();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hookCruisesPage);
  } else {
    hookCruisesPage();
  }
})();
