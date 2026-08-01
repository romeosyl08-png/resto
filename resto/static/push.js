console.log("push.js chargé");

const VAPID_PUBLIC_KEY = "{{ VAPID_PUBLIC_KEY }}";

// ================== PUSH ==================
async function askPushPermission() {
  console.log("Demande permission push");

  document.getElementById("push-popup")?.remove();
  localStorage.setItem("pushAccepted", "true");
  document.cookie = "pushAccepted=true; path=/; max-age=31536000";

  if (!("Notification" in window)) return;

  const permission = await Notification.requestPermission();
  if (permission !== "granted") return;

  const reg = await navigator.serviceWorker.register("/static/sw.js");

  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: VAPID_PUBLIC_KEY
  });

  await fetch("/push/subscribe/", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(sub)
  });

  console.log("Push OK");
}

function postponePush() {
  document.getElementById("push-popup")?.remove();
  console.log("Push reporté");
}

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM prêt (push)");

  if (localStorage.getItem("pushAccepted")) {
    document.getElementById("push-popup")?.remove();
    return;
  }

  document.getElementById("push-yes")
    ?.addEventListener("click", askPushPermission);

  document.getElementById("push-later")
    ?.addEventListener("click", postponePush);
});
