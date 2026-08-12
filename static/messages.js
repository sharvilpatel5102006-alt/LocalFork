(function () {
  function escapeHtml(str) {
    var div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function initThread(root) {
    var pollUrl = root.dataset.pollUrl;
    var sendUrl = root.dataset.sendUrl;
    var myRole = root.dataset.myRole;
    var otherName = root.dataset.otherName;
    var thread = root.querySelector(".message-thread");
    var form = root.querySelector(".message-form");
    var textarea = form ? form.querySelector('textarea[name="body"]') : null;
    var errorBox = root.querySelector(".message-error");
    var statusBadge = document.querySelector("[data-status-badge]");
    var statusBanner = document.querySelector("[data-status-banner]");
    var lastStatus = root.dataset.orderStatus;
    var shownIds = {};
    var polling = false;

    Array.prototype.forEach.call(thread.querySelectorAll(".message[data-id]"), function (el) {
      shownIds[el.dataset.id] = true;
    });

    function applyStatus(status, statusLabel) {
      if (status === lastStatus) return;
      lastStatus = status;
      if (statusBadge) {
        statusBadge.className = "badge badge-" + status;
        statusBadge.textContent = statusLabel;
      }
      if (statusBanner) {
        statusBanner.textContent = "Order status updated: " + statusLabel + ". Refresh the page to see any updated options.";
        statusBanner.style.display = "block";
      }
    }

    function appendMessage(m) {
      var empty = thread.querySelector(".empty");
      if (empty) empty.remove();
      var div = document.createElement("div");
      div.className = "message " + (m.sender_role === myRole ? "message-mine" : "message-theirs");
      div.dataset.id = m.id;
      var who = m.sender_role === myRole ? "You" : otherName;
      div.innerHTML =
        '<span class="muted small">' + escapeHtml(who) + " · " + escapeHtml(m.created_at) + "</span>" +
        "<p>" + escapeHtml(m.body) + "</p>";
      thread.appendChild(div);
    }

    function poll() {
      if (polling) return;
      polling = true;
      fetch(pollUrl, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          (data.messages || []).forEach(function (m) {
            if (!shownIds[m.id]) {
              shownIds[m.id] = true;
              appendMessage(m);
            }
          });
          if (data.status) applyStatus(data.status, data.status_label);
        })
        .catch(function () {})
        .finally(function () { polling = false; });
    }

    if (form && textarea) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var body = textarea.value.trim();
        if (!body) return;
        if (errorBox) { errorBox.style.display = "none"; errorBox.textContent = ""; }
        fetch(sendUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            Accept: "application/json",
          },
          body: "body=" + encodeURIComponent(body),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.ok) {
              textarea.value = "";
              poll();
            } else if (errorBox) {
              errorBox.textContent = data.error || "Message not sent.";
              errorBox.style.display = "block";
            }
          })
          .catch(function () {});
      });
    }

    poll();
    setInterval(poll, 3000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll("[data-message-thread]"), initThread);
  });
})();
