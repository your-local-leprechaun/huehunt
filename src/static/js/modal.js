(function () {
  /**
   * Returns black or white depending on which is more readable against the given
   * hex background, using the WCAG relative luminance formula.
   *
   * This mirrors the Python `luminance` function in challenges.py. A JS copy is
   * needed here because the color chip is rendered dynamically on the client
   * after the page loads, so the server-side template filter can't be used.
   *
   * @param {string} hex - Hex color string (e.g. "#a3f0c2").
   * @returns {string} "#000000" or "#ffffff".
   */
  function chipTextColor(hex) {
    const h = hex.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16) / 255;
    const g = parseInt(h.slice(2, 4), 16) / 255;
    const b = parseInt(h.slice(4, 6), 16) / 255;
    const lin = (c) =>
      c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return lum > 0.179 ? "#000000" : "#ffffff";
  }

  const modal = document.getElementById("post-modal");
  const modalImg = document.getElementById("modal-img");
  const modalDate = document.getElementById("modal-date");
  const modalChip = document.getElementById("modal-chip");
  const modalDesc = document.getElementById("modal-desc");
  const deleteBtn = document.getElementById("modal-delete");

  /**
   * Populates and opens the modal with data from the clicked post tile.
   * Reads image, alt text, date, challenge color, and post ID from the
   * tile's data attributes. Locks body scroll while the modal is open.
   *
   * @param {HTMLElement} tile - The .post-tile element that was clicked.
   */
  function openModal(tile) {
    modalImg.src = tile.dataset.img;
    modalImg.alt = tile.dataset.alt || "HueHunt submission";
    modalDate.textContent = tile.dataset.date;
    modalDesc.textContent = tile.dataset.alt;
    modalDesc.style.display = tile.dataset.alt ? "block" : "none";
    const hex = tile.dataset.challenge;
    if (hex) {
      modalChip.textContent = hex;
      modalChip.style.background = hex;
      modalChip.style.color = chipTextColor(hex);
      modalChip.style.display = "inline-block";
    } else {
      modalChip.style.display = "none";
    }
    if (deleteBtn) deleteBtn.dataset.id = tile.dataset.id;
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  /**
   * Closes the modal and restores body scroll.
   * Clears the image src to cancel any in-flight image load.
   */
  function closeModal() {
    modal.classList.add("hidden");
    document.body.style.overflow = "";
    modalImg.src = "";
  }

  document.querySelectorAll(".post-tile").forEach((tile) => {
    tile.addEventListener("click", () => openModal(tile));
  });

  document.getElementById("modal-close").addEventListener("click", closeModal);
  // Close when clicking the backdrop behind the modal
  document
    .getElementById("modal-backdrop")
    .addEventListener("click", closeModal);
  // Close on Escape key
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  // Delete button is only present on the user's own profile page
  if (deleteBtn) {
    deleteBtn.addEventListener("click", async () => {
      if (!confirm("Delete this post? This cannot be undone.")) return;
      const res = await fetch(`/post/${deleteBtn.dataset.id}`, {
        method: "DELETE",
      });
      if (res.ok) window.location.reload();
      else alert("Could not delete post.");
    });
  }
})();
