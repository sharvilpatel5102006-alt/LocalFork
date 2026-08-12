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

  function updateNavBadgeCounts(newOrders, unreadMessages) {
    var ordersBadge = document.querySelector("[data-orders-badge]");
    var messagesBadge = document.querySelector("[data-messages-badge]");
    if (ordersBadge && newOrders !== null && newOrders !== undefined) {
      ordersBadge.textContent = newOrders;
      ordersBadge.style.display = newOrders ? "" : "none";
    }
    if (messagesBadge && unreadMessages !== null && unreadMessages !== undefined) {
      messagesBadge.textContent = unreadMessages;
      messagesBadge.style.display = unreadMessages ? "" : "none";
    }
  }

  function initNavBadges(root) {
    var url = root.dataset.navStatusUrl;

    function poll() {
      fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          updateNavBadgeCounts(data.new_orders, data.unread_messages);
        })
        .catch(function () {});
    }

    setInterval(poll, 5000);
  }

  function renderOrderRow(o, orderUrlTemplate, acceptUrlTemplate) {
    var orderUrl = orderUrlTemplate.replace("999999", o.id);
    var div = document.createElement("div");
    div.className = "order-row" + (o.due_soon ? " order-row-soon" : "");
    div.dataset.orderRow = o.id;

    var dueSoonBadge = o.due_soon ? '<span class="badge badge-soon">Due soon</span>' : "";
    var actions = "";
    if (o.status === "placed") {
      var actionUrl = acceptUrlTemplate.replace("999999", o.id);
      actions =
        '<div class="menu-actions">' +
        '<form method="post" action="' + actionUrl + '"><input type="hidden" name="status" value="accepted"><button type="submit" class="btn-small">Accept</button></form>' +
        '<form method="post" action="' + actionUrl + '"><input type="hidden" name="status" value="declined"><button type="submit" class="btn-ghost small danger">Decline</button></form>' +
        "</div>";
    }

    div.innerHTML =
      '<a class="order-row-main" href="' + orderUrl + '">' +
      "<div><strong>" + escapeHtml(o.buyer_name) + "</strong>" +
      '<p class="muted small">Pickup ' + escapeHtml(o.pickup_display) + " · " + escapeHtml(o.fulfillment) + " " + dueSoonBadge + "</p></div>" +
      '<span class="badge badge-' + o.status + '">' + escapeHtml(o.status_label) + "</span>" +
      '<div class="order-total">' + escapeHtml(o.total_display) + "</div>" +
      "</a>" + actions;
    return div;
  }

  function initOrdersPage(root) {
    var pollUrl = root.dataset.ordersPollUrl;
    var orderUrlTemplate = root.dataset.orderUrlTemplate;
    var acceptUrlTemplate = root.dataset.acceptUrlTemplate;
    var listContainer = root.querySelector("[data-orders-list-container]");
    var banner = root.querySelector("[data-due-soon-banner]");
    var bannerCount = root.querySelector("[data-due-soon-count]");
    var bannerWord = root.querySelector("[data-due-soon-word]");
    var lastSignature = null;

    function poll() {
      fetch(pollUrl, { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var signature = JSON.stringify((data.orders || []).map(function (o) { return o.id + ":" + o.status; }));
          if (signature === lastSignature) return;
          lastSignature = signature;

          listContainer.innerHTML = "";
          if (data.orders && data.orders.length) {
            var listDiv = document.createElement("div");
            listDiv.className = "order-list";
            data.orders.forEach(function (o) {
              listDiv.appendChild(renderOrderRow(o, orderUrlTemplate, acceptUrlTemplate));
            });
            listContainer.appendChild(listDiv);
          } else {
            listContainer.innerHTML = '<p class="empty">No orders to make right now.</p>';
          }

          if (banner && bannerCount) {
            if (data.due_soon_count > 0) {
              bannerCount.textContent = data.due_soon_count;
              if (bannerWord) bannerWord.textContent = data.due_soon_count === 1 ? "order" : "orders";
              banner.style.display = "block";
            } else {
              banner.style.display = "none";
            }
          }

          updateNavBadgeCounts(data.new_orders, null);
        })
        .catch(function () {});
    }

    setInterval(poll, 4000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll("[data-message-thread]"), initThread);
    Array.prototype.forEach.call(document.querySelectorAll("[data-nav-badges]"), initNavBadges);
    Array.prototype.forEach.call(document.querySelectorAll("[data-orders-page]"), initOrdersPage);
  });
})();
