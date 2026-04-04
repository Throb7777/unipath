document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const copySuccess = body?.dataset.copySuccess || "Copied";
  const copyFailed = body?.dataset.copyFailed || "Copy failed";
  const select = document.querySelector("[data-executor-select]");
  const radios = document.querySelectorAll("[data-executor-select-radio]");
  const syncGroups = () => {
    if (!select) return;
    const value = select.value;
    document.querySelectorAll("[data-executor-group]").forEach((group) => {
      const active = group.getAttribute("data-executor-group") === value;
      group.style.display = active ? "block" : "none";
    });
    document.querySelectorAll("[data-executor-hint]").forEach((hint) => {
      const active = hint.getAttribute("data-executor-hint") === value;
      hint.classList.toggle("active", active);
    });
    radios.forEach((radio) => {
      const wrapper = radio.closest(".executor-option");
      if (!wrapper) return;
      const active = radio.value === value;
      wrapper.classList.toggle("active", active);
      radio.checked = active;
    });
  };

  if (select) {
    select.addEventListener("change", syncGroups);
    syncGroups();
  }

  radios.forEach((radio) => {
    radio.addEventListener("change", () => {
      if (!select) return;
      select.value = radio.value;
      syncGroups();
    });
  });

  document.querySelectorAll("[data-copy-text]").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.getAttribute("data-copy-text") || "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        const previous = button.textContent;
        button.textContent = copySuccess;
        window.setTimeout(() => {
          button.textContent = previous;
        }, 1200);
      } catch (_error) {
        button.textContent = copyFailed;
      }
    });
  });
});
