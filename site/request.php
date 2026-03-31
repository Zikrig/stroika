<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$code = $_GET['code'] ?? 'IG-24';
$role = $_GET['role'] ?? 'chairman';
$pageTitle = 'Заявка ' . $code;
$activeNav = '';

$requests = site_load_json('requests');
$events = site_load_json('events');
$attachments = site_load_json('attachments');
$users = site_load_json('users');

$jsonRequests = site_json_encode_for_js($requests);
$jsonEvents = site_json_encode_for_js($events);
$jsonAttachments = site_json_encode_for_js($attachments);
$jsonUsers = site_json_encode_for_js($users);
$initialCode = json_encode($code, JSON_UNESCAPED_UNICODE);
if ($initialCode === false) {
    $initialCode = '""';
}

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title" id="reqTitle">Заявка</div>
            <p class="page-subtitle"><a href="cards_chairman.php?role=<?= htmlspecialchars(urlencode($role), ENT_QUOTES, 'UTF-8') ?>">← К таблице</a></p>
        </div>
        <div class="header-controls">
            <button type="button" class="btn-secondary" id="btnResetDemo">Сбросить демо (localStorage)</button>
        </div>
    </div>

    <div id="notFound" class="muted" style="display:none">Заявка не найдена (проверьте код в адресе).</div>

    <div id="reqDetail" style="display:none">
        <div class="request-detail">
            <h2 id="reqCodeLine"></h2>
            <div class="request-grid" id="reqGrid"></div>
        </div>

        <div class="request-detail" id="containerBlock" style="display:none">
            <h3>Дочерние заявки (дробление)</h3>
            <ul id="childrenList"></ul>
        </div>

        <div class="request-detail">
            <h3>История событий</h3>
            <ul class="event-list" id="eventList"></ul>
        </div>

        <div class="request-detail">
            <h3>Вложения</h3>
            <ul class="event-list" id="attachList"></ul>
        </div>

        <div class="request-detail" id="managerActions" style="display:none">
            <h3>Действия руководителя (демо)</h3>
            <p class="muted">Записывается в localStorage как новые события.</p>
            <button type="button" class="btn-primary" id="btnComment">Комментарий</button>
            <button type="button" class="btn-primary" id="btnPause">Пауза</button>
            <button type="button" class="btn-primary" id="btnResume">Снять паузу</button>
            <button type="button" class="btn-primary" id="btnTerminate">Прекратить</button>
        </div>
    </div>

    <div class="modal-backdrop" id="modal">
        <div class="modal">
            <h3 id="modalTitle">Ввод</h3>
            <textarea id="modalText" rows="4" placeholder="Текст..."></textarea>
            <div>
                <button type="button" class="btn-primary" id="modalOk">OK</button>
                <button type="button" class="btn-reset" id="modalCancel">Отмена</button>
            </div>
        </div>
    </div>
<?php
ob_start();
?>
<script>
(function () {
  var BASE_REQ = <?= $jsonRequests ?>;
  var BASE_EV = <?= $jsonEvents ?>;
  var BASE_ATT = <?= $jsonAttachments ?>;
  var USERS = <?= $jsonUsers ?>;
  var CODE = <?= $initialCode ?>;
  var ROLE = <?= json_encode($role, JSON_UNESCAPED_UNICODE) ?: '""' ?>;

  var modal = document.getElementById('modal');
  var modalText = document.getElementById('modalText');
  var modalOk = document.getElementById('modalOk');
  var modalCancel = document.getElementById('modalCancel');
  var modalTitle = document.getElementById('modalTitle');
  var pendingAction = null;

  function findRequest() {
    var list = window.StroikaDemo.mergeRequests(BASE_REQ);
    var c = CODE;
    for (var i = 0; i < list.length; i++) {
      if (list[i].request_code === c) return list[i];
    }
    return null;
  }

  function isoNow() {
    return new Date().toISOString();
  }

  function pushEvent(requestId, type, payload) {
    window.StroikaDemo.addEvent({
      id: 'demo-ev-' + Date.now(),
      request_id: requestId,
      event_type: type,
      actor_user_id: 99,
      actor_role: 'manager',
      payload_json: payload || {},
      created_at: isoNow(),
    });
  }

  function render() {
    var r = findRequest();
    var nf = document.getElementById('notFound');
    var rd = document.getElementById('reqDetail');
    if (!r) {
      nf.style.display = 'block';
      rd.style.display = 'none';
      return;
    }
    nf.style.display = 'none';
    rd.style.display = 'block';

    document.getElementById('reqTitle').textContent = 'Заявка ' + r.request_code;
    document.getElementById('reqCodeLine').textContent = r.request_code + (r.is_container ? ' (контейнер)' : '');

    var f = window.StroikaFmt;
    var rows = [
      ['Статус', f.formatStatus(r.status_code)],
      ['Этап', f.formatStage(r.stage_code)],
      ['Объект', f.escapeHtml(r.object_name || '—')],
      ['Подобъект', f.escapeHtml(r.subobject_name || '—')],
      ['От прораба', f.escapeHtml(r.name_from_foreman || '—')],
      ['Номенклатура 1С', f.escapeHtml(r.nomenclature_1c || '—')],
      ['Код 1С', f.escapeHtml(r.code_1c || '—')],
      ['Запрошено', f.fmtQty(r.requested_qty) + ' ' + (r.unit || '')],
      ['Со склада / в закупку', f.fmtQty(r.from_stock_qty) + ' / ' + f.fmtQty(r.to_purchase_qty)],
      ['Получено / остаток', f.fmtQty(r.received_total_qty) + ' / ' + f.fmtQty(r.remaining_qty)],
      ['Ответственный', f.formatRole(r.responsible_role)],
      ['С кем согласовано', f.escapeHtml(r.approved_by || '—')],
      ['Срок need_by', f.escapeHtml(r.need_by || '—')],
    ];
    var html = '';
    rows.forEach(function (row) {
      html += '<dt>' + f.escapeHtml(row[0]) + '</dt><dd>' + row[1] + '</dd>';
    });
    document.getElementById('reqGrid').innerHTML = html;

    var list = window.StroikaDemo.mergeRequests(BASE_REQ);
    var children = list.filter(function (x) {
      return x.parent_request_id === r.id;
    });
    var cb = document.getElementById('containerBlock');
    var cl = document.getElementById('childrenList');
    if (children.length) {
      cb.style.display = 'block';
      cl.innerHTML = children
        .map(function (ch) {
          return (
            '<li><a class="link-code" href="request.php?code=' +
            encodeURIComponent(ch.request_code) +
            '&role=' +
            encodeURIComponent(ROLE) +
            '">' +
            f.escapeHtml(ch.request_code) +
            '</a> — ' +
            f.escapeHtml(ch.nomenclature_1c || ch.name_from_foreman || '') +
            '</li>'
          );
        })
        .join('');
    } else {
      cb.style.display = 'none';
    }

    var evAll = window.StroikaDemo.mergeEvents(BASE_EV);
    var evs = evAll.filter(function (e) {
      return e.request_id === r.id;
    });
    document.getElementById('eventList').innerHTML = evs
      .map(function (e) {
        return (
          '<li><strong>' +
          f.escapeHtml(e.event_type) +
          '</strong> · ' +
          f.escapeHtml(String(e.created_at || '').slice(0, 19)) +
          '</li>'
        );
      })
      .join('') || '<li class="muted">Нет событий</li>';

    var atts = BASE_ATT.filter(function (a) {
      return a.request_id === r.id;
    });
    document.getElementById('attachList').innerHTML = atts
      .map(function (a) {
        return (
          '<li>' +
          f.escapeHtml(a.attachment_type) +
          ': ' +
          f.escapeHtml(a.file_name || '') +
          '</li>'
        );
      })
      .join('') || '<li class="muted">Нет вложений</li>';

    var ma = document.getElementById('managerActions');
    if (ROLE === 'chairman' || ROLE === 'admin' || ROLE === 'manager') {
      ma.style.display = 'block';
    } else {
      ma.style.display = 'none';
    }
  }

  function openModal(title, onOk) {
    modalTitle.textContent = title;
    modalText.value = '';
    modal.classList.add('open');
    pendingAction = onOk;
  }

  function closeModal() {
    modal.classList.remove('open');
    pendingAction = null;
  }

  modalOk.addEventListener('click', function () {
    if (pendingAction) pendingAction(modalText.value);
    closeModal();
  });
  modalCancel.addEventListener('click', closeModal);

  document.getElementById('btnResetDemo').addEventListener('click', function () {
    window.StroikaDemo.clearDemo();
  });

  document.getElementById('btnComment').addEventListener('click', function () {
    var r = findRequest();
    if (!r) return;
    openModal('Комментарий руководителя', function (text) {
      pushEvent(r.id, 'manager_commented', { comment: text });
      render();
    });
  });
  document.getElementById('btnPause').addEventListener('click', function () {
    var r = findRequest();
    if (!r) return;
    openModal('Причина паузы', function (text) {
      window.StroikaDemo.patchRequest(r.id, {
        status_code: 'paused',
        stage_code: 'paused',
        responsible_role: null,
      });
      pushEvent(r.id, 'paused', { reason: text });
      render();
    });
  });
  document.getElementById('btnResume').addEventListener('click', function () {
    var r = findRequest();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'waiting',
      stage_code: 'pdo_processing',
      responsible_role: 'pdo',
    });
    pushEvent(r.id, 'resumed', { comment: 'demo resume' });
    render();
  });
  document.getElementById('btnTerminate').addEventListener('click', function () {
    var r = findRequest();
    if (!r) return;
    openModal('Причина прекращения', function (text) {
      window.StroikaDemo.patchRequest(r.id, {
        status_code: 'terminated',
        stage_code: 'terminated',
        responsible_role: null,
        remaining_qty: 0,
      });
      pushEvent(r.id, 'terminated', { reason: text });
      render();
    });
  });

  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
