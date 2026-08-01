let deferredPrompt;

/* 1. Vérifier si l’app est déjà installée */
function isAppInstalled() {
  return window.matchMedia("(display-mode: standalone)").matches
    || window.navigator.standalone === true;
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("install-btn");
  if (!btn) return;

  // Si déjà installée → on ne montre rien
  if (isAppInstalled()) {
    btn.remove();
    return;
  }

  // Clic utilisateur
  btn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    btn.remove();
  });
});

/* 2. Événement PWA officiel */
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredPrompt = e;

  const btn = document.getElementById("install-btn");
  if (btn && !isAppInstalled()) {
    btn.style.display = "block";
  }
});

/* 3. Cas où l’app vient d’être installée */
window.addEventListener("appinstalled", () => {
  document.getElementById("install-btn")?.remove();
  deferredPrompt = null;
});
