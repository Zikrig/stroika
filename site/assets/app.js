(function () {
  'use strict';

  var STORAGE_KEY = 'stroika_demo_v1';

  var STATUS_TITLES = {
    waiting: 'Ждёт действия',
    in_progress: 'В работе',
    forwarded: 'Передано дальше',
    closed: 'Закрыто',
    cancelled: 'Отменено',
    paused: 'На паузе',
    terminated: 'Прекращено',
  };

  var STAGE_TITLES = {
    created: 'Создано',
    pdo_processing: 'ПДО в работе',
    transferred_to_procurement: 'Передано в закупку',
    procurement_in_work: 'Закупка в работе',
    purchased: 'Закуплено',
    shipped: 'Отгружено',
    partially_received: 'Получено частично',
    fully_received: 'Получено полностью',
    cancelled: 'Отменено',
    paused: 'Приостановлено',
    terminated: 'Прекращено руководителем',
  };

  var ROLE_TITLES = {
    foreman: 'Прораб',
    pdo: 'ПДО',
    procurement: 'Закупка',
    manager: 'Руководитель',
    viewer: 'Зритель',
  };

  function loadOverlay() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { requestsById: {}, newRequests: [], events: [], deletedIds: [] };
      var o = JSON.parse(raw);
      return {
        requestsById: o.requestsById || {},
        newRequests: o.newRequests || [],
        events: o.events || [],
        deletedIds: o.deletedIds || [],
      };
    } catch (e) {
      return { requestsById: {}, newRequests: [], events: [], deletedIds: [] };
    }
  }

  function saveOverlay(overlay) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(overlay));
  }

  function clearDemo() {
    localStorage.removeItem(STORAGE_KEY);
    location.reload();
  }

  function mergeRequests(baseList) {
    var o = loadOverlay();
    var byId = {};
    baseList.forEach(function (r) {
      if (o.deletedIds.indexOf(r.id) >= 0) return;
      var patch = o.requestsById[r.id];
      byId[r.id] = patch ? Object.assign({}, r, patch) : Object.assign({}, r);
    });
    o.newRequests.forEach(function (r) {
      if (o.deletedIds.indexOf(r.id) >= 0) return;
      var patch = o.requestsById[r.id];
      byId[r.id] = patch ? Object.assign({}, r, patch) : Object.assign({}, r);
    });
    return Object.keys(byId).map(function (id) {
      return byId[id];
    });
  }

  function mergeEvents(baseEvents) {
    var o = loadOverlay();
    var extra = o.events || [];
    return baseEvents.concat(extra).sort(function (a, b) {
      return (a.created_at || '').localeCompare(b.created_at || '');
    });
  }

  function patchRequest(id, fields) {
    var o = loadOverlay();
    o.requestsById[id] = Object.assign({}, o.requestsById[id] || {}, fields);
    saveOverlay(o);
  }

  function addRequest(req) {
    var o = loadOverlay();
    o.newRequests.push(req);
    saveOverlay(o);
  }

  function addEvent(ev) {
    var o = loadOverlay();
    o.events.push(ev);
    saveOverlay(o);
  }

  function deleteRequest(id) {
    var o = loadOverlay();
    if (o.deletedIds.indexOf(id) < 0) o.deletedIds.push(id);
    saveOverlay(o);
  }

  function formatStatus(code) {
    var title = STATUS_TITLES[code] || code || '-';
    var cls = 'status-' + String(code || '').replace(/[^a-z_]/g, '');
    return '<span class="status-pill ' + cls + '">' + escapeHtml(title) + '</span>';
  }

  function formatStage(code) {
    var title = STAGE_TITLES[code] || code || '-';
    return '<span class="muted">' + escapeHtml(title) + '</span>';
  }

  function formatRole(code) {
    if (!code) return '<span class="muted">—</span>';
    var title = ROLE_TITLES[code] || code;
    return '<span class="role-pill">' + escapeHtml(title) + '</span>';
  }

  function fmtQty(value) {
    var num = parseFloat(value || 0);
    if (isNaN(num)) return '-';
    if (Number.isInteger(num)) return String(num);
    return num.toFixed(2).replace(/\.?0+$/, '');
  }

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function foremanName(uid, users) {
    if (!users || !uid) return '—';
    var u = users.find(function (x) {
      return x.id === uid;
    });
    return u ? u.display_name || String(uid) : String(uid);
  }

  function renderTableRow(r, users) {
    var remaining = parseFloat(r.remaining_qty || 0);
    var remainingClass = remaining <= 0 ? 'qty-remaining-zero' : 'qty-remaining-positive';
    var fn = foremanName(r.foreman_user_id, users);
    return (
      '<tr>' +
      '<td class="col-id"><a class="link-code" href="request.php?code=' +
      encodeURIComponent(r.request_code) +
      '&role=' +
      encodeURIComponent(new URLSearchParams(location.search).get('role') || 'chairman') +
      '">' +
      escapeHtml(r.request_code) +
      '</a></td>' +
      '<td>' +
      formatStatus(r.status_code) +
      '<div>' +
      formatStage(r.stage_code) +
      '</div></td>' +
      '<td class="col-object"><div>' +
      escapeHtml(r.object_name || '-') +
      '</div><div class="muted">' +
      escapeHtml(r.subobject_name || '—') +
      '</div></td>' +
      '<td class="col-name"><div>' +
      escapeHtml(r.nomenclature_1c || r.name_from_foreman || '—') +
      '</div><div class="muted">' +
      escapeHtml(r.name_from_foreman || '') +
      '</div></td>' +
      '<td class="qty">' +
      fmtQty(r.requested_qty) +
      ' ' +
      escapeHtml(r.unit || '') +
      '</td>' +
      '<td class="qty">' +
      fmtQty(r.from_stock_qty) +
      ' / ' +
      fmtQty(r.to_purchase_qty) +
      '</td>' +
      '<td class="qty">' +
      fmtQty(r.received_total_qty) +
      ' / <span class="' +
      remainingClass +
      '">' +
      fmtQty(r.remaining_qty) +
      '</span></td>' +
      '<td>' +
      formatRole(r.responsible_role) +
      '<div class="muted">' +
      escapeHtml(fn) +
      '</div></td>' +
      '<td>' +
      (r.approved_by ? escapeHtml(r.approved_by) : '<span class="muted">—</span>') +
      '</td>' +
      '<td><div>' +
      escapeHtml(r.need_by || '—') +
      '</div><div class="muted">' +
      escapeHtml(String(r.created_at || '').slice(0, 16)) +
      '</div></td>' +
      '</tr>'
    );
  }

  window.StroikaDemo = {
    STORAGE_KEY: STORAGE_KEY,
    loadOverlay: loadOverlay,
    mergeRequests: mergeRequests,
    mergeEvents: mergeEvents,
    patchRequest: patchRequest,
    addRequest: addRequest,
    addEvent: addEvent,
    deleteRequest: deleteRequest,
    clearDemo: clearDemo,
  };

  window.StroikaFmt = {
    STATUS_TITLES: STATUS_TITLES,
    STAGE_TITLES: STAGE_TITLES,
    ROLE_TITLES: ROLE_TITLES,
    formatStatus: formatStatus,
    formatStage: formatStage,
    formatRole: formatRole,
    fmtQty: fmtQty,
    escapeHtml: escapeHtml,
    foremanName: foremanName,
    renderTableRow: renderTableRow,
  };
})();
