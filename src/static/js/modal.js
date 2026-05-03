(function () {
  function chipTextColor(hex) {
    const h = hex.replace('#', '');
    const r = parseInt(h.slice(0, 2), 16) / 255;
    const g = parseInt(h.slice(2, 4), 16) / 255;
    const b = parseInt(h.slice(4, 6), 16) / 255;
    const lin = c => c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    const lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
    return lum > 0.179 ? '#000000' : '#ffffff';
  }

  const modal     = document.getElementById('post-modal');
  const modalImg  = document.getElementById('modal-img');
  const modalDate = document.getElementById('modal-date');
  const modalChip = document.getElementById('modal-chip');
  const modalDesc = document.getElementById('modal-desc');
  const deleteBtn = document.getElementById('modal-delete');

  function openModal(tile) {
    modalImg.src = tile.dataset.img;
    modalImg.alt = tile.dataset.alt || 'HueHunt submission';
    modalDate.textContent = tile.dataset.date;
    modalDesc.textContent = tile.dataset.alt;
    modalDesc.style.display = tile.dataset.alt ? 'block' : 'none';
    const hex = tile.dataset.challenge;
    if (hex) {
      modalChip.textContent = hex;
      modalChip.style.background = hex;
      modalChip.style.color = chipTextColor(hex);
      modalChip.style.display = 'inline-block';
    } else {
      modalChip.style.display = 'none';
    }
    if (deleteBtn) deleteBtn.dataset.id = tile.dataset.id;
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
    modalImg.src = '';
  }

  document.querySelectorAll('.post-tile').forEach(tile => {
    tile.addEventListener('click', () => openModal(tile));
  });

  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-backdrop').addEventListener('click', closeModal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  if (deleteBtn) {
    deleteBtn.addEventListener('click', async () => {
      if (!confirm('Delete this post? This cannot be undone.')) return;
      const res = await fetch(`/post/${deleteBtn.dataset.id}`, { method: 'DELETE' });
      if (res.ok) window.location.reload();
      else alert('Could not delete post.');
    });
  }
})();
