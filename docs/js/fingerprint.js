/**
 * Device fingerprinting for Spupoll participants.
 * Generates a stable UUID stored in localStorage.
 * Consistent across the pre- and post-discussion polls
 * as long as the participant uses the same browser.
 */
(function () {
  const KEY = "spupoll_device_id";

  function uuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function getOrCreate() {
    try {
      let id = localStorage.getItem(KEY);
      if (!id) {
        id = uuid();
        localStorage.setItem(KEY, id);
      }
      return id;
    } catch {
      // localStorage unavailable (private mode, etc.) — session-only ID
      if (!window._spupollTempId) window._spupollTempId = uuid();
      return window._spupollTempId;
    }
  }

  window.getDeviceId = getOrCreate;
})();
