/**
 * Administrator Dashboard JavaScript
 */

document.addEventListener("DOMContentLoaded", function () {
  // Tab Switching
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", function () {
      const targetTab = this.getAttribute("data-tab");

      tabButtons.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => (p.style.display = "none"));

      this.classList.add("active");
      const activePane = document.getElementById(`tab-${targetTab}`);
      if (activePane) {
        activePane.style.display = "block";
      }
    });
  });

  // Table Search Filter
  const searchInput = document.getElementById("adminUserSearch");
  if (searchInput) {
    searchInput.addEventListener("input", function () {
      const query = this.value.toLowerCase().trim();
      const rows = document.querySelectorAll(".user-data-row");

      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? "" : "none";
      });
    });
  }

  // Auto-Refresh
  const autoRefreshToggle = document.getElementById("autoRefreshToggle");
  let refreshTimer = null;

  if (autoRefreshToggle) {
    function setupRefresh() {
      if (autoRefreshToggle.checked) {
        if (!refreshTimer) {
          refreshTimer = setInterval(() => {
            window.location.reload();
          }, 6000);
        }
      } else {
        if (refreshTimer) {
          clearInterval(refreshTimer);
          refreshTimer = null;
        }
      }
    }

    autoRefreshToggle.addEventListener("change", setupRefresh);
  }
});
