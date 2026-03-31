<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$code = $_GET['code'] ?? 'IG-24';
$role = $_GET['role'] ?? 'procurement';
$pageTitle = 'Закупка: ' . $code;

$requests = site_load_json('requests');
$jsonRequests = site_json_encode_for_js($requests);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Закупка: действия (демо)</div>
        </div>
    </div>

    <div class="request-detail">
        <p id="head"></p>
        <button type="button" class="btn-primary" id="btnTake">Взять в работу</button>
        <button type="button" class="btn-primary" id="btnPurchased">Закуплено (план отгрузки)</button>
        <button type="button" class="btn-primary" id="btnShipped">Отгружено</button>
        <button type="button" class="btn-secondary" id="btnReturn">Вернуть ПДО</button>
        <p class="muted" id="out"></p>
    </div>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;
  var CODE = <?= json_encode($code, JSON_UNESCAPED_UNICODE) ?: '""' ?>;

  function find() {
    var list = window.StroikaDemo.mergeRequests(BASE);
    for (var i = 0; i < list.length; i++) {
      if (list[i].request_code === CODE) return list[i];
    }
    return null;
  }

  function render() {
    var r = find();
    document.getElementById('head').textContent = r
      ? r.request_code + ' · ' + (r.stage_code || '')
      : 'Не найдено';
  }

  document.getElementById('btnTake').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'in_progress',
      stage_code: 'procurement_in_work',
      responsible_role: 'procurement',
    });
    window.StroikaDemo.addEvent({
      id: 'ev-' + Date.now(),
      request_id: r.id,
      event_type: 'procurement_taken',
      actor_user_id: 30,
      actor_role: 'procurement',
      payload_json: {},
      created_at: new Date().toISOString(),
    });
    document.getElementById('out').textContent = 'Взято в работу.';
    render();
  });

  document.getElementById('btnPurchased').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'in_progress',
      stage_code: 'purchased',
      responsible_role: 'procurement',
    });
    window.StroikaDemo.addEvent({
      id: 'ev-' + Date.now(),
      request_id: r.id,
      event_type: 'purchased',
      actor_user_id: 30,
      actor_role: 'procurement',
      payload_json: { eta_shipping: '2026-03-10' },
      created_at: new Date().toISOString(),
    });
    document.getElementById('out').textContent = 'Отмечено как закуплено.';
    render();
  });

  document.getElementById('btnShipped').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'forwarded',
      stage_code: 'shipped',
      responsible_role: 'foreman',
    });
    window.StroikaDemo.addEvent({
      id: 'ev-' + Date.now(),
      request_id: r.id,
      event_type: 'shipped',
      actor_user_id: 30,
      actor_role: 'procurement',
      payload_json: { eta_arrival: '2026-03-12' },
      created_at: new Date().toISOString(),
    });
    document.getElementById('out').textContent = 'Отгружено.';
    render();
  });

  document.getElementById('btnReturn').addEventListener('click', function () {
    var r = find();
    if (!r) return;
    window.StroikaDemo.patchRequest(r.id, {
      status_code: 'waiting',
      stage_code: 'pdo_processing',
      responsible_role: 'pdo',
    });
    window.StroikaDemo.addEvent({
      id: 'ev-' + Date.now(),
      request_id: r.id,
      event_type: 'returned_to_pdo',
      actor_user_id: 30,
      actor_role: 'procurement',
      payload_json: {},
      created_at: new Date().toISOString(),
    });
    document.getElementById('out').textContent = 'Возврат в ПДО.';
    render();
  });

  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
