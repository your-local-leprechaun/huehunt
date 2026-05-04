/**
 * Activates the given auth tab (e.g. "signin" or "signup") and shows its
 * corresponding panel, hiding all others.
 *
 * @param {string} name - The tab name matching a data-tab attribute and panel ID.
 */
function activateTab(name) {
  document
    .querySelectorAll(".auth-tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".auth-panel")
    .forEach((p) => p.classList.add("hidden"));
  const tab = document.querySelector(`.auth-tab[data-tab="${name}"]`);
  if (tab) tab.classList.add("active");
  const panel = document.getElementById("panel-" + name);
  if (panel) panel.classList.remove("hidden");
}

document.querySelectorAll(".auth-tab").forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

// Allow the server to redirect back to a specific tab via ?tab=signup in the URL
const initialTab = new URLSearchParams(window.location.search).get("tab");
if (initialTab) activateTab(initialTab);
