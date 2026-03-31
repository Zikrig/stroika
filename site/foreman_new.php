<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'foreman';
$pageTitle = 'Новая заявка — демо';
$activeNav = 'foreman_new';

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Новая заявка (мастер)</div>
            <p class="page-subtitle">Демо: создаётся запись в localStorage (не на сервере)</p>
        </div>
    </div>

    <div class="wizard-steps" id="steps">
        <span class="wizard-step active" data-step="1">1. Описание</span>
        <span class="wizard-step" data-step="2">2. Кол-во</span>
        <span class="wizard-step" data-step="3">3. Подобъект</span>
        <span class="wizard-step" data-step="4">4. Срок</span>
        <span class="wizard-step" data-step="5">5. Согласовано</span>
    </div>

    <div class="request-detail" id="panel1">
        <label class="form-block">Описание<textarea id="desc" rows="4" placeholder="Текст заявки"></textarea></label>
        <button type="button" class="btn-primary" id="next1">Далее</button>
    </div>
    <div class="request-detail" id="panel2" style="display:none">
        <label class="form-block">Количество<input type="text" id="qty" placeholder="10 или 0"></label>
        <button type="button" class="btn-primary" id="next2">Далее</button>
    </div>
    <div class="request-detail" id="panel3" style="display:none">
        <label class="form-block">Подобъект (или -)<input type="text" id="sub" placeholder="-"></label>
        <button type="button" class="btn-primary" id="next3">Далее</button>
    </div>
    <div class="request-detail" id="panel4" style="display:none">
        <label class="form-block">Срок need_by (или -)<input type="text" id="need" placeholder="2026-04-01"></label>
        <button type="button" class="btn-primary" id="next4">Далее</button>
    </div>
    <div class="request-detail" id="panel5" style="display:none">
        <label class="form-block">С кем согласовано<input type="text" id="appr" placeholder="ФИО"></label>
        <button type="button" class="btn-primary" id="save">Создать заявку</button>
    </div>

    <p class="muted" id="result"></p>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;

  function nextParentCode(list) {
    var max = 0;
    list.forEach(function (r) {
      if (r.parent_request_id) return;
      var m = /^IG-(\d+)$/.exec(r.request_code || '');
      if (m) max = Math.max(max, parseInt(m[1], 10));
    });
    return 'IG-' + (max + 1);
  }

  function showPanel(n) {
    for (var i = 1; i <= 5; i++) {
      document.getElementById('panel' + i).style.display = i === n ? 'block' : 'none';
    }
    document.querySelectorAll('.wizard-step').forEach(function (el) {
      el.classList.toggle('active', el.getAttribute('data-step') === String(n));
    });
  }

  document.getElementById('next1').addEventListener('click', function () {
    showPanel(2);
  });
  document.getElementById('next2').addEventListener('click', function () {
    showPanel(3);
  });
  document.getElementById('next3').addEventListener('click', function () {
    showPanel(4);
  });
  document.getElementById('next4').addEventListener('click', function () {
    showPanel(5);
  });

  document.getElementById('save').addEventListener('click', function () {
    var list = window.StroikaDemo.mergeRequests(BASE);
    var code = nextParentCode(list);
    var id = 'demo-req-' + Date.now();
    var qty = parseFloat((document.getElementById('qty').value || '0').replace(',', '.')) || 0;
    var sub = document.getElementById('sub').value.trim();
    var need = document.getElementById('need').value.trim();
    var appr = document.getElementById('appr').value.trim();
    var desc = document.getElementById('desc').value.trim() || 'Без описания';

    var req = {
      id: id,
      request_code: code,
      chat_id: -1001234567890,
      parent_request_id: null,
      is_container: 0,
      foreman_user_id: 10,
      object_name: 'Игора. Демо',
      subobject_name: sub === '-' || sub === '' ? null : sub,
      name_from_foreman: desc,
      nomenclature_1c: null,
      code_1c: '',
      requested_qty: qty,
      unit: 'шт',
      from_stock_qty: 0,
      to_purchase_qty: qty,
      received_total_qty: 0,
      remaining_qty: qty,
      status_code: 'waiting',
      stage_code: 'created',
      responsible_role: 'pdo',
      approved_by: appr || null,
      need_by: need === '-' || need === '' ? null : need,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    window.StroikaDemo.addRequest(req);
    window.StroikaDemo.addEvent({
      id: 'demo-ev-new-' + Date.now(),
      request_id: id,
      event_type: 'request_created',
      actor_user_id: 10,
      actor_role: 'foreman',
      payload_json: { request_code: code },
      created_at: new Date().toISOString(),
    });
    document.getElementById('result').innerHTML =
      'Создана заявка <strong>' +
      code +
      '</strong>. Откройте <a href="request.php?code=' +
      encodeURIComponent(code) +
      '&role=foreman">карточку</a> или <a href="foreman_requests.php?role=foreman">список</a>.';
  });
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
